"""Prepare source-partitioned TTS/real-voice features using the recorded recipe."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
from common import DEFAULT_CONFIG, read_config, require_profile_identity, sha256, work_dir, write_json


def frontend(audio, work, engine):
    import numpy as np
    pcm = np.clip(audio*32768, -32768, 32767).astype("<i2").tobytes()
    if engine == "go":
        result = subprocess.run([str(work/"bin/gofeatures")], input=pcm,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 40)
    from pymicro_features import MicroFrontend
    processor, frames, offset = MicroFrontend(), [], 0
    while offset < len(pcm):
        result = processor.process_samples(pcm[offset:offset+320])
        if not result.samples_read: break
        offset += result.samples_read*2
        if result.features: frames.append(result.features)
    return np.asarray(frames, dtype=np.float32)


def load_rows(manifest, source_root):
    """Reject path escapes and source/hash leakage before any augmentation."""
    rows, identities, hashes, sessions = [], {}, {}, {}
    for line in manifest.read_text().splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        identity = row.get("source_id", row.get("id"))
        if not identity or row["split"] not in ("train", "val", "test") or row["label"] not in (0, 1):
            raise ValueError("Invalid source identity, split, or binary label")
        if identity in identities: raise ValueError("Duplicate source ID")
        identities[identity] = row["split"]
        audio = (source_root/row["path"]).resolve()
        if not audio.is_relative_to(source_root.resolve()): raise ValueError("Audio path escapes source directory")
        digest = sha256(audio)
        if row.get("sha256") and row["sha256"] != digest: raise ValueError("Source audio hash changed")
        if digest in hashes and hashes[digest] != row["split"]: raise ValueError("Audio content crosses partitions")
        hashes[digest] = row["split"]
        if "session" in row:
            session = row["session"]
            if session in sessions and sessions[session] != row["split"]: raise ValueError("Recording session crosses partitions")
            sessions[session] = row["split"]
        rows.append({**row, "source_id": identity, "sha256": digest})
    if not rows: raise ValueError("Empty source manifest")
    return rows


def augment(job):
    import numpy as np
    import soundfile as sf
    from scipy import signal
    row, variant, work, source_root, kind = job
    work, source_root = Path(work), Path(source_root)
    seed = int(hashlib.sha256(f"{row['source_id']}:{variant}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    audio, sr = sf.read(source_root/row["path"], dtype="float32")
    if sr != 16000 or audio.ndim != 1: raise ValueError("Expected mono 16 kHz source audio")
    active = np.flatnonzero(np.abs(audio) > max(.002, np.max(np.abs(audio))*.012))
    if row["label"] and not len(active): raise ValueError("Silent positive recording")
    if len(active): audio = audio[max(0, active[0]-800):min(len(audio), active[-1]+801)]
    context = 252*160
    if row["label"] and len(audio) > context-1600:
        raise ValueError("Positive speech exceeds context; record a shorter natural utterance, never truncate it")
    if len(audio) > context-800:
        start = int(rng.integers(0, len(audio)-(context-800)+1))
        audio = audio[start:start+context-800]
    audio = audio / max(.01, np.max(np.abs(audio))) * float(rng.uniform(.18, .95))
    if variant or row["split"] != "train":
        impulse = np.zeros(6401, np.float32); impulse[0] = 1
        for _ in range(7):
            delay = int(rng.integers(240, len(impulse)))
            impulse[delay] += float(rng.uniform(-.23, .4)*np.exp(-delay/4000))
        audio = signal.fftconvolve(audio, impulse)[:len(audio)+1600]
    bed = rng.normal(0, 1, context+4800).astype(np.float32)
    bed = signal.lfilter([1], [1, -float(rng.uniform(0, .95))], bed).astype(np.float32)
    bed /= max(1e-6, np.std(bed))
    bed *= max(.005, np.sqrt(np.mean(audio**2))) / 10**(float(rng.uniform(14, 38))/20)
    # Check after adding room tails, so the final context retains the whole positive.
    maximum_tail = min(.38*sr, context-len(audio)-160) if row["label"] else .38*sr
    if maximum_tail < 0: raise ValueError("Augmented positive no longer fits the context")
    tail = int(rng.uniform(min(.06*sr, maximum_tail), maximum_tail))
    end = len(bed)-tail; start = max(0, end-len(audio))
    if row["label"] and start < 4800: raise ValueError("Positive speech would be cropped by the feature window")
    bed[start:end] += audio[-(end-start):]
    engine = "c" if kind == "tts" and row["split"] == "train" and variant == 0 else "go"
    result = frontend(bed, work, engine)[-250:]
    if result.shape != (250, 40): raise ValueError("Unexpected frontend shape")
    metadata = {"source_id": row["source_id"], "source_sha256": row["sha256"], "variant": variant,
                "seed": seed, "split": row["split"], "label": row["label"], "frontend": engine,
                "kind": kind, "wav": row["path"], "complete_positive_retained": bool(row["label"])}
    return row["split"], int(row["label"]), np.clip(result, 0, 26).astype(np.float16), metadata


def preserve_level(job):
    """Keep complete short recordings and match the raw evaluator's warmup.

    Variant zero retains the original waveform and level. Other TRAIN variants
    change gain, room reflections and background noise. VAL/TEST stay unaltered;
    their source recordings must still belong to independent acquisition sessions.
    """
    import numpy as np
    import soundfile as sf
    row, variant, work, source_root, kind = job
    if kind != "real" or (row["split"] != "train" and variant != 0):
        raise ValueError("Preserved-level features require real recordings and unaugmented holdouts")
    audio, sr = sf.read(Path(source_root)/row["path"], dtype="float32")
    if sr != 16000 or audio.ndim != 1 or not len(audio):
        raise ValueError("Expected nonempty mono 16 kHz audio")
    context = 252*160
    if len(audio)+320 >= context:
        raise ValueError("Complete recording plus tail must fit the context; no automatic speech cropping")
    if row["label"] and not np.any(audio):
        raise ValueError("Silent positive recording")
    seed = int(hashlib.sha256(f"{row['source_id']}:raw:{variant}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    gain = 1.0 if variant == 0 else float(2**rng.uniform(-1, 3))
    tail = 320 if variant == 0 else int(rng.uniform(320, min(3200, context-len(audio))))
    full = np.concatenate([np.zeros(48000, np.float32), audio*gain, np.zeros(tail, np.float32)])
    if variant and variant % 3 == 0:
        delay = int(rng.integers(320, min(1600, tail)+1))
        full[delay:] += full[:-delay]*float(rng.uniform(.08, .22))
    if variant and variant % 2 == 0:
        full += rng.normal(0, float(rng.uniform(.00002, .00015))*gain, len(full)).astype(np.float32)
    result = frontend(full, Path(work), "go")[-250:]
    if result.shape != (250, 40):
        raise ValueError("Unexpected frontend shape")
    metadata = {"source_id": row["source_id"], "source_sha256": row["sha256"],
                "split": row["split"], "label": row["label"], "variant": variant,
                "seed": seed, "gain": gain, "tail_samples": tail, "leading_samples": 48000,
                "full_source_retained": True, "frontend": "go", "kind": "real",
                "policy": "preserved-level-v1", "unaugmented_holdout": row["split"] != "train"}
    return row["split"], int(row["label"]), np.clip(result, 0, 26).astype(np.float16), metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--kind", choices=["tts", "real"], default="tts")
    parser.add_argument("--real-policy", choices=["legacy", "preserved-level-v1"], default="legacy",
                        help="Optional complete-waveform owner adaptation; use a fresh feature directory")
    parser.add_argument("--manifest")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.kind != "real" and args.real_policy != "legacy":
        parser.error("--real-policy applies only to --kind real")
    cfg = read_config(args.config)
    work = work_dir(args.work_dir)
    require_profile_identity(work, cfg)
    if not 1 <= args.workers <= 32: parser.error("workers must be 1..32")
    source = work/("data-generation" if args.kind == "tts" else "recordings")
    manifest = Path(args.manifest) if args.manifest else source/("manifest-full.jsonl" if args.kind == "tts" else "manifest.jsonl")
    if not (work/"bin/gofeatures").is_file(): raise ValueError("Build the Go frontend first")
    rows = load_rows(manifest, source)
    output = work/"features"; output.mkdir(parents=True, exist_ok=True)
    provenance_path = output/f"{args.kind}_provenance.jsonl"
    names = [output/f"{args.kind}_{split}_{label}.npy" for split in ("train","val","test") for label in (0,1)]
    if provenance_path.exists() or any(p.exists() for p in names):
        raise ValueError("Feature outputs already exist; use a new work directory for changed data")
    import numpy as np
    preserved = args.real_policy == "preserved-level-v1"
    variants = 12 if preserved else 3
    tasks = [(r, v, str(work), str(source), args.kind) for r in rows for v in range(variants if r["split"] == "train" else 1)]
    groups = {(s,y): [] for s in ("train","val","test") for y in (0,1)}
    provenance = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for count, (split,label,features,metadata) in enumerate(pool.map(preserve_level if preserved else augment, tasks, chunksize=16), 1):
            groups[split,label].append(features); provenance.append(metadata)
            if count % 500 == 0: print(f"Features {count}/{len(tasks)}", flush=True)
    for (split,label), values in groups.items():
        array = np.asarray(values, np.float16).reshape(-1,250,40)
        if args.kind == "tts" and not len(array): raise ValueError("Every synthetic partition/label must be nonempty")
        with (output/f"{args.kind}_{split}_{label}.npy").open("xb") as stream: np.save(stream, array)
    with provenance_path.open("x") as stream:
        stream.write("\n".join(json.dumps(r) for r in provenance)+"\n")
    write_json(output/f"{args.kind}_features.json", {
        "source_manifest_sha256": sha256(manifest), "frontend_sha256": sha256(work/"bin/gofeatures"),
        "arrays": [{"path": p.name, "sha256": sha256(p)} for p in names],
        "positive_window_policy": "No speech cropping after room augmentation",
        "real_policy": args.real_policy if args.kind == "real" else None,
    }, exclusive=True)
    print("Saved",len(tasks),args.kind,"feature windows")


if __name__ == "__main__": main()
