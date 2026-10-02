#!/usr/bin/env python3
"""Compare TFLite reference kernels with exact pinned Go scores on identical features.
No WAV frontend is involved here: this isolates interpreter/state compatibility.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--model", required=True, type=Path)
p.add_argument("--features", required=True, type=Path)
p.add_argument("--go-scores", required=True, type=Path)
p.add_argument("--max-raw-error", type=int, default=1,
               help="explicit max absolute error budget in uint8 score units, default 1")
p.add_argument("--scores-out", type=Path)
p.add_argument("--window", type=int, default=5)
p.add_argument("--decision-threshold", type=float, default=0.90)
a = p.parse_args()
os.umask(0o077)
import numpy as np
import tensorflow as tf
if not 0 <= a.max_raw_error <= 255:
    p.error("--max-raw-error must be in [0,255]")
interpreter = tf.lite.Interpreter(
    model_path=str(a.model), num_threads=1,
    experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF,
)
interpreter.allocate_tensors()
inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
assert len(inputs) == len(outputs) == 1, "internal-state one-input/one-output model required"
i, o = inputs[0], outputs[0]
assert i["dtype"] == np.int8 and o["dtype"] == np.uint8
shape = tuple(i["shape"])
assert len(shape) == 3 and shape[0] == 1 and shape[2] == 40
features = np.fromfile(a.features, dtype=np.int8).reshape((-1, 40))
stride = shape[1]
# Never reset interpreter state between chunks of a continuous recording.
predictions = []
for offset in range(0, len(features) - stride + 1, stride):
    interpreter.set_tensor(i["index"], features[offset:offset + stride].reshape(shape))
    interpreter.invoke()
    values = interpreter.get_tensor(o["index"]).reshape(-1)
    assert len(values) == 1
    predictions.append(int(values[0]))
with a.go_scores.open(newline="") as f:
    go = np.array([int(row["raw_uint8"]) for row in csv.DictReader(f)], dtype=np.int16)
tflite = np.asarray(predictions, dtype=np.int16)
assert len(tflite) == len(go) > 0, f"inference count mismatch: TensorFlow={len(tflite)} Go={len(go)}"
assert a.window >= 1 and 0 <= a.decision_threshold <= 1

def averages(values):
    return np.array([np.mean(values[max(0, n-a.window+1):n+1])/255
                     for n in range(len(values))])

go_average, tf_average = averages(go), averages(tflite)
error = np.abs(tflite - go)
worst = int(np.argmax(error))
report = {
    "model_sha256": hashlib.sha256(a.model.read_bytes()).hexdigest(),
    "go_scores_sha256": hashlib.sha256(a.go_scores.read_bytes()).hexdigest(),
    "features_sha256": hashlib.sha256(a.features.read_bytes()).hexdigest(),
    "tensorflow_version": tf.__version__,
    "tensorflow_kernel_resolver": "BUILTIN_REF",
    "input_shape": list(map(int, shape)),
    "input_quantization": i["quantization"],
    "output_quantization": o["quantization"],
    "invocations": len(go),
    "max_absolute_raw_error": int(error.max()),
    "mean_absolute_raw_error": float(error.mean()),
    "exact_match_fraction": float(np.mean(error == 0)),
    "worst_invocation": worst + 1,
    "worst_go_raw": int(go[worst]),
    "worst_tflite_raw": int(tflite[worst]),
    "allowed_max_raw_error": a.max_raw_error,
    "sliding_window": a.window,
    "decision_threshold": a.decision_threshold,
    "go_max_sliding_average": float(go_average.max()),
    "tflite_max_sliding_average": float(tf_average.max()),
    "max_absolute_sliding_average_error": float(np.max(np.abs(go_average-tf_average))),
    "go_clip_detected": bool(np.any(go_average >= a.decision_threshold)),
    "tflite_clip_detected": bool(np.any(tf_average >= a.decision_threshold)),
    "clip_decision_agrees": bool(np.any(go_average >= a.decision_threshold) == np.any(tf_average >= a.decision_threshold)),
    "threshold_side_differs_at_invocations": int(np.count_nonzero((go_average >= a.decision_threshold) != (tf_average >= a.decision_threshold))),
    "passed": bool(error.max() <= a.max_raw_error),
    "note": "Same-feature interpreter parity only; use exact Go frontend and held-out WAVs for acoustic evaluation.",
}
if a.scores_out:
    with a.scores_out.open("x", newline="") as f:
        os.chmod(a.scores_out, 0o600)
        w = csv.writer(f)
        w.writerow(["invocation", "go_raw", "tflite_raw", "absolute_error"])
        w.writerows((n + 1, int(g), int(t), int(e)) for n, (g, t, e) in enumerate(zip(go, tflite, error)))
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["passed"] else 2)
