#!/usr/bin/env python3
"""Calibrate, freeze, then evaluate an EchoLocal wake model without touching hardware."""
import argparse
import contextlib
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import wave

SCHEMA = 1
RUNTIME = "github.com/zserge/microwakeword@v0.0.0-20260330234603-bfaf3840114e"
OFFLINE_GATES = ("runtime", "strict_parity", "positive_recall", "zero_negative_events",
                 "negative_duration", "clean_holdout")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stamp(path):
    p = Path(path).resolve(strict=True)
    if not p.is_file():
        raise ValueError(f"not a regular file: {p}")
    return {"path": str(p), "sha256": sha(p)}


def verify_file(item):
    if sha(item["path"]) != item["sha256"]:
        raise ValueError(f"frozen file changed: {item['path']}")


def save(path, obj):
    """Never overwrite evidence. Sidecar hashes cover the exact JSON bytes."""
    path = Path(path)
    data = (json.dumps(obj, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    digest = hashlib.sha256(data).hexdigest()
    with path.with_suffix(".sha256").open("x") as f:
        f.write(digest + "\n")
    return digest


def load_verified(path):
    path = Path(path)
    if sha(path) != path.with_suffix(".sha256").read_text().strip():
        raise ValueError(f"evidence checksum mismatch: {path}")
    return json.loads(path.read_text())


def path_under(root, value):
    p = (root / value).resolve(strict=True)
    p.relative_to(root.resolve())
    return p


def snapshot_manifest(path):
    """Lock bytes and each audio source; retain optional LibriSpeech member hashes."""
    path = Path(path).resolve(strict=True)
    record = stamp(path)
    rows, seen, seen_audio = [], set(), set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) - {"id", "label", "wav", "pcm", "leading_ms", "trailing_ms"}:
            raise ValueError("unknown manifest field")
        if not isinstance(row.get("id"), str) or not row["id"] or row["id"] in seen:
            raise ValueError("manifest ids must be unique nonempty strings")
        seen.add(row["id"])
        if row.get("label") not in ("positive", "negative"):
            raise ValueError("manifest labels must be positive or negative")
        kinds = [k for k in ("wav", "pcm") if row.get(k)]
        if len(kinds) != 1:
            raise ValueError("manifest row requires exactly one wav or pcm")
        kind = kinds[0]
        source = (path.parent / row[kind]).resolve(strict=True)
        for field in ("leading_ms", "trailing_ms"):
            n = row.get(field, 0)
            if not isinstance(n, int) or not 0 <= n <= 10000:
                raise ValueError("padding must be integer milliseconds in [0,10000]")
        if row.get("leading_ms", 0) < 3000:
            raise ValueError("this protocol requires at least 3000ms leading warmup")
        if kind == "wav":
            with wave.open(str(source)) as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getcomptype()) != (16000, 1, 2, "NONE"):
                    raise ValueError(f"audio must be PCM16 mono 16kHz: {source}")
                samples = w.getnframes()
                # Normalized PCM identity also detects the same recording in a different WAV container.
                pcm_hash = hashlib.sha256(w.readframes(samples)).hexdigest()
        else:
            if source.stat().st_size % 2:
                raise ValueError("raw PCM byte count must be even")
            samples = source.stat().st_size // 2
            pcm_hash = sha(source)
        if samples < 480:
            raise ValueError("source audio must contain at least 30ms")
        if pcm_hash in seen_audio:
            raise ValueError("duplicate audio within one manifest; do not inflate clip counts")
        seen_audio.add(pcm_hash)
        rows.append({"id": row["id"], "label": row["label"], "audio": stamp(source),
                     "pcm_sha256": pcm_hash, "source_seconds": samples / 16000,
                     "leading_ms": row.get("leading_ms", 0), "trailing_ms": row.get("trailing_ms", 0)})
    if not rows:
        raise ValueError("empty manifest")
    record["rows"] = rows
    provenance = path.parent / "provenance.json"
    if provenance.is_file():
        metadata = json.loads(provenance.read_text())
        record["provenance"] = stamp(provenance)
        # The supplied prep tool writes this sidecar. It is evidence, not an independently trusted attestation.
        record["member_pcm_sha256"] = sorted({r["pcm_sha256"] for r in metadata.get("files", [])
                                               if "pcm_sha256" in r})
    return record


