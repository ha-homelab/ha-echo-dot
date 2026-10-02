#!/usr/bin/env python3
"""Measure C pymicro_features versus pinned Go features; do not assume bit equality."""
import argparse
import importlib.metadata
import json
import os
import wave
from pathlib import Path


p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--wav", required=True, type=Path)
p.add_argument("--go-int8", required=True, type=Path)
p.add_argument("--go-uint16", required=True, type=Path)
p.add_argument("--c-int8-out", type=Path)
a = p.parse_args()
os.umask(0o077)
import numpy as np
from pymicro_features import MicroFrontend
with wave.open(str(a.wav)) as wav:
    assert wav.getframerate() == 16000 and wav.getnchannels() == 1 and wav.getsampwidth() == 2
    audio = wav.readframes(wav.getnframes())
frontend = MicroFrontend()
frames, frame_end_samples = [], []
offset = 0
while offset + 320 <= len(audio):
    result = frontend.process_samples(audio[offset:offset + 320])
    assert result.samples_read > 0, "C frontend consumed no samples"
    offset += result.samples_read * 2
    if result.features:
        frames.append(result.features)
        frame_end_samples.append(offset // 2)
c_float = np.asarray(frames, dtype=np.float32).reshape((-1, 40))
c_raw = np.rint(c_float * 25.6).astype(np.uint16)
# This matches EchoLocal's hardcoded raw-feature packing, isolating frontend differences.
c_int8 = np.clip((c_raw.astype(np.int32) * 256 + 333) // 666 - 128, -128, 127).astype(np.int8)
go_raw = np.fromfile(a.go_uint16, dtype="<u2").reshape((-1, 40))
go_int8 = np.fromfile(a.go_int8, dtype=np.int8).reshape((-1, 40))
assert len(c_float) == len(go_raw) == len(go_int8), f"frame count mismatch C={len(c_float)} Go={len(go_raw)}"
raw_error = np.abs(c_raw.astype(np.int32) - go_raw.astype(np.int32))
q_error = np.abs(c_int8.astype(np.int16) - go_int8.astype(np.int16))
steps = np.diff(frame_end_samples)
report = {
    "pymicro_features_version": importlib.metadata.version("pymicro-features"),
    "audio_samples": len(audio) // 2,
    "c_frames": len(c_float), "go_frames": len(go_raw),
    "c_first_frame_end_sample": frame_end_samples[0],
    "c_hop_samples_unique": list(map(int, np.unique(steps))),
    "c_first_window_ms": frame_end_samples[0] / 16,
    "c_hop_ms_unique": list(map(float, np.unique(steps) / 16)),
    "c_float_min": float(c_float.min()), "c_float_max": float(c_float.max()),
    "c_float_mean": float(c_float.mean()),
    "c_raw_min": int(c_raw.min()), "c_raw_max": int(c_raw.max()),
    "go_raw_min": int(go_raw.min()), "go_raw_max": int(go_raw.max()),
    "c_int8_min": int(c_int8.min()), "c_int8_max": int(c_int8.max()),
    "go_int8_min": int(go_int8.min()), "go_int8_max": int(go_int8.max()),
    "raw_mean_absolute_difference": float(raw_error.mean()),
    "raw_max_absolute_difference": int(raw_error.max()),
    "int8_mean_absolute_difference": float(q_error.mean()),
    "int8_max_absolute_difference": int(q_error.max()),
    "int8_exact_match_fraction": float(np.mean(q_error == 0)),
    "note": "Measured frontend difference, not a pass/fail quality gate. C float features are raw uint16 /25.6; Go packs raw features directly. No resampling or frontend resets between frames.",
}
if a.c_int8_out:
    with a.c_int8_out.open("xb") as f:
        f.write(c_int8.tobytes())
    os.chmod(a.c_int8_out, 0o600)
print(json.dumps(report, indent=2))
