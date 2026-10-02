# Pinned compatibility findings

## EchoLocal 0.0.8 and microWakeWord

EchoLocal 0.0.8 pins `zserge/microwakeword` at commit `bfaf3840114ece54665c15e6e202ddb1463c3d37`. The exact Go source is used without patches by this validator. `NewDetector` only parses and allocates; its internal `runInference` discards `SetInput`/`Invoke` errors. A model can therefore appear installed yet produce no new scores. The offline gate calls the interpreter directly so those failures are visible.

The selected v2 contract is one INT8 main input `[1, stride, 40]`, internal streaming resource state, and one UINT8 probability element, normally `[1, 1]`. Bundled Okay Nabu has stride 3, input scale `26/255` and zero point -128, output scale `1/256` and zero point 0. The detector hardcodes input packing and interprets output as a byte divided by 255 rather than applying arbitrary output quantization. This validator accepts only that contract, allowing input scale relative rounding error up to 0.002% to accommodate observed converter calibration rounding.

Every subgraph must use the supported operator set:

`CALL_ONCE`, `VAR_HANDLE`, `READ_VARIABLE`, `ASSIGN_VARIABLE`, `RESHAPE`, `CONCATENATION`, `STRIDED_SLICE`, `CONV_2D`, `DEPTHWISE_CONV_2D`, `FULLY_CONNECTED`, `LOGISTIC`, `QUANTIZE`, `SPLIT_V` (named `SPLITV` by the Go parser).

The parser names other operators that the interpreter does not implement, including `ADD`, `AVERAGE_POOL_2D`, `MAX_POOL_2D`, `MUL`, `MEAN`, `PAD` and `PACK`. Naming an operator in a schema is not runtime support.

The convolution/dense kernels assume symmetric INT8 weights (zero point 0). They require an explicit bias tensor: a valid TFLite `-1` absent optional bias causes an index panic. The initial random smoke export exposed this because the converter optimized away its all-zero final dense bias. A nonzero smoke bias retained the tensor; the trained pilot models also retained their learned bias. Validate every final export independently. Do not assume this is fixed by a model filename or metadata change.

ReLU6's upper clamp is not implemented correctly by this pin; avoid it. The safe candidate architecture uses ordinary ReLU. Nonzero STRIDED_SLICE ellipsis/new-axis/shrink-axis masks are also rejected by the gate because its kernel ignores them. Other kernel options and per-channel details still require same-feature TensorFlow comparison on the trained model.

Primary sources:

- [EchoLocal 0.0.8 dependency pin](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/go.mod)
- [EchoLocal backend and score handling](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/internal/feature/detect/backends.go)
- [EchoLocal timing and thresholds](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/internal/feature/detect/engine.go)
- [Pinned Go detector, including silent inference errors](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/microwakeword.go)
- [Pinned interpreter kernel dispatch and implementation](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/interpreter/ops.go)

## Trainer compatibility

The reference training recipe and the pilot models use the pinned kahrendt MixedNet core at `a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0`. The following architecture exported and executed successfully in the Go pin: pointwise filters `48,48,48,48`, repeat counts `1,1,1,1`, mixed kernels `[5],[7,11],[9,15],[23]`, residual connections all false, first convolution 32 filters/kernel 5/stride 3, spatial attention false, pooled false and max_pool false. Training context is 250 frames at 10 ms. This is evidence for this actual exported graph, not a guarantee for all MixedNet flag combinations.

Residual connections introduce unsupported ADD; spatial attention introduces unsupported multiplication/reduction kernels; pooling introduces unsupported pool kernels. Keep those paths disabled. Export `STREAM_INTERNAL_STATE_INFERENCE`, not external-state or nonstreaming inference. Quantize all model/state tensors using INT8 builtins and variable quantization; use INT8 input and UINT8 output.

The Apple Silicon wrapper at `daca60ca8b42d6e11658aecd0db74f252c8dbda2` packages the internal-state quantized artifact. Its script dynamically clones/pulls TaterTotterson instead of pinning it, so pin the dependency separately. That wrapper/core combination is a separately inspected alternative, not the core used by this reference recipe. Keep the tested kahrendt core pin and set architecture flags explicitly.

The interkelstar wrapper at `8fdbadc3b969a8c1993108c0d655910440dfb762` hardcodes residual connections true and pooled true. Its export path also falls back from streaming to nonstreaming after errors, then from full integer quantization to less restricted conversion. Those fallbacks are incompatible with an executable EchoLocal guarantee and must fail closed in an adapted workflow. The wrapper's setup pins kahrendt core `a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0`; its behavior is not interchangeable with a later unpinned core.

Primary sources:

