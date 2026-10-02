#!/usr/bin/env python3
"""Package, verify and explicitly stage an EchoLocal micro wake-word model.

Standard library only. This tool has no network, HA API, microphone, credential
discovery, service reload, or device selection code. Staging writes two files to
the explicitly supplied Home Assistant configuration directory.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile


SCHEMA_VERSION = 1
MODEL_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,95}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REQUIRED_GATES = (
    "runtime", "strict_parity", "positive_recall", "zero_negative_events",
    "negative_duration", "clean_holdout", "human_trials", "room_soak",
)


def fail(message: str) -> None:
    raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def valid_id(value: str, label: str = "Model ID") -> str:
    if not isinstance(value, str) or not MODEL_ID.fullmatch(value):
        fail(f"{label} must contain only lowercase ASCII letters, digits, '_' and '-', starting with a letter or digit.")
    return value


def probability(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 < value < 1:
        fail("Cutoff must be a finite number strictly between zero and one.")
    return float(value)


def same_cutoff(left: object, right: object) -> bool:
    return math.isclose(probability(left), probability(right), rel_tol=0, abs_tol=1e-9)


def json_object(data: bytes, label: str) -> dict:
    try:
        result = json.loads(data)
    except (ValueError, UnicodeDecodeError) as exc:
        fail(f"Invalid JSON in {label}: {exc}")
    if not isinstance(result, dict):
        fail(f"Expected a JSON object in {label}.")
    return result


def read_file(path: Path, maximum: int = 32 * 1024 * 1024) -> bytes:
    if path.is_symlink() or not path.is_file():
        fail(f"Expected a regular, non-symlinked file: {path}")
    if path.stat().st_size > maximum:
        fail(f"File is larger than the supported {maximum}-byte bound: {path.name}")
    return path.read_bytes()


def validate_model(model: bytes, sidecar: dict, model_id: str, cutoff: object) -> None:
    valid_id(model_id)
    if len(model) < 8 or model[4:8] != b"TFL3":
        fail("The model is not a TFLite FlatBuffer (missing TFL3 identifier).")
    if sidecar.get("type") != "micro" or sidecar.get("model") != f"{model_id}.tflite":
        fail("Expected type 'micro' and a model filename matching --model-id.")
    if not isinstance(sidecar.get("wake_word"), str) or not sidecar["wake_word"].strip():
        fail("Sidecar wake_word must contain the spoken phrase.")
    languages = sidecar.get("trained_languages")
    if not isinstance(languages, list) or not languages or not all(isinstance(item, str) and item.strip() for item in languages):
        fail("Sidecar trained_languages must be a non-empty string list.")
    if sidecar.get("version") != 2:
        fail("This packaging contract expects micro wake-word manifest version 2.")
    micro = sidecar.get("micro")
    if not isinstance(micro, dict):
        fail("Sidecar must declare its micro model parameters.")
    for field in ("sliding_window_size", "feature_step_size"):
        if type(micro.get(field)) is not int or micro[field] <= 0:
            fail(f"Sidecar micro.{field} must be a positive integer.")
    if not same_cutoff(micro.get("probability_cutoff"), cutoff):
        fail("Package cutoff differs from its delivered model sidecar.")


def acceptance(reports: list[tuple[str, dict]], model_sha: str, cutoff: float) -> tuple[list[str], dict]:
    """Conservative release policy; missing evidence never becomes an implied pass."""
    reasons: list[str] = []
    gate_reports = []
    for name, report in reports:
        reported_sha = report.get("model_sha256")
        if reported_sha is not None and reported_sha != model_sha:
            fail(f"Evaluation {name} refers to a different model SHA256.")
        if "gates" not in report:
            continue
        if reported_sha != model_sha:
            fail(f"Gate report {name} must identify the exact model_sha256.")
        if not same_cutoff(report.get("cutoff"), cutoff):
            fail(f"Gate report {name} was evaluated at a different cutoff.")
        gates = report["gates"]
        if not isinstance(gates, dict):
            fail(f"Gate report {name} has an invalid gates object.")
        statuses = {}
        for gate in list(REQUIRED_GATES) + sorted(set(gates) - set(REQUIRED_GATES)):
            value = gates.get(gate)
            status = value.get("status") if isinstance(value, dict) else "NOT_RUN"
            if status not in {"PASS", "FAIL", "NOT_RUN"}:
                fail(f"Gate report {name} has an invalid status for {gate}.")
            statuses[gate] = status
            if status != "PASS":
                reasons.append(f"{name}: {gate}={status}")
        if report.get("all_gates_passed") is not True:
            reasons.append(f"{name}: all_gates_passed is not true")
        protocol_sha = report.get("protocol_sha256")
        if not isinstance(protocol_sha, str) or not SHA256.fullmatch(protocol_sha):
            reasons.append(f"{name}: missing frozen protocol SHA256")
        gate_reports.append({"report": name, "gates": statuses})
    if not gate_reports:
        reasons.append("No matching-model evaluation report provides every required release gate.")
    return reasons, {"required_gates": list(REQUIRED_GATES), "reports": gate_reports}


def require_protocol_evidence(
    reports: list[tuple[str, bytes]], decoded: list[tuple[str, dict]],
    model_sha: str, cutoff: float, window: int,
) -> list[str]:
    included = {digest(data): (name, json_object(data, name)) for name, data in reports}
    reasons = []
    for name, report in decoded:
        if "gates" not in report:
            continue
        protocol_hash = report.get("protocol_sha256")
        if protocol_hash not in included:
            reasons.append(f"{name}: frozen protocol bytes are not included among --evaluation files")
            continue
        protocol_name, protocol = included[protocol_hash]
        model = protocol.get("model")
        if not isinstance(model, dict) or model.get("sha256") != model_sha:
            fail(f"Frozen protocol {protocol_name} refers to a different or missing model SHA256.")
        if not same_cutoff(protocol.get("cutoff"), cutoff) or type(protocol.get("window")) is not int or protocol["window"] != window:
            fail(f"Frozen protocol {protocol_name} does not match the sidecar cutoff and sliding window.")
        validator = protocol.get("validator")
        if not isinstance(validator, dict) or not isinstance(validator.get("sha256"), str) or not SHA256.fullmatch(validator["sha256"]):
            reasons.append(f"{protocol_name}: missing exact validator SHA256")
        if protocol.get("strict_parity") != "PASS":
            reasons.append(f"{protocol_name}: frozen strict_parity is not PASS")
    return reasons


def payload_entry(path: str, data: bytes) -> dict:
    return {"path": path, "size": len(data), "sha256": digest(data)}


def package(args: argparse.Namespace) -> dict:
    model_id = valid_id(args.model_id)
    candidate = valid_id(args.candidate, "Candidate")
    cutoff = probability(args.cutoff)
    work = args.work_dir.expanduser().resolve()
    source = work / "models" / candidate
    if source.is_symlink():
        fail("Refusing a symlinked model candidate directory.")
    model = read_file(source / f"{model_id}.tflite")
    source_sidecar_bytes = read_file(source / f"{model_id}.json")
    sidecar = json_object(source_sidecar_bytes, "source model sidecar")
    micro = sidecar.get("micro")
    source_cutoff = probability(micro.get("probability_cutoff") if isinstance(micro, dict) else None)
    validate_model(model, sidecar, model_id, source_cutoff)
    sidecar_bytes = source_sidecar_bytes
    adjustment = None
    if not same_cutoff(source_cutoff, cutoff):
        sidecar["micro"]["probability_cutoff"] = cutoff
        sidecar_bytes = (json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        adjustment = {"field": "micro.probability_cutoff", "source": source_cutoff, "packaged": cutoff, "reason": "Explicit --cutoff; acceptance requires evaluation at this exact operating point."}
    validate_model(model, sidecar, model_id, cutoff)
    source_sidecar_name = f"source/{model_id}.json"
    files = {f"{model_id}.tflite": model, f"{model_id}.json": sidecar_bytes, source_sidecar_name: source_sidecar_bytes}
    raw_reports = []
    decoded_reports = []
    for index, path in enumerate(args.evaluation):
        path = path.expanduser().absolute()
        data = read_file(path)
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", path.name)
        relative = f"reports/{index:03d}-{name}"
        raw_reports.append((relative, data))
        decoded_reports.append((relative, json_object(data, path.name)))
        files[relative] = data
    reasons, evidence = acceptance(decoded_reports, digest(model), cutoff)
    reasons.extend(require_protocol_evidence(raw_reports, decoded_reports, digest(model), cutoff, sidecar["micro"]["sliding_window_size"]))
    if reasons and not args.experimental:
        fail("Release gates are failed or incomplete. Use --experimental to preserve this evidence and package a trial candidate:\n  " + "\n  ".join(reasons))
    status = "experimental" if args.experimental else "accepted"
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "candidate": candidate,
        "status": status,
        "experimental_reasons": reasons,
        "wake_word": sidecar["wake_word"],
        "trained_languages": sidecar["trained_languages"],
        "recommended_cutoff": cutoff,
        "runtime_cutoff_note": "EchoLocal 0.0.8 requires setting the selected slot's sensitivity in Home Assistant; copying probability_cutoff does not set it.",
        "model": payload_entry(f"{model_id}.tflite", model),
        "sidecar": f"{model_id}.json",
        "source_sidecar": {**payload_entry(source_sidecar_name, source_sidecar_bytes), "cutoff": source_cutoff},
        "sidecar_adjustment": adjustment,
        "evaluation": evidence,
        "files": [payload_entry(name, data) for name, data in sorted(files.items())],
        "integrity_note": "SHA256 records content integrity, not authenticity or permission to redistribute.",
    }
    delivery = work / "delivery"
    if delivery.is_symlink():
        fail("Refusing a symlinked delivery directory.")
    delivery.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = delivery / model_id
    if target.exists() or target.is_symlink():
        fail("Package destination already exists. Verify it or use a new immutable model ID; packaging never overwrites.")
    temporary = Path(tempfile.mkdtemp(prefix=".package-", dir=delivery))
    try:
        for name, data in files.items():
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open("xb") as stream:
                os.chmod(path, 0o600)
                stream.write(data)
        manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (temporary / "manifest.json").write_bytes(manifest_bytes)
        (temporary / "manifest.sha256").write_text(f"{digest(manifest_bytes)}  manifest.json\n", encoding="ascii")
        os.chmod(temporary / "manifest.json", 0o600)
        os.chmod(temporary / "manifest.sha256", 0o600)
        verify_package(temporary)
        # rename is atomic on this filesystem; refuse even an empty existing dir.
        if target.exists() or target.is_symlink():
            fail("Package destination appeared during packaging; refusing to replace it.")
        temporary.rename(target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {"status": "packaged", "package": str(target), "release_status": status, "model_sha256": digest(model), "recommended_cutoff": cutoff, "experimental_reasons": reasons}


def safe_relative(name: object) -> str:
    if not isinstance(name, str) or not name or "\\" in name:
        fail("Invalid package payload path.")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"..", "."} for part in path.parts) or str(path) != name:
        fail("Package paths must be normalized relative paths without traversal.")
    return name


def verify_package(root: Path) -> tuple[dict, dict[str, bytes]]:
    if root.is_symlink() or not root.is_dir():
        fail("Package must be a non-symlinked directory.")
    manifest_bytes = read_file(root / "manifest.json")
    checksum = read_file(root / "manifest.sha256", 256).decode("ascii").strip()
    if checksum != f"{digest(manifest_bytes)}  manifest.json":
        fail("Package manifest checksum mismatch.")
    manifest = json_object(manifest_bytes, "package manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        fail("Unsupported delivery manifest schema.")
    model_id = valid_id(manifest.get("model_id"))
    if manifest.get("status") not in {"accepted", "experimental"}:
        fail("Invalid package release status.")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        fail("Package manifest files must be a list.")
    files = {}
    for entry in entries:
        if not isinstance(entry, dict):
            fail("Invalid package file entry.")
        name = safe_relative(entry.get("path"))
        if name in files or name in {"manifest.json", "manifest.sha256"}:
            fail("Duplicate or reserved package payload path.")
        path = root / name
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
            fail("Refusing symlinked package subdirectories.")
        data = read_file(path)
        if type(entry.get("size")) is not int or entry["size"] != len(data) or entry.get("sha256") != digest(data):
            fail(f"Package payload checksum or size mismatch: {name}")
        files[name] = data
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            fail("Package contains a symlink.")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(files) | {"manifest.json", "manifest.sha256"}:
        fail("Package contains unlisted files or is missing listed files.")
    model_name, sidecar_name = f"{model_id}.tflite", f"{model_id}.json"
    if model_name not in files or sidecar_name not in files or manifest.get("sidecar") != sidecar_name:
        fail("Package is missing its canonical model or sidecar.")
    sidecar = json_object(files[sidecar_name], "packaged model sidecar")
    cutoff = probability(manifest.get("recommended_cutoff"))
    validate_model(files[model_name], sidecar, model_id, cutoff)
    source_name = f"source/{model_id}.json"
    if source_name not in files:
        fail("Package is missing the unmodified source sidecar evidence.")
    source_sidecar = json_object(files[source_name], "source model sidecar evidence")
    micro = source_sidecar.get("micro")
    source_cutoff = probability(micro.get("probability_cutoff") if isinstance(micro, dict) else None)
    validate_model(files[model_name], source_sidecar, model_id, source_cutoff)
    if manifest.get("source_sidecar") != {**payload_entry(source_name, files[source_name]), "cutoff": source_cutoff}:
        fail("Source sidecar provenance disagrees with its exact bytes.")
    expected_adjustment = None
    if not same_cutoff(source_cutoff, cutoff):
        source_sidecar["micro"]["probability_cutoff"] = cutoff
        expected_adjustment = {"field": "micro.probability_cutoff", "source": source_cutoff, "packaged": cutoff, "reason": "Explicit --cutoff; acceptance requires evaluation at this exact operating point."}
    if source_sidecar != sidecar or manifest.get("sidecar_adjustment") != expected_adjustment:
        fail("Delivered sidecar differs from source evidence beyond the declared cutoff adjustment.")
    if manifest.get("model") != payload_entry(model_name, files[model_name]):
        fail("Model identity disagrees with the package payload.")
    if manifest.get("wake_word") != sidecar["wake_word"] or manifest.get("trained_languages") != sidecar["trained_languages"]:
        fail("Model phrase or language disagrees with the package manifest.")
    raw_reports = [(name, data) for name, data in files.items() if name.startswith("reports/")]
    decoded_reports = [(name, json_object(data, name)) for name, data in raw_reports]
    reasons, evidence = acceptance(decoded_reports, digest(files[model_name]), cutoff)
    reasons.extend(require_protocol_evidence(raw_reports, decoded_reports, digest(files[model_name]), cutoff, sidecar["micro"]["sliding_window_size"]))
    if manifest.get("evaluation") != evidence or manifest.get("experimental_reasons") != reasons:
        fail("Release gate summary disagrees with the included evaluation reports.")
    if manifest["status"] == "accepted" and reasons:
        fail("Package claims acceptance despite failed or incomplete release gates.")
    return manifest, files


def stage(args: argparse.Namespace) -> dict:
    root = args.package.expanduser().absolute()
    manifest, files = verify_package(root)
    if manifest["status"] == "experimental" and not args.experimental:
        fail("This package is experimental; staging requires the explicit --experimental flag.")
    config = args.ha_config_dir.expanduser().absolute()
    if config.is_symlink() or not config.is_dir():
        fail("--ha-config-dir must be an existing, non-symlinked Home Assistant configuration directory.")
    destination = config / "custom_wake_words"
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        fail("Refusing a symlinked or non-directory custom_wake_words destination.")
    names = (manifest["model"]["path"], manifest["sidecar"])
    existing = []
    for name in names:
        target = destination / name
        if target.is_symlink():
            fail("Refusing a symlinked staged model or sidecar.")
        if target.exists():
            if read_file(target) != files[name]:
                fail(f"A different {name} already exists; use a new model ID instead of replacing it.")
            existing.append(name)
    if len(existing) == len(names):
        return {"status": "already_staged", "destination": str(destination), "release_status": manifest["status"], "model_sha256": manifest["model"]["sha256"]}
    destination.mkdir(exist_ok=True, mode=0o755)
    temporary = Path(tempfile.mkdtemp(prefix=".stage-", dir=config))
    created = []
    try:
        for name in names:
            if name in existing:
                continue
            source = temporary / name
            source.write_bytes(files[name])
            os.chmod(source, 0o644)
            # Hard link gives exclusive no-clobber creation with a complete payload.
            # Both paths are in the same HA config filesystem.
            target = destination / name
            os.link(source, target)
            created.append(target)
        for name in names:
            if read_file(destination / name) != files[name]:
                fail("Post-stage byte verification failed.")
    except BaseException:
        for target in created:
            target.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(temporary)
    return {
        "status": "staged",
        "destination": str(destination),
        "release_status": manifest["status"],
        "model_sha256": manifest["model"]["sha256"],
        "files": list(names),
        "recommended_cutoff": manifest["recommended_cutoff"],
        "next_step": "Coordinate Home Assistant discovery/restart if required, then explicitly select the second wake-word slot and set its sensitivity. No HA or device settings were changed by this command.",
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    command = commands.add_parser("package", help="Create an immutable package with the model, manifest and evaluation evidence.")
    command.add_argument("--work-dir", type=Path, required=True)
    command.add_argument("--candidate", required=True, help="Directory under WORK/models, for example candidate-1.")
    command.add_argument("--model-id", required=True, help="Basename shared by the candidate .tflite and .json files.")
    command.add_argument("--cutoff", type=float, required=True, help="Selected operating point; must match the frozen protocol and gate report. Updates only the packaged sidecar and preserves the source.")
    command.add_argument("--evaluation", type=Path, action="append", default=[], help="JSON report or frozen protocol to preserve byte-for-byte; may be repeated.")
    command.add_argument("--experimental", action="store_true", help="Explicitly package a trial candidate despite incomplete or failed acceptance gates.")
    for name, help_text in (("verify", "Verify checksums, model metadata and reported release gates."), ("stage", "Copy only the verified model and sidecar to an explicit HA configuration directory.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--package", type=Path, required=True)
        if name == "stage":
            command.add_argument("--ha-config-dir", type=Path, required=True, help="Existing local or mounted HA configuration directory; never auto-discovered.")
            command.add_argument("--experimental", action="store_true", help="Explicitly permit staging an experimental package.")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "package":
            summary = package(args)
        elif args.command == "stage":
            summary = stage(args)
        else:
            manifest, _ = verify_package(args.package.expanduser().absolute())
            summary = {"status": "verified", "release_status": manifest["status"], "model_sha256": manifest["model"]["sha256"], "recommended_cutoff": manifest["recommended_cutoff"], "experimental_reasons": manifest["experimental_reasons"]}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