def identities(manifests):
    return {r["pcm_sha256"] for m in manifests for r in m["rows"]} | {
        h for m in manifests for h in m.get("member_pcm_sha256", [])}


def snapshots(paths):
    result = [snapshot_manifest(p) for p in paths]
    if len({r["path"] for r in result}) != len(result):
        raise ValueError("duplicate manifest")
    seen = set()
    for m in result:
        current = {r["pcm_sha256"] for r in m["rows"]} | set(m.get("member_pcm_sha256", []))
        if seen & current:
            raise ValueError("overlapping audio across manifests; do not count both concatenated and per-utterance versions")
        seen |= current
    return result


def verify_manifests(records):
    for record in records:
        if snapshot_manifest(record["path"]) != record:
            raise ValueError(f"frozen manifest/audio/provenance changed: {record['path']}")


@contextlib.contextmanager
def exclusive(evaluation):
    evaluation.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = evaluation / ".evaluation.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        lock.unlink()


def run_dir(a):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", a.run_id):
        raise ValueError("run-id must be a simple name, not a path")
    return a.work_dir.resolve() / "evaluation" / a.run_id


def parity_evidence(paths, model):
    evidence = []
    for path in paths:
        report = json.loads(Path(path).read_text())
        if report.get("model_sha256") != model["sha256"]:
            raise ValueError("parity report does not describe this model")
        # A caller cannot turn a loose comparison into strict parity by choosing a wider budget.
        passed = (report.get("passed") is True and report.get("allowed_max_raw_error") == 1
                  and isinstance(report.get("max_absolute_raw_error"), (float, int))
                  and report["max_absolute_raw_error"] <= 1
                  and report.get("tensorflow_kernel_resolver") == "BUILTIN_REF"
                  and report.get("invocations", 0) > 0)
        evidence.append({"file": stamp(path), "strict_passed": passed, "report": report})
    return evidence