- [Pinned reference MixedNet architecture](https://github.com/kahrendt/microWakeWord/blob/a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0/microwakeword/mixednet.py)
- [Pinned reference streaming export](https://github.com/kahrendt/microWakeWord/blob/a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0/microwakeword/utils.py)
- [Apple Silicon wrapper](https://github.com/skrashevich/microWakeWord-Trainer-AppleSilicon/blob/daca60ca8b42d6e11658aecd0db74f252c8dbda2/train_microwakeword_macos.sh)
- [interkelstar architecture, feature scaling and fallback exports](https://github.com/interkelstar/microwakeword-trainer/blob/8fdbadc3b969a8c1993108c0d655910440dfb762/train_mww.py)

## Frontend and feature scale

The device consumes mono 16 kHz signed PCM16, uses 30 ms windows, 10 ms hops for this model, 40 channels and 125–7500 Hz frequency limits. Both PCAN and noise reduction carry state. Do not substitute a generic librosa mel spectrogram.

`pymicro-features==2.0.2` returns float features equal to raw uint16 features multiplied by 0.0390625 (divided by 25.6). The pinned kahrendt dataset loader applies this same factor to stored uint16 features. interkelstar's `/24.7` for imported uint16 negatives is different and should not be copied into this workflow. Never infer an old precomputed dataset's 10 ms versus 20 ms frame step from its array shape; verify its provenance or re-extract raw audio.

The pinned Go code packs its own raw frontend values as `clamp(((raw*256 + 333)/666) - 128, -128, 127)` using integer division. The `gofeatures` tool dequantizes these exact int8 values by `(q+128)*26/255` for training. The Go frontend is a floating-point approximation of the C frontend; the historical reference comparison showed material per-frame differences. Mix/evaluate exact Go features when targeting EchoLocal, and test recorded utterances rather than assuming C-frontend validation transfers perfectly.

The pinned core's C path ignores its Python `step_ms` argument and relies on the C frontend's default. The installed 2.0.2 frontend was measured to use 10 ms, with exactly 761 frames on the reference WAV. Its API requires full 320-byte PCM chunks; discard an incomplete final chunk, without padding it silently. The C core helper's strict `<` loop can omit a final full chunk at an exact boundary; this is a small edge-handling difference, not evidence of a different hop.

Primary sources:

- [Pinned Go frontend](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/audiofrontend/frontend.go)
- [Go frontend test's approximation tolerance](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/audiofrontend/frontend_test.go)
- [Pinned stored uint16 scaling](https://github.com/kahrendt/microWakeWord/blob/a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0/microwakeword/data.py)
- [Pinned C versus TensorFlow frontend paths](https://github.com/kahrendt/microWakeWord/blob/a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0/microwakeword/audio/audio_utils.py)
- [Pinned Go Okay Nabu synthesized-audio test skip](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/microwakeword_test.go)

## Home Assistant 2026.9.1 manifest

Home Assistant's schema requires only string fields `type` and `wake_word`, and allows other fields. This is metadata validation, not executable-model validation. It scans flat `/config/custom_wake_words/*.json`, requires a same-stem `.tflite`, computes its SHA-256/size and offers the model by the JSON filename stem. The cache is a singleton; file changes may require a suitable reload/restart before discovery. HA serves a local URL selected with `allow_cloud=False`; the Echo must actually reach it.

EchoLocal additionally reads the manifest's `model` filename, `trained_languages`, `micro.sliding_window_size` and `micro.feature_step_size`. Keep ASCII matching filenames such as `privet_myshka_v1.json` and `privet_myshka_v1.tflite`, and use the actual Russian phrase as UTF-8 display metadata. Example:

```json
{
  "type": "micro",
  "wake_word": "Привет, Мышка",
  "model": "privet_myshka_v1.tflite",
  "trained_languages": ["ru"],
  "version": 2,
  "micro": {
    "sliding_window_size": 5,
    "feature_step_size": 10,
    "probability_cutoff": 0.85
  }
}
```

`probability_cutoff` here is illustrative metadata, not a selected deployment threshold: EchoLocal 0.0.8 overrides the detector cutoff with 1.1 and applies the active HA per-slot threshold separately. It does not validate ESPHome tensor arena or minimum-version metadata. Do not invent a tested tensor-arena size. A Russian HA speech pipeline does not create a Russian wake-word detector; the `.tflite` must actually be trained for the phrase.

Keep Okay Nabu in slot 0 and add the Russian model in slot 1. External model selection replaces the active list; it must preserve both IDs deliberately. These validation tools never perform deployment.

Primary sources:

- [HA 2026.9.1 schema, discovery and model serving](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/esphome/assist_satellite.py)
- [EchoLocal manifest loading](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/internal/lib/wake/models.go)
- [EchoLocal external model download](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/internal/lib/wake/external.go)
- [EchoLocal slots](https://github.com/ygelfand/echolocal/blob/6eff3b12db168223df3871f0a56250e736d3954a/internal/feature/wakeword/wakeword.go)
