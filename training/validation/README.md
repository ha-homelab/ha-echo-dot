# Offline validation and frozen evaluation

These tools target **EchoLocal 0.0.8**, using its exact Go microWakeWord dependency without patches. They never contact an Echo or Home Assistant. Executable-model compatibility, numerical agreement, held-out accuracy and room acceptance are separate checks. Read [COMPATIBILITY.md](COMPATIBILITY.md) before changing the architecture or frontend.

Run commands from the repository root. Keep `WORK` outside a public checkout; it contains audio, trained models, logs and binaries. Python commands use the training environment described in [the training instructions](../README.md); `--help` works without third-party Python packages.

## Build once

```bash
REPO="$PWD"
WORK="$HOME/echolocal-training-private"
export WORK
umask 077
mkdir -p "$WORK/bin" "$WORK/evaluation"
(
  cd "$REPO/training/validation"
  GOPROXY=https://proxy.golang.org,direct go mod download
  GOPROXY=https://proxy.golang.org,direct go build -trimpath -o "$WORK/bin/validate" .
  GOPROXY=https://proxy.golang.org,direct go build -trimpath -o "$WORK/bin/gofeatures" ./cmd/gofeatures
  go test ./...
  go vet ./...
)
python -m unittest discover -s training/validation -p 'test_*.py'
```

Go 1.26 or later is required by this module. `go.mod` and `go.sum` pin dependencies. The proxy override affects only the command. Do not replace the validator binary after freezing a protocol: its SHA-256 is part of the evidence.

`reference-sources.json` lists public, commit-pinned Okay Nabu assets and runtime test audio with hashes. Those assets are **not included** in this repository. Download them into a private work directory and verify their SHA-256 if you want a positive compatibility reference. An upstream test recording is an execution fixture, not an accuracy benchmark for a new Russian phrase.

## Inspect the final exported model

```bash
MODEL="$WORK/models/candidate-2/privet_myshka_v1.tflite"
"$WORK/bin/validate" -model "$MODEL"
```

The validator checks every subgraph's operator whitelist, supported tensor types, INT8 input `[1, stride, 40]`, UINT8 scalar output, quantization, internal resource state, explicit bias tensors and known unsupported options. It calls `SetInput` and `Invoke` directly 64 times so errors cannot disappear inside the detector wrapper. These checks are conservative and do not implement the full TFLite specification.

For an existing **validation** recording, set `WAV` to an uncompressed PCM16 mono 16 kHz WAV. This parity comparison must use validation audio, before opening the final test set:

```bash
WAV="$WORK/recordings/validation-phrase.wav"
test -f "$WAV"
QA="$(mktemp -d "$WORK/evaluation/parity.XXXXXX")"
"$WORK/bin/validate" -model "$MODEL" -wav "$WAV" \
  -features-out "$QA/trace.int8" -raw-features-out "$QA/trace.uint16" \
  -scores-out "$QA/go.csv" > "$QA/go.json"
python training/validation/compare_tflite.py \
  --model "$MODEL" --features "$QA/trace.int8" --go-scores "$QA/go.csv" \
  --scores-out "$QA/tensorflow.csv" --decision-threshold 0.90 \
  > "$QA/parity.json"
```

The last command returns **2 on strict parity failure**, while preserving its JSON report. It runs TensorFlow Lite reference kernels on identical int8 features, with state retained between invocations. The fixed strict budget is one raw UINT8 score unit. A matching threshold decision is reported separately and does not turn a failed numerical gate into a pass. Test several relevant validation traces, including a high-scoring negative. A constant-output random model is a weak numerical test.

The single-waveform Go check also compares its direct score trace against the public Go Detector, catching silent inference failures. The batch evaluator calls the same interpreter directly but does not run the duplicate Detector pass over every long recording.

## Verify frontend differences and extract features

```bash
python training/validation/compare_frontends.py \
  --wav "$WAV" --go-int8 "$QA/trace.int8" --go-uint16 "$QA/trace.uint16" \
  --c-int8-out "$QA/c.int8" > "$QA/frontends.json"
```

