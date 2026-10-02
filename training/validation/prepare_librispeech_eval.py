#!/usr/bin/env python3
"""Decode a fixed LibriSpeech inventory to PCM; no resampling or model inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--librispeech", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path,
                   help="new directory, refused if it already exists")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--val-speakers", action="store_true")
    g.add_argument("--inventory", type=Path,
                   help="JSONL with path relative to --librispeech, in fixed order")
    a = p.parse_args()
    import soundfile as sf

    os.umask(0o077)
    root, dst = a.librispeech.resolve(), a.output_dir.resolve()
    selection_file = root / "split_manifest.json" if a.val_speakers else a.inventory.resolve()
    if a.val_speakers:
        split = json.loads(selection_file.read_text())
        files = []
        for speaker in sorted(map(str, split["val_speakers"])):
            if not speaker.isdigit():
                raise ValueError("LibriSpeech speaker ids must be numeric")
            selected = sorted((root / "raw/LibriSpeech/dev-clean" / speaker).glob("*/*.flac"))
            if not selected:
                raise ValueError(f"no downloaded audio for validation speaker {speaker}")
            files.extend(selected)
        selection = "all dev-clean utterances belonging to fixed validation speakers"
    else:
        rows = [json.loads(line) for line in selection_file.read_text().splitlines() if line.strip()]
        if any(Path(r["path"]).is_absolute() for r in rows):
            raise ValueError("inventory paths must be relative to --librispeech")
        files = [(root / r["path"]).resolve() for r in rows]
        selection = "fixed ordered inventory"
    files = [f.resolve() for f in files]
    if not files or len(set(files)) != len(files) or len({f.stem for f in files}) != len(files):
        raise ValueError("expected a nonempty list of unique files and utterance ids")
    for path in files:
        path.relative_to(root)
        if not path.is_file():
            raise ValueError(f"missing source: {path}")
    dst.mkdir(parents=True, exist_ok=False, mode=0o700)
    provenance, offset_samples = [], 0
    with (dst / "concatenated.s16le").open("xb") as cf, (dst / "per-utterance.jsonl").open("x") as mf:
        for path in files:
            audio, rate = sf.read(path, dtype="int16", always_2d=True)
            if rate != 16000 or audio.shape[1] != 1 or len(audio) < 480:
                raise ValueError(f"expected mono 16kHz, at least 30ms: {path}")
            pcm = audio[:, 0].astype("<i2").tobytes()
            out = dst / (path.stem + ".s16le")
            with out.open("xb") as f:
                f.write(pcm)
            cf.write(pcm)
            mf.write(json.dumps({"id": path.stem, "label": "negative", "pcm": out.name,
                                 "leading_ms": 3000, "trailing_ms": 1000}) + "\n")
            provenance.append({"id": path.stem, "source": str(path.relative_to(root)),
                               "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "samples": len(audio),
                               "concat_start_sample": offset_samples,
                               "concat_end_sample": offset_samples + len(audio)})
            offset_samples += len(audio)
    with (dst / "concatenated.jsonl").open("x") as f:
        f.write(json.dumps({"id": "concatenated-speech", "label": "negative", "pcm": "concatenated.s16le",
                            "leading_ms": 3000, "trailing_ms": 1000}) + "\n")
    report = {"selection": selection, "selection_file_sha256": hashlib.sha256(selection_file.read_bytes()).hexdigest(),
              "utterances": len(files), "source_samples": offset_samples, "source_seconds": offset_samples / 16000,
              "concatenation": "no gaps or resampling, deterministic order, streaming state retained across joins",
              "warmup": "3000ms digital zero excluded from scoring; 1000ms zero tail",
              "claim": "concatenated clean speech benchmark, not real-room microphone audio", "files": provenance}
    with (dst / "provenance.json").open("x") as f:
        f.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "files"}, indent=2))


if __name__ == "__main__":
    main()