def score(binary, model, manifests, thresholds, window, dest):
    dest.mkdir(mode=0o700)
    summaries = []
    for i, manifest in enumerate(manifests):
        cmd = [binary["path"], "-model", model["path"], "-manifest", manifest["path"],
               "-batch-out", str(dest / f"{i:02d}.clips.jsonl"), "-thresholds",
               ",".join(format(t, ".12g") for t in thresholds), "-window", str(window)]
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        (dest / f"{i:02d}.stdout.json").write_text(completed.stdout)
        (dest / f"{i:02d}.stderr.log").write_text(completed.stderr)
        if completed.returncode:
            raise RuntimeError(f"validator failed ({completed.returncode}); see {dest}/{i:02d}.stderr.log")
        summary = json.loads(completed.stdout)
        if summary.get("model_sha256") != model["sha256"] or summary.get("runtime") != RUNTIME:
            raise ValueError("unexpected validator model or runtime identity")
        if summary.get("sliding_window") != window:
            raise ValueError("validator window mismatch")
        if [v["threshold"] for v in summary["thresholds"]] != thresholds:
            raise ValueError("validator threshold grid mismatch")
        expected_pos = sum(r["label"] == "positive" for r in manifest["rows"])
        if summary["positive_clips"] != expected_pos or summary["clips"] != len(manifest["rows"]):
            raise ValueError("validator omitted manifest rows")
        expected_neg = len(manifest["rows"]) - expected_pos
        expected_seconds = sum(r["source_seconds"] for r in manifest["rows"] if r["label"] == "negative")
        if summary["negative_clips"] != expected_neg or not math.isclose(
                summary["negative_source_seconds"], expected_seconds, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("validator negative duration/count mismatch")
        summaries.append(summary)
    positives = sum(s["positive_clips"] for s in summaries)
    negatives = sum(s["negative_clips"] for s in summaries)
    negative_seconds = sum(s["negative_source_seconds"] for s in summaries)
    grid = []
    for i, threshold in enumerate(thresholds):
        hits = sum(s["thresholds"][i]["positive_clips_detected"] for s in summaries)
        events = sum(s["thresholds"][i]["negative_echo_timing_events"] for s in summaries)
        grid.append({"threshold": threshold, "positive_clips_detected": hits,
                     "positive_clip_recall": hits / positives if positives else 0,
                     "negative_clips_detected": sum(s["thresholds"][i]["negative_clips_detected"] for s in summaries),
                     "negative_echo_timing_events": events,
                     "negative_events_per_source_hour": events * 3600 / negative_seconds if negative_seconds else None})
    return {"positive_clips": positives, "negative_clips": negatives,
            "negative_source_seconds": negative_seconds, "thresholds": grid,
            "summaries": summaries}


def prepare_tts(a):
    work = a.work_dir.resolve()
    src = a.source_manifest.resolve() if a.source_manifest else work / "data-generation/manifest-full.jsonl"
    dst = a.output.resolve() if a.output else work / "evaluation/manifests" / f"tts-{a.split}.jsonl"
    rows, ids = [], set()
    for line in src.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["split"] != a.split:
            continue
        path = path_under(src.parent, r["path"])
        if r["source_id"] in ids or r["label"] not in (0, 1):
            raise ValueError("invalid or duplicate TTS row")
        if r.get("sha256") and sha(path) != r["sha256"]:
            raise ValueError(f"TTS source checksum changed: {r['source_id']}")
        ids.add(r["source_id"])
        rows.append({"id": r["source_id"], "label": "positive" if r["label"] else "negative",
                     "wav": os.path.relpath(path, dst.parent), "leading_ms": 3000, "trailing_ms": 1000})
    if not rows:
        raise ValueError("no TTS rows selected")
    dst.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with dst.open("x") as f:
        f.writelines(json.dumps(r) + "\n" for r in rows)
    save(dst.with_suffix(".selection.json"), {"source": stamp(src), "manifest": stamp(dst),
                                             "split": a.split, "rows": len(rows)})
    return {"manifest": str(dst), "rows": len(rows)}


def calibrate(a):
    directory = run_dir(a)
    thresholds = [float(t) for t in a.thresholds.split(",")]
    if not thresholds or any(not math.isfinite(t) or not 0 <= t <= 1 for t in thresholds) or sorted(set(thresholds)) != thresholds:
        raise ValueError("thresholds must be strictly increasing finite numbers in [0,1]")
    if not 0 < a.min_recall <= 1 or not 0 <= a.min_cutoff <= 1 or a.window < 1:
        raise ValueError("invalid calibration criteria")
    model = stamp(a.model)
    binary = stamp(a.validator or a.work_dir / "bin/validate")
    manifests = snapshots(a.manifest)
    parity = parity_evidence(a.parity_report, model)
    with exclusive(directory.parent):
        directory.mkdir(mode=0o700)
        result = score(binary, model, manifests, thresholds, a.window, directory / "validation")
        verify_file(model)
        verify_file(binary)
        verify_manifests(manifests)
        eligible = [r["threshold"] for r in result["thresholds"] if r["threshold"] >= a.min_cutoff
                    and r["positive_clip_recall"] >= a.min_recall and r["negative_echo_timing_events"] == 0
                    and result["positive_clips"] > 0 and result["negative_clips"] > 0]
        strict_passed = bool(parity) and all(p["strict_passed"] for p in parity)
        report = {"schema": SCHEMA, "created_utc": utc(), "run_id": a.run_id, "model": model,
                  "validator": binary, "runtime": RUNTIME, "window": a.window,
                  "manifests": manifests, "parity": parity,
                  "criteria": {"min_cutoff": a.min_cutoff, "min_recall": a.min_recall,
                               "max_negative_events": 0, "strict_raw_error_budget": 1},
                  "result": result, "eligible_cutoffs": eligible,
                  "strict_parity": "PASS" if strict_passed else "FAIL",
                  "passed": bool(eligible) and strict_passed,
                  "scope": "validation only; no test audio is evaluated"}
        save(directory / "calibration.json", report)
    return report


def freeze(a):
    directory = run_dir(a)
    with exclusive(directory.parent):
        cal = load_verified(directory / "calibration.json")
        if a.cutoff not in cal["eligible_cutoffs"]:
            raise ValueError("cutoff must pass the prespecified validation criteria")
        if cal["strict_parity"] != "PASS" and not a.evaluation_only:
            raise ValueError("strict parity FAILED; use --evaluation-only to measure held-out behavior with that failure retained")
        if not math.isfinite(a.min_test_negative_seconds) or a.min_test_negative_seconds < 0:
            raise ValueError("invalid minimum negative duration")
        for item in [cal["model"], cal["validator"]] + [p["file"] for p in cal["parity"]]:
            verify_file(item)
        verify_manifests(cal["manifests"])
        tests = snapshots(a.test_manifest)
        if identities(tests) & identities(cal["manifests"]):
            raise ValueError("validation/test audio overlap; split by source before augmentation")
        rows = [r for m in tests for r in m["rows"]]
        if not any(r["label"] == "positive" for r in rows) or not any(r["label"] == "negative" for r in rows):
            raise ValueError("test must include positive and negative audio")
        protocol = {"schema": SCHEMA, "created_utc": utc(), "run_id": a.run_id,
                    "model": cal["model"], "validator": cal["validator"], "runtime": RUNTIME,
                    "calibration": stamp(directory / "calibration.json"),
                    "cutoff": a.cutoff, "window": cal["window"], "test_manifests": tests,
                    "min_recall": cal["criteria"]["min_recall"],
                    "min_test_negative_seconds": a.min_test_negative_seconds,
                    "max_negative_events": 0, "strict_parity": cal["strict_parity"],
                    "evaluation_only": bool(a.evaluation_only or cal["strict_parity"] != "PASS"),
                    "timing": "20ms polling; 300ms hold; 800ms refractory; leading warmup excluded",
                    "claim": "offline evaluation; human trials and room soak require separate evidence"}
        digest = save(directory / "protocol.json", protocol)
    return {"protocol": str(directory / "protocol.json"), "protocol_sha256": digest,
            "model_sha256": protocol["model"]["sha256"], "cutoff": a.cutoff}


def gate(passed, **extra):
    return {"status": "PASS" if passed else "FAIL", **extra}


def final_test(a):
    directory = run_dir(a)
    with exclusive(directory.parent):
        protocol = load_verified(directory / "protocol.json")
        protocol_hash = sha(directory / "protocol.json")
        for item in (protocol["model"], protocol["validator"], protocol["calibration"]):
            verify_file(item)
        cal = load_verified(protocol["calibration"]["path"])
        verify_manifests(cal["manifests"])
        verify_manifests(protocol["test_manifests"])
        for p in cal["parity"]:
            verify_file(p["file"])
        if (directory / "test.json").exists():
            raise ValueError("test result already exists; never overwrite final evidence")
        history = directory.parent / "holdout-history"
        history.mkdir(exist_ok=True, mode=0o700)
        used = identities(protocol["test_manifests"])
        previous = []
        for path in history.glob("*.json"):
            old = load_verified(path)
            if used & set(old["pcm_sha256"]):
                previous.append(old["run_id"])
        if previous and not a.allow_reused_test:
            raise ValueError("test audio already consumed by " + ", ".join(previous) +
                             "; --allow-reused-test REASON permits explicitly non-clean analysis only")
        # Reserve the holdout BEFORE any inference. A crash is still a consumed test attempt.
        save(history / f"{a.run_id}.json", {"run_id": a.run_id, "started_utc": utc(),
             "protocol_sha256": protocol_hash, "model_sha256": protocol["model"]["sha256"],
             "cutoff": protocol["cutoff"], "pcm_sha256": sorted(used),
             "prior_runs": previous, "reuse_reason": a.allow_reused_test})
        gates = {name: {"status": "NOT_RUN"} for name in OFFLINE_GATES + ("human_trials", "room_soak")}
        gates["strict_parity"] = {"status": protocol["strict_parity"], "raw_error_budget": 1}
        gates["clean_holdout"] = gate(not previous, prior_runs=previous, reuse_reason=a.allow_reused_test)
        report = {"schema": SCHEMA, "created_utc": utc(), "run_id": a.run_id,
                  "model_sha256": protocol["model"]["sha256"], "cutoff": protocol["cutoff"],
                  "protocol_sha256": protocol_hash, "gates": gates,
                  "heldout_status": "reused_not_clean" if previous else "first_use_in_this_work_directory",
                  "all_gates_passed": False, "offline_gates_passed": False,
                  "limitations": ["No claim of unobserved test data outside this work directory.",
                                  "Offline synthetic and clean speech scores do not establish human or room performance.",
                                  "A checksum records evidence; it is not an independent signed attestation."]}
        try:
            result = score(protocol["validator"], protocol["model"], protocol["test_manifests"],
                           [protocol["cutoff"]], protocol["window"], directory / "heldout")
            verify_file(protocol["model"])
            verify_file(protocol["validator"])
            verify_manifests(protocol["test_manifests"])
            row = result["thresholds"][0]
            gates["runtime"] = gate(True, runtime=RUNTIME)
            gates["positive_recall"] = gate(row["positive_clip_recall"] >= protocol["min_recall"],
                observed=row["positive_clip_recall"], required=protocol["min_recall"])
            gates["zero_negative_events"] = gate(row["negative_echo_timing_events"] == 0,
                observed=row["negative_echo_timing_events"], allowed=0)
            gates["negative_duration"] = gate(result["negative_source_seconds"] >= protocol["min_test_negative_seconds"],
                observed_seconds=result["negative_source_seconds"], required_seconds=protocol["min_test_negative_seconds"])
            report["result"] = result
            report["offline_gates_passed"] = all(gates[k]["status"] == "PASS" for k in OFFLINE_GATES)
        except Exception as error:
            gates["runtime"] = gate(False, error=str(error))
            report["error"] = str(error)
        save(directory / "test.json", report)
    return report


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-tts", help="create val/test manifests without inference")
    prep.add_argument("--work-dir", required=True, type=Path)
    prep.add_argument("--split", required=True, choices=("val", "test"))
    prep.add_argument("--source-manifest", type=Path)
    prep.add_argument("--output", type=Path)
    for name in ("calibrate", "freeze", "test"):
        s = sub.add_parser(name)
        s.add_argument("--work-dir", required=True, type=Path)
        s.add_argument("--run-id", required=True)
        if name == "calibrate":
            s.add_argument("--model", required=True, type=Path)
            s.add_argument("--validator", type=Path, help="default WORK/bin/validate")
            s.add_argument("--manifest", required=True, action="append", type=Path)
            s.add_argument("--parity-report", required=True, action="append", type=Path)
            s.add_argument("--thresholds", default="0.85,0.90,0.92,0.95,0.97,0.99")
            s.add_argument("--min-cutoff", type=float, default=0.85)
            s.add_argument("--min-recall", type=float, default=0.98)
            s.add_argument("--window", type=int, default=5)
        elif name == "freeze":
            s.add_argument("--cutoff", required=True, type=float)
            s.add_argument("--test-manifest", required=True, action="append", type=Path)
            s.add_argument("--min-test-negative-seconds", type=float, default=3600)
            s.add_argument("--evaluation-only", action="store_true",
                           help="retain failed strict parity while measuring held-out behavior; never acceptance")
        else:
            s.add_argument("--allow-reused-test", metavar="REASON",
                           help="explicitly non-clean analysis; clean_holdout will FAIL")
    return p


def main():
    a = parser().parse_args()
    os.umask(0o077)
    try:
        functions = {"prepare-tts": prepare_tts, "calibrate": calibrate, "freeze": freeze, "test": final_test}
        report = functions[a.command](a)
        print(json.dumps(report, indent=2, allow_nan=False))
        if a.command == "calibrate" and not report["passed"]:
            return 2
        if a.command == "test" and not report["offline_gates_passed"]:
            return 2
        return 0
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"evaluation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
