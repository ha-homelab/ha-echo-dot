#!/usr/bin/env python3
"""Fetch pinned precomputed negatives and reproduce the original window recipe.

These TensorFlow microfrontend archives are auxiliary negatives, not exact Go
frontend features. Corpus/source partitions stay separate; see README.md.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import importlib.metadata
import json
from pathlib import Path
import time

from common import (FeatureWriter, digest, download, extract_archive, fingerprint,
                    immutable_json, immutable_jsonl, inside, stage_lock)
from recipe import BACKGROUND_PINS

REVISION = "0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1"
FRAMES, BINS, SEED = 250, 40, 20261001


def fetch_one(root: Path, pin: dict) -> dict:
    archive = inside(root, "downloads/" + pin["file"])
    download(pin, archive)
    name = pin["file"].removesuffix(".zip")
    destination = inside(root, name)
    extract_archive(archive, destination, inside(root, name + ".extracted.json"), pin["sha256"])
    directories = sorted(str(p.relative_to(root)) for p in destination.rglob("*_mmap") if (p / "data.ninja").is_file())
    print(f"Verified/extracted {pin['file']}: {pin['bytes']} bytes", flush=True)
    return {**pin, "mmap_dirs": directories,
            "license_reference": f"https://huggingface.co/datasets/kahrendt/microwakeword/blob/{REVISION}/README.md"}


def fetch(root: Path, workers: int):
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        records = list(pool.map(lambda pin: fetch_one(root, pin), BACKGROUND_PINS))
    immutable_json(inside(root, "sources.json"), records)


def plan_background(root: Path, frames=FRAMES, seed=SEED) -> list[dict]:
    """Pure read-only plan; preserve original RNG calls and sorted directory order."""
    import numpy as np
    from mmap_ninja.ragged import RaggedMmap
    rng = np.random.default_rng(seed)
    directories = sorted(p for p in root.rglob("*_mmap") if (p / "data.ninja").is_file())
    if not directories:
        raise ValueError("No extracted background mmap directories")
    rows = []
    for directory in directories:
        rel = str(directory.relative_to(root))
        if rel.startswith("dinner_party_eval/"):
            split, cap = "test", 2000
        elif rel.startswith("dinner_party/"):
            split, cap = "val", 1500
        elif "/training/" in rel:
            split, cap = "train", 6000
        else:
            continue
        data = RaggedMmap(str(directory))
        indices = rng.permutation(len(data))[:min(len(data), cap)]
        for item in indices:
            feat = np.asarray(data[int(item)])
            if feat.ndim != 2 or feat.shape[1] != BINS:
                raise ValueError(f"Unexpected feature shape in {rel}: {feat.shape}")
            if len(feat) < frames:
                continue
            offsets = (np.linspace(0, len(feat) - frames, min(250, len(feat) // frames), dtype=int)
                       if split == "test" else [int(rng.integers(0, len(feat) - frames + 1))])
            for offset in offsets:
                rows.append({"split": split, "dataset": rel, "item": int(item),
                             "offset": int(offset), "raw_dtype": str(feat.dtype)})
    if any(not any(r["split"] == s for r in rows) for s in ("train", "val", "test")):
        raise ValueError("Background plan has an empty partition")
    return rows


def prepare_features(work: Path, frames=FRAMES, seed=SEED):
    import numpy as np
    from mmap_ninja.ragged import RaggedMmap
    root = inside(work, "background")
    sources = json.loads((root / "sources.json").read_text())
    expected = {p["file"]: p for p in BACKGROUND_PINS}
    if len(sources) != len(expected):
        raise ValueError("Incomplete source provenance; finish background download first")
    for source in sources:
        pin = expected.get(source["file"])
        if pin is None or source["sha256"] != pin["sha256"] or source["revision"] != REVISION:
            raise ValueError("Background provenance differs from pinned sources")
        marker = root / (source["file"].removesuffix(".zip") + ".extracted.json")
        if not marker.exists():
            raise ValueError("No verified extraction marker; run background download")
        extraction = json.loads(marker.read_text())
        if extraction["archive_sha256"] != pin["sha256"]:
            raise ValueError("Extraction marker does not match pinned archive")
        # The extraction manifest pins the complete file set. Verify before using it.
        from common import verify_file
        dest = root / source["file"].removesuffix(".zip")
        for item in extraction["files"]:
            verify_file(inside(dest, item["path"]), item)
    rows = plan_background(root, frames, seed)
    plan_path = inside(work, "features/background_provenance.jsonl")
    immutable_jsonl(plan_path, rows)
    recipe = {"version": 1, "revision": REVISION, "frames": frames, "bins": BINS, "seed": seed,
              "plan_sha256": digest(plan_path), "archives": BACKGROUND_PINS,
              "numpy": importlib.metadata.version("numpy"),
              "mmap_ninja": importlib.metadata.version("mmap_ninja"),
              "uint16_to_float": "divide by 25.6, clip to [0,26], cast float16",
              "source_split": "speech/no_speech training => train; dinner_party => val; dinner_party_eval => test",
              "caveat": "Precomputed TensorFlow features retain their upstream cadence; this does not convert them into exact 10 ms Go features. Counts describe windows, not independent acoustic events."}
    immutable_json(inside(work, "features/background_recipe.json"), recipe)
    writers = {split: FeatureWriter(inside(work, f"features/background_{split}.npy"),
               (sum(r["split"] == split for r in rows), frames, BINS), recipe) for split in ("train", "val", "test")}
    cache, counts = {}, {s: 0 for s in writers}
    start = time.monotonic()
    for row in rows:
        split = row["split"]
        index = counts[split]
        counts[split] += 1
        if index < writers[split].done:
            continue
        if row["dataset"] not in cache:
            cache[row["dataset"]] = RaggedMmap(str(inside(root, row["dataset"])))
        feat = np.asarray(cache[row["dataset"]][row["item"]])
        if str(feat.dtype) != row["raw_dtype"]:
            raise ValueError("Input feature dtype changed since planning")
        window = feat[row["offset"]:row["offset"] + frames].astype(np.float32)
        if feat.dtype == np.uint16:
            window /= 25.6
        if window.shape != (frames, BINS) or not np.isfinite(window).all() or window.max() > 40:
            raise ValueError("Unexpected feature shape/range")
        writers[split].append(index, np.clip(window, 0, 26).astype(np.float16))
    outputs = [{"split": split, "path": f"features/background_{split}.npy", **writer.finish()}
               for split, writer in writers.items()]
    immutable_json(inside(work, "features/background_complete.json"), {"recipe_sha256": fingerprint(recipe), "outputs": outputs})
    print(json.dumps({"complete": True, "elapsed_seconds": time.monotonic() - start, "outputs": outputs}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("download", "features", "all"))
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3, help="Concurrent downloads/extractions, 1–4")
    parser.add_argument("--frames", type=int, default=FRAMES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or args.frames < 1:
        parser.error("workers must be 1–4 and frames positive")
    work = args.work_dir.resolve()
    with stage_lock(inside(work, "background"), "background"):
        if args.mode in ("download", "all"):
            fetch(inside(work, "background"), args.workers)
        if args.mode in ("features", "all"):
            prepare_features(work, args.frames, args.seed)


if __name__ == "__main__":
    main()
