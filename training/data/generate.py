#!/usr/bin/env python3
"""Bounded native Piper data generation. Use --work-dir and --stage.

The manifest partitions original WAVs before feature extraction/augmentation.
One process owns one cached voice, with two ONNX CPU threads. Each process
replays its deterministic inference sequence on reruns, including existing WAVs.
No trimming, duration cap, synthetic silence padding, or waveform augmentation.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import random
import sys
import time
import urllib.request
import wave

from common import (digest as sha256, download, immutable_bytes, immutable_json,
                    immutable_jsonl, inside, stage_lock)
from recipe import (REVISION, REPO, MASTER_SEED, VOICES, POSITIVES, NEGATIVES,
                    VOICE_PINS, SYNTHESIS_PACKAGES)


def download_voice(root: Path, name: str) -> dict:
    pin = VOICE_PINS[name]
    files = []
    for item in pin["files"]:
        dest = inside(root, item["path"])
        download(item, dest)
        files.append(item)
    folder = inside(root, "voices/" + name)
    record = {"voice": name, "repository": REPO, "revision": REVISION,
              "license_reference": pin["license_reference"],
              "model_card": (folder / "MODEL_CARD").read_text(), "files": files}
    immutable_json(folder / "provenance.json", record)
    return record


def make_jobs() -> dict[str, list[dict]]:
    by_voice = {v: {"positive": [], "negative": []} for v in VOICES}
    for label, count, phrases in (("positive", 4000, POSITIVES), ("negative", 2500, NEGATIVES)):
        indices = list(range(count))
        random.Random(f"{MASTER_SEED}:{label}:split").shuffle(indices)
        splits = {i: ("train" if n < count * .8 else "val" if n < count * .9 else "test")
                  for n, i in enumerate(indices)}
        for i in range(count):
            voice = VOICES[i % len(VOICES)]
            local_index = i // len(VOICES)
            source_id = f"pm-v1-{label[:3]}-{voice}-{local_index:04d}"
            seed = int.from_bytes(hashlib.sha256(f"{MASTER_SEED}:{source_id}".encode()).digest()[:8], "big")
            rng = random.Random(seed)
            # Each voice covers every phrase; parameters vary continuously.
            phrase = phrases[local_index % len(phrases)]
            job = {"source_id": source_id, "class": label, "label": int(label == "positive"), "split": splits[i],
                   "voice": voice, "text": phrase, "parameter_seed": seed,
                   "length_scale": round(rng.uniform(.82, 1.16), 5),
                   "noise_scale": round(rng.uniform(.5, .8), 5),
                   "noise_w_scale": round(rng.uniform(.6, .95), 5),
                   "volume": round(rng.uniform(.72, .92), 5)}
            by_voice[voice][label].append(job)
    ordered = {}
    for voice, labels in by_voice.items():
        jobs = []
        for i in range(max(len(x) for x in labels.values())):
            for label in ("positive", "negative"):
                if i < len(labels[label]):
                    jobs.append(labels[label][i])
        ordered[voice] = jobs
    return ordered


def run_voice(root: str, voice_name: str, jobs: list[dict], stage: str) -> dict:
    ROOT = Path(root)
    # Set before numerical imports in each spawned process.
    os.environ.update(OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="2")
    import numpy as np
    import onnxruntime as ort
    from scipy.signal import resample_poly
    from piper import PiperVoice, SynthesisConfig
    from piper.config import PiperConfig

    start = time.monotonic()
    voice_seed = MASTER_SEED + VOICES.index(voice_name) * 10007
    random.seed(voice_seed)
    np.random.seed(voice_seed)
    ort.set_seed(voice_seed)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    options.add_session_config_entry("session.inter_op.allow_spinning", "0")
    stem = ROOT / "voices" / voice_name / f"ru_RU-{voice_name}-medium.onnx"
    config = PiperConfig.from_dict(json.loads(Path(str(stem) + ".json").read_text()))
    session = ort.InferenceSession(str(stem), sess_options=options, providers=["CPUExecutionProvider"])
    voice = PiperVoice(session=session, config=config)
    transcript_cache = {}
    entries = []
    for ordinal, job in enumerate(jobs):
        text = job["text"]
        if text not in transcript_cache:
            transcript_cache[text] = voice.phonemize(text)
        phonemes = transcript_cache[text]
        settings = SynthesisConfig(length_scale=job["length_scale"], noise_scale=job["noise_scale"],
                                   noise_w_scale=job["noise_w_scale"], normalize_audio=True,
                                   volume=job["volume"])
        chunks = []
        for sentence in phonemes:
            raw = voice.phoneme_ids_to_audio(voice.phonemes_to_ids(sentence), settings)
            peak = float(np.max(np.abs(raw))) if len(raw) else 0
            if peak < 1e-7:
                raise RuntimeError(f"Silent synthesis: {job['source_id']}")
            chunks.append(raw / peak * job["volume"])
        raw = np.concatenate(chunks)
        gcd = math.gcd(config.sample_rate, 16000)
        samples = resample_poly(raw, 16000 // gcd, config.sample_rate // gcd)
        samples = np.rint(np.clip(samples, -.999, .999) * 32767).astype("<i2")
        duration = len(samples) / 16000
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)) / 32768)
        if not (.12 < duration < 15) or rms < .001:
            raise RuntimeError(f"Invalid waveform {job['source_id']}: duration={duration}, rms={rms}")
        path = inside(ROOT, Path("wav") / job["split"] / job["class"] / (job["source_id"] + ".wav"))
        path.parent.mkdir(parents=True, exist_ok=True)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            wav.writeframes(samples.tobytes())
        encoded = buffer.getvalue()
        checksum = hashlib.sha256(encoded).hexdigest()
        # Replaying synthesis keeps ORT's per-session random sequence stable.
        if path.exists():
            if sha256(path) != checksum:
                raise RuntimeError(f"Reproducibility mismatch; refusing replacement: {path}")
        else:
            immutable_bytes(path, encoded)
        entry = {**job, "path": str(path.relative_to(ROOT)), "sha256": checksum,
                 "sample_rate": 16000, "channels": 1, "sample_width_bytes": 2,
                 "samples": len(samples), "duration": duration, "duration_seconds": duration, "rms": rms,
                 "peak": int(np.max(np.abs(samples.astype(np.int32)))),
                 "native_sample_rate": config.sample_rate, "voice_rng_seed": voice_seed,
                 "voice_sequence_index": ordinal,
                 "phonemes": ["".join(x) for x in phonemes],
                 "trimmed": False, "padded": False, "augmented": False}
        entries.append(entry)
        if (ordinal + 1) % 100 == 0:
            print(f"{voice_name}: {ordinal + 1}/{len(jobs)}, {(time.monotonic()-start):.1f}s", flush=True)
    manifest = ROOT / f"manifest-{stage}-{voice_name}.jsonl"
    immutable_jsonl(manifest, entries)
    return {"voice": voice_name, "count": len(entries), "seconds": time.monotonic() - start,
            "manifest": manifest.name}


def write_preview(root: Path, entries: list[dict]) -> None:
    """Four complete neutral examples, separated for audition only."""
    buffer, segments, start = io.BytesIO(), [], 0.0
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        for voice in VOICES:
            row = next(x for x in entries if x["voice"] == voice and x["label"] == 1 and x["text"] == POSITIVES[0])
            with wave.open(str(inside(root, row["path"])), "rb") as source:
                output.writeframes(source.readframes(source.getnframes()))
            segments.append({"voice": voice, "start_seconds": start, "duration": row["duration"], "source_path": row["path"]})
            output.writeframes(b"\0" * 16000 * 2)
            start += row["duration"] + 1
    immutable_bytes(inside(root, "preview-smoke.wav"), buffer.getvalue())
    immutable_json(inside(root, "preview-smoke.json"), {
        "purpose": "Audition only; excluded from training manifests. Complete clips, one second separator silence.",
        "segments": segments})


def run(args):
    ROOT = inside(args.work_dir.resolve(), "data-generation")
    start = time.monotonic()
    if args.stage != "download":
        actual = {p: importlib.metadata.version(p) for p in SYNTHESIS_PACKAGES}
        if actual != SYNTHESIS_PACKAGES:
            raise RuntimeError(f"Pinned synthesis packages required: {SYNTHESIS_PACKAGES}; installed: {actual}")
        final_manifest = ROOT / f"manifest-{args.stage}.jsonl"
        complete = (ROOT / ("_SUCCESS.json" if args.stage == "full" else "summary-smoke.json"))
        if complete.exists() and final_manifest.exists():
            from verify import verify_dataset
            print(json.dumps(verify_dataset(args.work_dir.resolve(), args.stage), indent=2))
            return
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        voices = list(pool.map(lambda v: download_voice(ROOT, v), VOICES))
    immutable_json(ROOT / "voices-provenance.json", voices)
    if args.stage == "download":
        print(json.dumps({"download_seconds": time.monotonic() - start, "voices": len(voices)}))
        return
    recipe = {"version": "pm-v1", "master_seed": MASTER_SEED, "voice_repository_revision": REVISION,
              "voices": VOICES, "positives": POSITIVES, "negatives": NEGATIVES,
              "raw_positive_count": 4000, "raw_negative_count": 2500, "split": [.8, .1, .1],
              "workers": 4, "ort_intra_threads_per_worker": 2, "ort_inter_threads_per_worker": 1,
              "randomness": "Deterministic parameter/source splits and per-voice ORT seed+inference order; reruns replay preceding inference and verify existing WAV hashes.",
              "audio_processing": "Resample complete native waveform to 16k mono PCM16; no cutting, padding or offline augmentation.",
              "split_limitations": "Source-disjoint synthetic splits share TTS voices and phrase vocabulary; they do not establish real-speaker generalization.",
              "packages": actual}
    immutable_json(ROOT / "recipe.json", recipe)
    jobs = make_jobs()
    if args.stage == "smoke":
        jobs = {v: tasks[:32] for v, tasks in jobs.items()}
    import multiprocessing
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context("spawn")) as pool:
        futures = [pool.submit(run_voice, str(ROOT), voice, jobs[voice], args.stage) for voice in VOICES]
        summaries = [future.result() for future in futures]
    entries = []
    for summary in summaries:
        entries.extend(json.loads(line) for line in (ROOT / summary["manifest"]).read_text().splitlines())
    entries.sort(key=lambda x: x["source_id"])
    manifest_path = ROOT / f"manifest-{args.stage}.jsonl"
    immutable_jsonl(manifest_path, entries)
    if args.stage == "smoke":
        write_preview(ROOT, entries)
    summary = {"stage": args.stage, "wall_seconds": time.monotonic() - start,
               "workers": summaries, "counts": {}, "duration_seconds": {},
               "manifest": manifest_path.name, "manifest_sha256": sha256(manifest_path)}
    import numpy as np
    for label in ("positive", "negative"):
        selected = [x for x in entries if x["class"] == label]
        lengths = np.array([x["duration_seconds"] for x in selected])
        summary["counts"][label] = {split: sum(x["split"] == split for x in selected) for split in ("train", "val", "test")}
        summary["duration_seconds"][label] = {k: float(v) for k, v in zip(("min", "p05", "median", "p95", "max"), np.quantile(lengths, [0, .05, .5, .95, 1]))}
        summary["duration_seconds"][label]["over_1_5_seconds"] = int(sum(lengths > 1.5))
        summary["duration_seconds"][label]["over_2_04_seconds"] = int(sum(lengths > 2.04))
    if len({x["source_id"] for x in entries}) != len(entries):
        raise RuntimeError("Duplicate source IDs")
    if len({x["sha256"] for x in entries}) != len(entries):
        raise RuntimeError("Duplicate waveforms; investigate before training")
    summary_path = ROOT / f"summary-{args.stage}.json"
    if summary_path.exists():
        existing = json.loads(summary_path.read_text())
        keys = ("stage", "counts", "duration_seconds", "manifest", "manifest_sha256")
        if any(existing.get(k) != summary[k] for k in keys):
            raise ValueError("Existing summary differs from this dataset")
        summary = existing  # Preserve the original successful run's timing.
    immutable_json(summary_path, summary)
    if args.stage == "full":
        immutable_json(ROOT / "_SUCCESS.json", {"manifest": manifest_path.name, "sha256": sha256(manifest_path), "count": len(entries)})
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Reproduce the fixed pm-v1 Russian Piper dataset in an explicit work directory.")
    parser.add_argument("--work-dir", type=Path, required=True, help="All generated data goes under WORK/data-generation")
    parser.add_argument("--stage", choices=("download", "smoke", "full"), required=True)
    args = parser.parse_args()
    root = inside(args.work_dir.resolve(), "data-generation")
    with stage_lock(root, "synthesis"):
        run(args)


if __name__ == "__main__":
    main()