This measures `pymicro-features==2.0.2` against the pinned Go approximation; it is not an equality gate. Both use a 30 ms first window, 10 ms hop and 40 channels. C float features are raw uint16 divided by **25.6**, not 24.7. Go packs its own frontend output directly.

`gofeatures` takes **headerless mono 16 kHz int16LE PCM on stdin**, not a WAV container. It emits only headerless float32LE row-major `[frames,40]` on stdout. Diagnostics go to stderr. It resets the frontend once per process, accepts 480 samples to 32 MiB, and returns `(q+128)*float32(26/255)` from the exact Go int8 features. Do not apply another `/25.6` to this output. Extract the full recording before slicing training windows.

```python
import os, subprocess
from pathlib import Path
import numpy as np

binary = Path(os.environ["WORK"]) / "bin/gofeatures"
# pcm16 is already mono 16 kHz; conversion/resampling belongs to data preparation.
def extract(pcm16):
    result = subprocess.run([str(binary)], input=pcm16.astype("<i2").tobytes(),
                            capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1, 40)
```

## Prepare evaluation audio without scoring it

TTS preparation reads `WORK/data-generation/manifest-full.jsonl`, verifies any source checksums, and writes relative audio paths. It selects the existing split; it does not create or reshuffle a split.

```bash
python training/evaluate.py prepare-tts --work-dir "$WORK" --split val
python training/evaluate.py prepare-tts --work-dir "$WORK" --split test
python training/validation/prepare_librispeech_eval.py \
  --librispeech "$WORK/librispeech" --output-dir "$WORK/evaluation/audio/libri-val" \
  --val-speakers
python training/validation/prepare_librispeech_eval.py \
  --librispeech "$WORK/librispeech" --output-dir "$WORK/evaluation/audio/libri-test" \
  --inventory "$WORK/librispeech/test_clean_continuous_at_least_1h.jsonl"
```

The LibriSpeech input comes from the [data preparation stage](../data/README.md). Validation uses all downloaded `dev-clean` utterances for the saved validation speaker IDs. Test uses the supplied ordered JSONL inventory, with paths relative to the LibriSpeech directory. No resampling occurs. Output directories must be new; failures leave partial output for inspection instead of silently overwriting it.

Each output directory contains `per-utterance.jsonl`, `concatenated.jsonl`, decoded PCM and `provenance.json` with source/PCM hashes and join boundaries. Use **only one** of these two manifests in a run. `concatenated.jsonl` preserves streaming state across all joins with no inserted gaps. It is a concatenated clean-speech benchmark, not real-room continuous microphone audio.

The general batch JSONL schema is:

```json
{"id":"positive-001","label":"positive","wav":"audio/positive.wav","leading_ms":3000,"trailing_ms":1000}
{"id":"negative-stream","label":"negative","pcm":"audio/negative.s16le","leading_ms":3000,"trailing_ms":1000}
```

Use unique IDs and exactly one `wav` or `pcm`. Paths resolve relative to the manifest. Each row resets frontend/model state. Three seconds of leading digital zero fill the 250-frame context and are excluded from scored events; one second of trailing zero remains in the scored interval. This is a quiet warmup, not ambient room audio. Event counts simulate 20 ms microphone polling, 300 ms hold and 800 ms refractory timing, using the last available exact Go sliding score. They do not reproduce HA's conversation lifecycle. Source-duration denominators exclude padding.

## Calibrate, freeze, then explicitly test

Choose criteria before calibration. In this example: minimum cutoff 0.85, recall at least 98%, zero negative events, sliding window five, and at least 3,600 seconds of test negative source audio. Calibration runs a grid on **validation only**:

```bash
RUN="candidate-2-evaluation"
python training/evaluate.py calibrate --work-dir "$WORK" --run-id "$RUN" \
  --model "$MODEL" --manifest "$WORK/evaluation/manifests/tts-val.jsonl" \
  --manifest "$WORK/evaluation/audio/libri-val/concatenated.jsonl" \
  --parity-report "$QA/parity.json" \
  --thresholds 0.85,0.90,0.92,0.95,0.97,0.99 --min-cutoff 0.85 --min-recall 0.98
```

