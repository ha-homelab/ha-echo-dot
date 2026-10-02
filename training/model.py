"""Build, smoke-test, benchmark, or export the pinned streaming architecture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from common import CORE_REVISION, DEFAULT_CONFIG, candidate_dir, read_config, sha256, work_dir, write_json


def initialize(work, cfg, device="cpu"):
    if os.environ.get("TF_USE_LEGACY_KERAS") == "1":
        raise ValueError("Legacy Keras is incompatible with this pinned builder")
    source = work / "vendor/micro-wake-word"
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip()
    if revision != CORE_REVISION or dirty:
        raise ValueError("Builder must be clean and at the pinned revision; run the setup stage")
    sys.path.insert(0, str(source))
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
    import tensorflow as tf
    if device == "cpu":
        tf.config.set_visible_devices([], "GPU")
    elif not tf.config.list_physical_devices("GPU"):
        raise ValueError("No Metal GPU is available; do not label a CPU fallback as a GPU benchmark")
    tf.config.threading.set_intra_op_parallelism_threads(cfg["training"]["cpu_threads"])
    tf.config.threading.set_inter_op_parallelism_threads(2)
    tf.keras.utils.set_random_seed(cfg["seed"])
    return tf


def build(cfg):
    from microwakeword import mixednet
    return mixednet.model(SimpleNamespace(**cfg["architecture"]), (cfg["frames"], 40), batch_size=None)


def export(model, output, representative, cfg):
    import numpy as np
    import tensorflow as tf
    from microwakeword.utils import to_streaming_inference
    from microwakeword.layers.modes import Modes
    output.mkdir(parents=True, exist_ok=False)
    stride = cfg["architecture"]["stride"]
    streaming = to_streaming_inference(model, {
        "spectrogram_length": cfg["frames"], "features_length": cfg["frames"], "stride": stride,
    }, mode=Modes.STREAM_INTERNAL_STATE_INFERENCE)
    if tuple(streaming.input_shape) != (1, stride, 40):
        raise ValueError(f"Unexpected streaming shape: {streaming.input_shape}")
    archive = tf.keras.export.ExportArchive()
    archive.track(streaming)
    archive.add_endpoint("serve", fn=streaming.call,
        input_signature=[tf.TensorSpec(streaming.input.shape, tf.float32)])
    archive.write_out(str(output / "saved_model"), verbose=False)

    def chunks():
        for sample in representative:
            for offset in range(0, len(sample)-stride+1, stride):
                yield [sample[None, offset:offset+stride].astype(np.float32)]

    converter = tf.lite.TFLiteConverter.from_saved_model(str(output / "saved_model"))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter._experimental_variable_quantization = True
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.uint8
    converter.representative_dataset = chunks
    data = converter.convert()  # Never fall back to float or nonstreaming output.
    path = output / (cfg["model_id"] + ".tflite")
    path.write_bytes(data)
    interpreter = tf.lite.Interpreter(model_content=data)
    interpreter.allocate_tensors()
    inp, out = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    if inp["dtype"] != np.int8 or out["dtype"] != np.uint8:
        raise ValueError("Quantized input/output contract failed")
    if tuple(inp["shape"]) != (1, stride, 40):
        raise ValueError("Exported shape changed")
    if not np.isclose(inp["quantization"][0], 26/255, rtol=1e-4) or inp["quantization"][1] != -128:
        raise ValueError("Input scale does not match the deployed frontend")
    if out["quantization"] != (1/256, 0):
        raise ValueError("Output score quantization changed")
    ops = sorted({x["op_name"] for x in interpreter._get_ops_details()})
    allowed = set("CALL_ONCE VAR_HANDLE READ_VARIABLE ASSIGN_VARIABLE RESHAPE CONCATENATION STRIDED_SLICE CONV_2D DEPTHWISE_CONV_2D FULLY_CONNECTED LOGISTIC QUANTIZE SPLIT_V DELEGATE".split())
    if set(ops)-allowed:
        raise ValueError(f"Unsupported operations: {set(ops)-allowed}")
    interpreter.set_tensor(inp["index"], np.full(inp["shape"], -128, np.int8))
    interpreter.invoke()
    report = {"input_shape": inp["shape"].tolist(), "input_quantization": inp["quantization"],
              "output_quantization": out["quantization"], "ops": ops, "bytes": len(data),
              "model_sha256": sha256(path), "note": "Requires the independent exact-Go validator before any deployment."}
    write_json(output / "export.json", report)
    manifest = {"type": "micro", "wake_word": cfg["wake_word"], "author": "Local training experiment",
                "model": path.name, "trained_languages": cfg["trained_languages"], "version": 2,
                "micro": {"probability_cutoff": cfg["provisional_cutoff"],
                          "feature_step_size": cfg["feature_step_ms"], "sliding_window_size": cfg["sliding_window_size"]}}
    write_json(path.with_suffix(".json"), manifest)
    (output / "sha256.txt").write_text(sha256(path) + "  " + path.name + "\n")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["smoke", "benchmark", "export"])
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--candidate")
    parser.add_argument("--device", choices=["cpu", "metal"], default="cpu")
    args = parser.parse_args()
    work, cfg = work_dir(args.work_dir), read_config(args.config)
    tf = initialize(work, cfg, args.device)
    import numpy as np
    model = build(cfg)
    if args.stage == "benchmark":
        model.compile(optimizer=tf.keras.optimizers.Adam(.001), loss="binary_crossentropy", jit_compile=False)
        rng = np.random.default_rng(cfg["seed"])
        x = rng.uniform(0, 26, (64, cfg["frames"], 40)).astype(np.float32)
        y = rng.integers(0, 2, (64, 1)).astype(np.float32)
        for _ in range(5): model.train_on_batch(x, y)
        start = time.monotonic()
        for _ in range(50): model.train_on_batch(x, y)
        result = {"requested_device": args.device, "tensorflow_devices": [d.name for d in tf.config.list_logical_devices()],
                  "seconds_per_update": (time.monotonic()-start)/50, "updates": 50, "warmup_updates": 5}
        write_json(work / f"benchmark-{args.device}.json", result, exclusive=True)
        print(json.dumps(result))
        return
    publish = None
    if args.stage == "smoke":
        model.layers[-1].bias.assign([.01])  # Go requires the otherwise optional dense bias tensor.
        samples = np.random.default_rng(1).uniform(0, 26, (8, cfg["frames"], 40)).astype(np.float32)
        samples[0, 0, :2] = [0, 26]
        path = export(model, work / "smoke-export", samples, cfg)
    else:
        if not args.candidate: parser.error("export requires --candidate")
        directory = candidate_dir(work, args.candidate)
        saved = json.loads((directory / "recipe.json").read_text())
        if saved["config"] != cfg: raise ValueError("Export recipe differs from trained recipe")
        completed = json.loads((directory / "training-complete.json").read_text())
        if sha256(directory / "best.weights.h5") != completed["weights_sha256"]:
            raise ValueError("Completed training weights changed")
        for name, identity in saved["input_features"].items():
            if sha256(work/"features"/(name+".npy")) != identity["sha256"]:
                raise ValueError(f"Training or validation features changed after training: {name}")
        model.load_weights(directory / "best.weights.h5")
        samples = np.concatenate([np.load(work/"features"/name, mmap_mode="r")[:count] for name,count in
                                  [("tts_train_1.npy",64),("tts_train_0.npy",32),("background_train.npy",32)]]).astype(np.float32)
        samples[0, 0, :2] = [0, 26]
        export_dir = directory / "export"
        path = export(model, export_dir, samples, cfg)
        publish = directory
    validator = work / "bin/validate"
    if not validator.exists(): raise ValueError("Missing Go validator; run the build stage")
    report = subprocess.run([str(validator), "-model", str(path)], capture_output=True, text=True)
    (path.parent/"go-structure.json").write_text(report.stdout)
    (path.parent/"go-structure.stderr.log").write_text(report.stderr)
    if report.returncode:
        raise RuntimeError("Exact-Go validation failed; inspect go-structure.json and go-structure.stderr.log; do not deploy this candidate")
    if publish is not None:
        # Publish the pair only after conversion AND exact-runtime structure checks succeed.
        for source in [path, path.with_suffix(".json")]:
            target = publish/source.name
            with target.open("xb") as out: out.write(source.read_bytes())
    print((publish/path.name) if publish else path)


if __name__ == "__main__": main()
