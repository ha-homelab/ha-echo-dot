#!/usr/bin/env python3
"""Fetch, source/speaker-partition, and extract exact-Go LibriSpeech negatives."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

from common import (FeatureWriter, digest, download, extract_archive, fingerprint,
                    immutable_json, immutable_jsonl, inside, stage_lock, verify_file)
from recipe import LIBRISPEECH_PINS

FRAMES, BINS, SEED = 250, 40, 2026100203
GO_RUNTIME = "github.com/zserge/microwakeword@v0.0.0-20260330234603-bfaf3840114e"


def prepare_archives(root: Path, allow_download: bool):
    for source in LIBRISPEECH_PINS:
        filename = source["subset"] + ".tar.gz"
        path = inside(root, filename)
        if allow_download:
            download(source, path)
        else:
            if not path.exists():
                raise FileNotFoundError("Download LibriSpeech archives before index/features")
            verify_file(path, source)
        extract_archive(path, inside(root, "raw"), inside(root, source["subset"] + ".extracted.json"), source["sha256"])
    immutable_json(inside(root, "sources.json"), {
        "archives": LIBRISPEECH_PINS,
        "attribution": "LibriSpeech ASR corpus, Vassil Panayotov, Guoguo Chen, Daniel Povey and Sanjeev Khudanpur (2015); source audio from LibriVox.",
        "transformations": "16 kHz FLAC decoded losslessly to signed int16 PCM; non-overlapping random-offset 2.52-second windows at the default 250 frames; pinned EchoLocal Go frontend; float16 feature storage."})
    immutable_json(inside(root, "_ARCHIVES_READY.json"), {"archives": [{"subset": p["subset"], "sha256": p["sha256"]} for p in LIBRISPEECH_PINS]})


def read_subsets(root: Path) -> dict:
    import soundfile as sf
    subsets = {}
    for subset in ("dev-clean", "test-clean"):
        rows = []
        for path in sorted((root / "raw" / "LibriSpeech" / subset).rglob("*.flac")):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Raw source path escapes work directory")
            info = sf.info(path)
            if info.samplerate != 16000 or info.channels != 1:
                raise ValueError("Unexpected LibriSpeech format")
            parts = path.stem.split("-")
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                raise ValueError("Unexpected LibriSpeech source ID")
            rows.append({"path": str(path.relative_to(root)), "subset": subset,
                         "utterance_id": path.stem, "speaker_id": parts[0], "chapter_id": parts[1],
                         "samples": info.frames, "sample_rate": info.samplerate, "duration_seconds": info.duration})
        if not rows:
            raise ValueError("Missing extracted LibriSpeech subset")
        subsets[subset] = rows
    utterances = [r["utterance_id"] for rows in subsets.values() for r in rows]
    if len(set(utterances)) != len(utterances):
        raise ValueError("Duplicate LibriSpeech source IDs")
    return subsets


def plan_index(subsets: dict, frames=FRAMES, seed=SEED):
    """Deterministic pure plan, preserving the successful original RNG sequence."""
    import numpy as np
    samples = 480 + (frames - 1) * 160
    dev_speakers = sorted({r["speaker_id"] for r in subsets["dev-clean"]}, key=int)
    test_speakers = sorted({r["speaker_id"] for r in subsets["test-clean"]}, key=int)
    if set(dev_speakers) & set(test_speakers):
        raise ValueError("Source speaker overlap between dev-clean and test-clean")
    rng = np.random.default_rng(seed)
    shuffled = rng.permutation(dev_speakers).tolist()
    cut = int(len(shuffled) * 0.8)
    train_ids = set(shuffled[:cut])
    val_ids = set(shuffled[cut:])
    if not train_ids or not val_ids or train_ids & val_ids:
        raise ValueError("Invalid dev-clean speaker partition")
    rows_by_split = {
        "train": [r for r in subsets["dev-clean"] if r["speaker_id"] in train_ids],
        "val": [r for r in subsets["dev-clean"] if r["speaker_id"] in val_ids],
        "test": subsets["test-clean"],
    }
    test_order = np.random.default_rng(seed + 9).permutation(len(subsets["test-clean"]))
    hour, duration = [], 0.0
    for i in test_order:
        row = subsets["test-clean"][int(i)]
        hour.append(row)
        duration += row["duration_seconds"]
        if duration >= 3600:
            break
    if duration < 3600:
        raise ValueError("Less than one hour of held-out test audio")
    metadata = {"seed": seed, "method": "Whole dev-clean speakers: seeded 80/20 split; all test-clean held out.",
                "train_speakers": sorted(train_ids, key=int), "val_speakers": sorted(val_ids, key=int),
                "test_speakers": test_speakers, "speaker_intersection_count": 0,
                "test_raw_seconds": sum(r["duration_seconds"] for r in subsets["test-clean"]),
                "test_continuous_list_seconds": duration, "test_continuous_list_files": len(hour),
                "splits": {s: {"utterances": len(rs), "seconds": sum(r["duration_seconds"] for r in rs)} for s, rs in rows_by_split.items()}}
    all_jobs = []
    for split, rows in rows_by_split.items():
        jobs = []
        for row in rows:
            n = row["samples"] // samples
            if n < 1:
                continue
            utterance_seed = int(hashlib.sha256(f"{seed}:{row['utterance_id']}".encode()).hexdigest()[:16], 16)
            # Same-length disjoint windows with a deterministic random origin in
            # the unused margin. Even the 30 ms frontend windows do not overlap.
            slack = row["samples"] - n * samples
            offset = int(np.random.default_rng(utterance_seed).integers(0, slack + 1))
            for j in range(n):
                start = offset + j * samples
                jobs.append({**row, "split": split, "start_sample": start,
                             "end_sample": start + samples, "label": 0})
        maximum = {"train": 12000, "val": 1500, "test": 3000}[split]
        chosen = np.random.default_rng(seed + {"train": 1, "val": 2, "test": 3}[split]).permutation(len(jobs))[:maximum]
        selected = [jobs[int(i)] for i in chosen]
        for i, job in enumerate(selected):
            job["feature_index"] = i
        metadata["splits"][split].update(available_nonoverlap_windows=len(jobs), selected_windows=len(selected), cap=maximum)
        all_jobs += selected
    return all_jobs, metadata, hour


def build_index(root: Path, frames=FRAMES, seed=SEED):
    subsets = read_subsets(root)
    jobs, metadata, hour = plan_index(subsets, frames, seed)
    recipe = {"frames": frames, "bins": BINS, "seed": seed,
              "samples_per_window": 480 + (frames - 1) * 160,
              "archives": [{"subset": p["subset"], "sha256": p["sha256"]} for p in LIBRISPEECH_PINS],
              "numpy": importlib.metadata.version("numpy"), "soundfile": importlib.metadata.version("soundfile")}
    immutable_json(inside(root, "index_recipe.json"), recipe)
    immutable_jsonl(inside(root, "test_clean_raw.jsonl"), subsets["test-clean"], sort_keys=True)
    immutable_jsonl(inside(root, "test_clean_continuous_at_least_1h.jsonl"), hour, sort_keys=True)
    immutable_jsonl(inside(root, "windows.jsonl"), jobs, sort_keys=True)
    immutable_json(inside(root, "split_manifest.json"), metadata)
    print(json.dumps(metadata, indent=2))


def extract_job(job):
    import numpy as np
    import soundfile as sf
    binary, root, frames, row = job
    expected = 480 + (frames - 1) * 160
    audio, sr = sf.read(inside(Path(root), row["path"]), start=row["start_sample"], stop=row["end_sample"], dtype="int16")
    if sr != 16000 or audio.shape != (expected,):
        raise ValueError("LibriSpeech audio slice shape mismatch")
    result = subprocess.run([binary], input=audio.astype("<i2", copy=False).tobytes(),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=True)
    feature = np.frombuffer(result.stdout, dtype="<f4").reshape(-1, BINS)
    if feature.shape != (frames, BINS) or not np.isfinite(feature).all() or feature.min() < 0 or feature.max() > 26:
        raise ValueError("Go frontend output contract failed")
    return row["split"], row["feature_index"], feature.astype(np.float16)


def extract(work: Path, binary: Path, workers: int, frames=FRAMES, seed=SEED):
    root = inside(work, "librispeech")
    index_recipe = json.loads((root / "index_recipe.json").read_text())
    if index_recipe["frames"] != frames or index_recipe["seed"] != seed:
        raise ValueError("Requested feature settings differ from the index")
    binary = binary.resolve(strict=True)
    jobs = [json.loads(line) for line in (root / "windows.jsonl").read_text().splitlines()]
    recipe = {"index_recipe": index_recipe, "windows_sha256": digest(root / "windows.jsonl"),
              "binary_sha256": digest(binary), "go_runtime": GO_RUNTIME,
              "frontend_contract": "16k mono PCM16LE -> 40-bin float32LE; 30ms window /10ms hop; (q+128)*float32(26/255)",
              "fresh_frontend_state_per_window": True, "raw_windows_nonoverlapping": True,
              "numpy": importlib.metadata.version("numpy"), "soundfile": importlib.metadata.version("soundfile")}
    immutable_json(inside(root, "feature_recipe.json"), recipe)
    writers = {split: FeatureWriter(inside(work, f"features/librispeech_{split}.npy"),
               (sum(r["split"] == split for r in jobs), frames, BINS), recipe) for split in ("train", "val", "test")}
    pending = [r for r in jobs if r["feature_index"] >= writers[r["split"]].done]
    start = time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        for i, (split, offset, feature) in enumerate(pool.map(extract_job,
                ((str(binary), str(root), frames, r) for r in pending), chunksize=8), 1):
            writers[split].append(offset, feature)
            if i % 250 == 0:
                print(f"Go features {i}/{len(pending)}, {time.monotonic()-start:.1f}s", flush=True)
    outputs = [{"split": split, "path": f"features/librispeech_{split}.npy", **writer.finish()}
               for split, writer in writers.items()]
    provenance = {"recipe_sha256": fingerprint(recipe), "binary_sha256": recipe["binary_sha256"],
                  "go_runtime": GO_RUNTIME, "frames": frames, "outputs": outputs,
                  "note": "The one-hour test file is a fixed playlist of complete held-out utterances, not a continuous room recording."}
    immutable_json(inside(root, "feature_provenance.json"), provenance)
    print(json.dumps({"complete": True, "elapsed_seconds": time.monotonic() - start, "outputs": outputs}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("download", "index", "features", "all"))
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--binary", type=Path, help="Go raw-PCM extractor, default WORK/bin/gofeatures")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--frames", type=int, default=FRAMES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if not 1 <= args.workers <= 6 or args.frames < 1:
        parser.error("workers must be 1–6 and frames positive")
    work = args.work_dir.resolve()
    root = inside(work, "librispeech")
    with stage_lock(root, "librispeech"):
        if args.mode in ("download", "index", "all"):
            prepare_archives(root, allow_download=args.mode in ("download", "all"))
        if args.mode in ("index", "all"):
            build_index(root, args.frames, args.seed)
        if args.mode in ("features", "all"):
            extract(work, args.binary or inside(work, "bin/gofeatures"), args.workers, args.frames, args.seed)


if __name__ == "__main__":
    main()