Repeat `--parity-report` for additional validation traces. Calibration writes `WORK/evaluation/RUN/calibration.json` and `.sha256`, complete per-clip scores and summaries. Exit 2 means no eligible cutoff or a strict parity failure. Inspect the result; do not suppress the failure in an automation.

If 0.90 is listed under `eligible_cutoffs`, freeze it **before** final test inference:

```bash
python training/evaluate.py freeze --work-dir "$WORK" --run-id "$RUN" --cutoff 0.90 \
  --test-manifest "$WORK/evaluation/manifests/tts-test.jsonl" \
  --test-manifest "$WORK/evaluation/audio/libri-test/concatenated.jsonl" \
  --min-test-negative-seconds 3600
```

If strict parity failed and the purpose is to measure the failure's practical impact, add **`--evaluation-only`** to that freeze command. It retains `strict_parity: FAIL` throughout the protocol and final report. It is not an acceptance override. A cutoff that failed the prespecified validation recall/zero-negative criteria cannot be frozen.

`protocol.json` and `protocol.sha256` lock the model and validator binaries, validation evidence, cutoff/window, test manifests, all source audio hashes, optional provenance, and criteria. Files must remain at their frozen paths. Any changed bytes are rejected. Exact PCM overlap between validation and test is rejected, including member hashes recorded by LibriSpeech preparation. This is an additional guard; source/speaker separation must already be enforced by data preparation.

Final test execution is a separate, explicit command. It has no cutoff override:

```bash
python training/evaluate.py test --work-dir "$WORK" --run-id "$RUN"
```

The command reserves test audio in `WORK/evaluation/holdout-history/` **before inference**, including attempts that later fail or crash. A later run that uses the same audio is refused. `--allow-reused-test 'reason'` permits a diagnostic rerun in a new run directory, but labels it `reused_not_clean` and fails the `clean_holdout` gate. Never delete the ledger or start another work directory to present tuning on observed test data as an unseen test. The ledger cannot prove what happened outside its own work directory, and checksums are not signed external attestations.

Runs and reports are not overwritten. If a process crashes while holding `.evaluation.lock`, confirm the process has exited before removing **only that lock**; retain the consumed-holdout record and partial evidence. Prepare a new run ID for subsequent diagnostic work.

## Result contract

`test.json` and `test.sha256` retain all failures. Exit 0 means the automated **offline** gates passed; exit 2 means an offline gate failed. `gates` contains `runtime`, `strict_parity`, `positive_recall`, `zero_negative_events`, `negative_duration`, `clean_holdout`, `human_trials`, and `room_soak`, each with `status` equal to `PASS`, `FAIL` or `NOT_RUN`. `model_sha256`, `cutoff` and `protocol_sha256` tie the report to its frozen artifact.

These scripts leave `human_trials` and `room_soak` as `NOT_RUN`, so `all_gates_passed` stays false even when `offline_gates_passed` is true. Synthetic positives and English audiobook negatives cannot establish Russian human/household performance. Packaging must retain the failed/unrun evidence and label such models experimental.

The historical pilot illustrates why these checks remain separate. The frozen model `20b28cd466a8c65aee5ac827b3e6a6d492b73645a510dffb2aacd81e1ae591eb` at cutoff 0.90 detected 400/400 held-out synthetic positives, but also **2/250 hard negatives**; zero-negative acceptance therefore failed. It produced zero events over 3,601.99 seconds of concatenated held-out English speech. Strict TensorFlow/Go comparisons also failed (maximum differences 2 and 16 raw units on two validation traces), although their 0.90 decisions agreed. A later human wake attempt did not establish successful activation. No passing human or room-soak result is claimed. Historical recordings and raw logs remain private and are not included here.

See [THIRD_PARTY.md](THIRD_PARTY.md) for pinned source and dependency licensing.
