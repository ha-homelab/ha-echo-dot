#!/usr/bin/env python3
"""Read-only verification of the fixed Russian synthesis recipe and every WAV."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import wave

from common import digest, inside


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_dataset(work: Path, stage="full") -> dict:
    import numpy as np
    from generate import make_jobs
    root = inside(work, "data-generation")
    manifest = root / f"manifest-{stage}.jsonl"
    rows = [json.loads(x) for x in manifest.read_text().splitlines()]
    expected_jobs = make_jobs()
    if stage == "smoke":
        expected_jobs = {v: jobs[:32] for v, jobs in expected_jobs.items()}
    expected = {x["source_id"]: x for jobs in expected_jobs.values() for x in jobs}
    require(len(rows) == len(expected), "Wrong source count")
    require({x["source_id"] for x in rows} == set(expected), "Missing/duplicate/unexpected sources")
    require(len({x["sha256"] for x in rows}) == len(rows), "Duplicate waveforms")
    require(len({x["path"] for x in rows}) == len(rows), "Duplicate paths")
    marker_path = root / ("_SUCCESS.json" if stage == "full" else "summary-smoke.json")
    marker = json.loads(marker_path.read_text())
    expected_hash = marker.get("sha256", marker.get("manifest_sha256"))
    require(digest(manifest) == expected_hash, "Manifest hash mismatch")
    all_paths, counts = set(), {}
    minimum_rms, clipped = 1., 0
    for row in rows:
        require(all(row.get(k) == v for k, v in expected[row["source_id"]].items()), "Source recipe/split mismatch")
        path = inside(root, row["path"]).resolve()
        require(path.is_relative_to((root / "wav").resolve()), "WAV outside dataset")
        all_paths.add(path)
        require(digest(path) == row["sha256"], "WAV hash mismatch")
        require(row["trimmed"] is row["padded"] is row["augmented"] is False, "Unexpected derived audio")
        with wave.open(str(path), "rb") as wav:
            require((wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2), "Wrong PCM format")
            require(wav.getnframes() == row["samples"], "Wrong sample count")
            require(wav.getnframes() / 16000 == row["duration"], "Wrong duration")
            pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64)
        rms = float(np.sqrt(np.mean(pcm ** 2)) / 32768)
        require(rms > .001, "Silent/invalid waveform")
        minimum_rms = min(minimum_rms, rms)
        clipped += int(np.sum(np.abs(pcm) >= 32767))
        key = f"{row['split']}_{row['label']}"
        counts[key] = counts.get(key, 0) + 1
    if stage == "full":
        require(all_paths == {p.resolve() for p in (root / "wav").glob("*/*/*.wav")}, "Unexpected extra WAV files")
    return {"status": "passed", "stage": stage, "wav_files": len(rows), "counts": counts,
            "manifest_sha256": digest(manifest), "format": "16000 Hz mono signed PCM16",
            "all_source_ids_unique": True, "all_waveform_sha256_unique": True,
            "source_recipe_and_partition_verified": True, "all_wav_hashes_verified": True,
            "minimum_rms": minimum_rms, "samples_at_pcm_limit": clipped,
            "read_only": True,
            "limitation": "Synthetic integrity only; shared TTS voices do not establish real-speaker accuracy or human-approved prosody."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=("smoke", "full"), default="full")
    args = parser.parse_args()
    print(json.dumps(verify_dataset(args.work_dir.resolve(), args.stage), indent=2))


if __name__ == "__main__":
    main()
