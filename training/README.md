# Train and evaluate Russian wake phrases for EchoLocal

This is the executable version of the [Russian wake-word experiment](../docs/custom-wake-word.md). It covers preparation, synthesis, feature extraction, training, export, exact-runtime checks, calibration, a frozen test, optional personal recordings, packaging, and Home Assistant installation. Commands are deliberately separate: completing training does not start a final test or change a speaker.

For user-controlled microphone collection on macOS, use the [local recording studio](recorder/README.md). It collects separate TRAIN/VAL/TEST sessions for **Мышка** and **Привет, Мышка**, saves private WAVs, and requires transcript review before importing either target.

The reference target is **Echo Dot 2 / EchoLocal 0.0.8**, using its pinned Go microWakeWord runtime. The default recipe trains **Привет, Мышка**. The separate [Привет, котик recipe](configs/privet-kotik.json) selects its own `pk-v1` synthesis vocabulary through `synthesis_profile`; the pipeline forwards that profile to generation and data verification. Changing only the display phrase does not train another phrase. A different target requires a reviewed synthesis vocabulary, pronunciation and negative examples as well.

**Current result:** all custom models remain experimental. The owner-adapted short-word detector recognized 15/16 held-out Mac utterances at a frozen 0.935 cutoff, but failed strict numerical parity and the required 100% recall. After deployment, the owner reported frequent false activations in a nearly quiet room and requested rollback. The short model is now inactive on both Dot 2 units. Each uses **Okay Nabu / 0.85** and the previous **Привет, Мышка / 0.35** model, with **FCC Russian Backup** preserved. The old long model was restored on the first device and explicitly requested for the second. Verified installation does not erase the older model's known misses or establish acoustic acceptance. Read the [training history](../docs/training-history.md) for the failed gates, field report and rollback evidence.

## Where each component runs

All commands through packaging run on a **training computer**, not on the Echo, Synology USB host, or Home Assistant. The reference computer uses Apple Silicon, macOS 14 or newer, Python 3.11.16 and CPU TensorFlow. The direct dependency list is provided for other compatible Unix hosts, but a fresh Linux installation has not been validated here. Go 1.26+, Git, `uv`, and `ffmpeg` are prerequisites. `setup` downloads Python packages and a pinned builder; it does not install those system tools.

Reserve approximately **50 GiB of free disk space** for the reference run. The retained historical work directory occupied about 36 GiB, including cached archives, features and models; future runs and personal recordings may require more. A new run also downloads several gigabytes of public data. See the [data provenance and source terms](data/README.md) before downloading.

Home Assistant needs the **ESPHome integration**, a paired EchoLocal satellite, and a working **Assist pipeline**. Russian recognition and speech synthesis belong to that pipeline. ESPHome Device Builder, HACS, a new HA training integration, and a separate wake-word server are not part of this route. Wake inference runs on the Echo. See [HA setup](../research/ha-integration.md).

After conversion, the Echo can use ordinary USB power. Training, model delivery and HA configuration use the network. A USB data connection to Synology or OpenWrt is only needed again for a USB maintenance/recovery procedure.

## 0. Create a private, immutable run

Start in the repository root. These shell variables contain only local paths and artifact names:

```bash
REPO="$PWD"
WORK="$REPO/private/wakeword-runs/myshka-v1"
CANDIDATE="candidate-2"
MODEL_ID="privet_myshka_v1"
RUN="candidate-2-evaluation"
export WORK
umask 077
python3 training/pipeline.py --work-dir "$WORK" doctor
```

Use a new `WORK` for changed source data or feature preparation. Keep it under ignored `private/` or outside a public checkout. Do not point this workflow at historical experiment files. A candidate name and an evaluation run ID are immutable within their work directory. A model ID must be new when deploying changed model bytes, because devices can cache installed IDs.

The recipe is [configs/privet-myshka.json](configs/privet-myshka.json). `setup` saves it to `WORK/recipe.json`. To use an edited recipe, copy it into a private file and pass `--config /absolute/path/recipe.json` **before the stage name** during setup. All later stages default to the saved recipe. Do not edit a recipe midway through a run.

For **Привет, котик**, use a new work directory and the matching profile from the start:

```bash
WORK="$REPO/private/wakeword-runs/kotik-v1"
CANDIDATE="candidate-1"
MODEL_ID="privet_kotik_v1"
RUN="candidate-1-evaluation"
python3 training/pipeline.py --work-dir "$WORK" \
  --config training/configs/privet-kotik.json setup --reference-lock
```

Continue the stages below with those variables. Regenerate phrase-specific speech and features: old Myshka positives are not Kotik positives. Cache reuse must record hashes and preserve source partitions. The historical Myshka results below do not measure the new phrase; Kotik needs its own calibration, held-out test and ordinary-voice acceptance.

For any stage, inspect the planned command or its options first:

```bash
python3 training/pipeline.py --work-dir "$WORK" --dry-run train --candidate "$CANDIDATE"
python3 training/pipeline.py train --help
```

`--dry-run` does not create a work directory, download, train, copy files to HA, or write a journal. Actual executed stages append their arguments, recipe hash and exit code to `WORK/stages.jsonl`. An interrupted process can leave partial output; the journal is not proof that an unrecorded stage completed.

## 1. Install the pinned environment and build the exact runtime

For the tested macOS ARM64 package set:

```bash
python3 training/pipeline.py --work-dir "$WORK" setup --reference-lock
uv pip check --python "$WORK/.venv/bin/python"
"$WORK/.venv/bin/python" training/test_dependency_security.py -v
python3 training/pipeline.py --work-dir "$WORK" build
```

On another compatible Unix host, omit `--reference-lock`; setup uses [requirements.txt](requirements.txt) instead of the complete [macOS lock](requirements-macos-arm64.lock.txt). It saves the actual package list as `environment-resolved.txt`. Run Python stages through the pipeline or `"$WORK/.venv/bin/python"`, not an unrelated system environment. Do not set `TF_USE_LEGACY_KERAS=1`.

The current environment pairs protobuf 5.29.6 with TensorFlow 2.18.1. Protobuf
4.25.9 is affected by [CVE-2026-0994](https://github.com/advisories/GHSA-7gcm-g887-7qv7),
and TensorFlow 2.16.2 requires protobuf below 5. Updating protobuf alone therefore
cannot produce a valid installation. The macOS lock also updates TensorBoard,
tf-keras and ml-dtypes to compatible versions while retaining unrelated pins.
Use a new work directory for the changed environment. Historical training and
accuracy results remain measurements of their original environment; they do not
validate a newly trained model or authorize a device update.

The updated lock passed a clean macOS ARM64/Python 3.11 installation and package
compatibility check, the nested-Any regression test, TensorFlow/Keras imports,
and the pinned builder's synthetic INT8/UINT8 export with exact-Go inference.
The regression test fails with protobuf 4.25.9 and passes with 5.29.6. No model
training, acoustic acceptance or device rollout is claimed by these checks.

Dependabot keeps TensorFlow and tf-keras on the validated 2.18 line, and SciPy
below 1.18 because the recipe requires Python 3.11 and NumPy 1.26.4. NumPy stays
below 2 and ml-dtypes below 0.6, whose package metadata requires NumPy 2.
TensorFlow 2.18 also requires protobuf below 6 and TensorBoard below 2.19.
Related TensorFlow packages update together. A new runtime line needs a complete lock,
package compatibility, security and builder/export parity checks before these
bounds change. Compatible patches remain eligible. Piper 1.8.0 is recorded in
both installation paths and the synthesis recipe; changed synthesis dependencies
require a new work directory, and do not validate historical acoustic results.

Host CI runs `python training/check_reference_lock.py` using uv 0.12.18. This
resolves every direct and locked dependency for Python 3.11 / macOS 14 ARM64,
rejects incompatible versions and missing transitive pins, and never installs
native packages. macOS 14 is explicit because the recorded ONNX Runtime wheel
requires it. This metadata check also runs on Linux; native imports and the
builder/export checks above are still required for a changed runtime.

The builder is `kahrendt/microWakeWord` at `a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0`. The Go validator imports `zserge/microwakeword` at `bfaf3840114ece54665c15e6e202ddb1463c3d37`, the revision used by EchoLocal 0.0.8. `build` creates `WORK/bin/validate`, `WORK/bin/gofeatures` and a source/binary hash receipt. It refuses to silently replace a changed validator in a recorded run.

**Complete when:** `environment.json`, `environment-resolved.txt`, `recipe.json` and `bin/build.json` exist, and both commands return zero. The exact runtime and frontend constraints are in [validation/COMPATIBILITY.md](validation/COMPATIBILITY.md).

## 2. Prove export compatibility, then choose compute

```bash
python3 training/pipeline.py --work-dir "$WORK" smoke
python3 training/pipeline.py --work-dir "$WORK" benchmark --device cpu
```

On a Mac with TensorFlow Metal installed, an optional independent benchmark is:

```bash
python3 training/pipeline.py --work-dir "$WORK" benchmark --device metal
```

The smoke model uses random features. It must convert to streaming INT8 input / UINT8 output, retain internal state, pass the operator checks and execute in the exact Go interpreter. It does **not** prove acoustic accuracy or numerical parity of a trained model. The historical CPU benchmark was faster than Metal for this small model; the training command therefore uses CPU.

**Complete when:** `smoke-export/export.json` and `go-structure.json` report a usable model, and `benchmark-cpu.json` records timing. Stop on a conversion/runtime error before downloading or training a full dataset. Outputs are not overwritten.

## 3. Download voices and audition a small synthesis set

```bash
python3 training/pipeline.py --work-dir "$WORK" voices
python3 training/pipeline.py --work-dir "$WORK" synth-smoke
python3 training/pipeline.py --work-dir "$WORK" verify-data --stage smoke
```

The voice download revision, file hashes, four voices and synthesis parameters are pinned in [data/recipe.py](data/recipe.py). Listen to the smoke WAVs under `WORK/data-generation/`, especially both words of the target, stress and pauses. Verify absence of clipping and incorrect pronunciation. Automatic format/duration checks cannot replace listening. Do this before the full synthesis command.

**Complete when:** source downloads verify, the small manifest passes checks, and the operator has auditioned the intended pronunciations. The scripts do not invent or record a human listening approval.

## 4. Generate partitioned speech and background data

```bash
python3 training/pipeline.py --work-dir "$WORK" synth-full
python3 training/pipeline.py --work-dir "$WORK" verify-data --stage full
python3 training/pipeline.py --work-dir "$WORK" background
python3 training/pipeline.py --work-dir "$WORK" librispeech --workers 4
python3 training/pipeline.py --work-dir "$WORK" features --workers 6
```

The full synthetic source set has **4,000 positives and 2,500 negatives**, partitioned before augmentation: train 3,200/2,000, validation 400/250, test 400/250. All derived windows stay with their original recording. The same four TTS voices occur across splits; this is not an unseen-speaker experiment.

Feature extraction produces three variants per training recording and one per validation/test recording: **16,900 windows**, each `[250,40]`. One training variant uses the C frontend; the other two and all held-out variants use the exact Go frontend. Go already emits float features in model units, so do not rescale them again. Augmentation retains complete positive speech after room reflections and refuses a phrase that cannot fit the context.

The auxiliary Hugging Face arrays produce 42,000/3,000/3,500 train/validation/test windows. They were generated with a C frontend and a **20 ms hop**; scaling their raw values by `1/25.6` is an explicitly recorded approximation, not equivalence to Go's 10 ms hop. LibriSpeech supplies 5,099/1,260/3,000 Go-feature windows with disjoint train/validation/test speaker groups. The independent final continuous-audio test does not use these precomputed test arrays.

**Complete when:** the verified source manifests, source/speaker split records, feature provenance and expected arrays exist under `data-generation/`, `background/`, `librispeech/` and `features/`. See [data/README.md](data/README.md) for per-command outputs, restart behavior and checksums. Downloads/extraction and selected feature jobs can resume verified progress; completed data is not silently regenerated. Fix a data definition in a new run instead of overwriting it.

## 5. Train a bounded candidate

```bash
python3 training/pipeline.py --work-dir "$WORK" train --candidate "$CANDIDATE"
```

The reference budget is at most **5,000 optimizer updates**, validation every 500, early stopping after four non-improving checks, and learning-rate reduction after two. Each batch contains 32 positives, 16 phrase-confusable negatives, four precomputed background windows and 12 LibriSpeech windows. Negative examples receive weight two. The best checkpoint is selected by weighted **validation** loss. Training reads no final-test feature arrays.

The command writes `models/CANDIDATE/recipe.json`, `history.json`, `best.weights.h5`, `evaluation-nonstreaming.json` and `training-complete.json`. The recipe records source-array hashes and the actual batch. Training completion is not streaming validation. `--without-librispeech` reproduces the earlier candidate-1 ablation; the reference candidate-2 path includes LibriSpeech.

**Complete when:** the completion receipt exists and records the checkpoint hash and actual update count. An interrupted candidate is retained for inspection; choose another candidate name instead of silently resuming optimizer state that was not saved.

## 6. Export and validate the trained model

```bash
python3 training/pipeline.py --work-dir "$WORK" export --candidate "$CANDIDATE"
MODEL="$WORK/models/$CANDIDATE/$MODEL_ID.tflite"
```

Export checks that weights, recipe and recorded train/validation features still match. It writes the streaming TFLite model and sidecar under `models/CANDIDATE/export/`. It publishes the pair at the candidate root only after the exact Go structural and repeated-inference check passes. It never falls back to float or a nonstreaming model. Inspect `export/export.json` and `export/go-structure.json`.

The JSON's initial **0.85** cutoff is provisional metadata. Calibration chooses the operating threshold; packaging later records that chosen value. EchoLocal additionally requires setting the slot's threshold in HA.

## 7. Compare trained-model output on validation traces

Select an existing **validation** WAV from the synthetic manifest or a separately recorded validation session. Test at least a positive and a difficult negative. For each selected file, set `WAV` to its actual path and give the trace a unique name:

```bash
WAV="/absolute/path/to/an/existing/validation-phrase.wav"
python3 training/pipeline.py --work-dir "$WORK" parity \
  --model "$MODEL" --wav "$WAV" --name positive-val --cutoff 0.90
```

Repeat with another WAV and `--name negative-val`. Reports live under `evaluation/parity/NAME/`. The wrapper adds three seconds of leading digital zero and one second of trailing zero, extracts the exact Go input frames, and compares TensorFlow Lite and Go on identical frames with persistent state.

**Exit 2 is a recorded strict numerical failure.** It must remain visible even when threshold decisions match. The allowed numerical difference is one UINT8 score unit. Inspect each `parity.json`; never treat a failed comparison as a success or modify the tolerance to conceal it. See [validation/README.md](validation/README.md) for frontend diagnostics and the comparison contract.

## 8. Prepare validation and untouched test manifests

These commands prepare audio and record hashes; they do not run final-test inference:

```bash
python3 training/pipeline.py --work-dir "$WORK" prepare-tts --split val
python3 training/pipeline.py --work-dir "$WORK" prepare-tts --split test
python3 training/pipeline.py --work-dir "$WORK" prepare-speech \
  --output-dir "$WORK/evaluation/audio/libri-val" --val-speakers
python3 training/pipeline.py --work-dir "$WORK" prepare-speech \
  --output-dir "$WORK/evaluation/audio/libri-test" \
  --inventory "$WORK/librispeech/test_clean_continuous_at_least_1h.jsonl"
```

Use each `concatenated.jsonl` below to preserve streaming state across complete utterances. Do not also include its per-utterance manifest in the same evaluation. These long streams are joined clean English audiobook recordings, not ambient household recordings. Every independent manifest row resets frontend and model state.

## 9. Calibrate using validation only

Choose the acceptance criteria before examining scores. This example requires at least 98% positive recall, zero negative events, cutoff at least 0.85, and a five-score averaging window:

```bash
python3 training/pipeline.py --work-dir "$WORK" calibrate \
  --run-id "$RUN" --model "$MODEL" \
  --manifest "$WORK/evaluation/manifests/tts-val.jsonl" \
  --manifest "$WORK/evaluation/audio/libri-val/concatenated.jsonl" \
  --parity-report "$WORK/evaluation/parity/positive-val/parity.json" \
  --parity-report "$WORK/evaluation/parity/negative-val/parity.json" \
  --thresholds 0.85,0.90,0.92,0.95,0.97,0.99 --min-cutoff 0.85 --min-recall 0.98
```

Inspect `evaluation/RUN/calibration.json`. Exit 2 means no eligible cutoff or a failed strict parity gate. Thresholds listed in `eligible_cutoffs` met the acoustic validation criteria only; that list does not override a parity failure. If no cutoff qualifies, change training/data and create another candidate while preserving the test set.

## 10. Freeze the protocol before the final test

The following uses **0.90 only if calibration lists it as eligible**:

```bash
python3 training/pipeline.py --work-dir "$WORK" freeze --run-id "$RUN" --cutoff 0.90 \
  --test-manifest "$WORK/evaluation/manifests/tts-test.jsonl" \
  --test-manifest "$WORK/evaluation/audio/libri-test/concatenated.jsonl" \
  --min-test-negative-seconds 3600
```

If strict parity failed and you explicitly intend to measure the experimental model anyway, add `--evaluation-only` to this command. The failure stays in the immutable protocol and final report. This is how to investigate a failed gate, not obtain acceptance. Freeze rejects a cutoff that failed the validation criteria.

`protocol.json` plus its checksum lock model bytes, runtime binary, validation evidence, cutoff/window, test manifests, audio hashes and minimum negative duration. Do not replace files at those paths. Exact validation/test PCM overlap is rejected. Speaker/session separation still depends on preparing the dataset correctly.

## 11. Execute one frozen held-out test

```bash
python3 training/pipeline.py --work-dir "$WORK" test --run-id "$RUN"
```

This is the first final-test inference stage. It cannot accept a new cutoff. It reserves the holdout in a consumption ledger **before inference**, including runs that crash. `test.json` preserves per-gate results and links to the frozen protocol; exit 2 means an offline gate failed. A later diagnostic reuse requires an explicit reason and is labelled `reused_not_clean` rather than a new independent test.

**Complete when:** a report exists for the frozen bytes and operating point. Inspect every failed or unrun gate. Do not tune a threshold on this result and relabel the same audio as untouched. `human_trials` and `room_soak` remain `NOT_RUN` automatically, so an offline pass alone never becomes full acceptance.

## 12. Improve the model with real voice sessions

This is the next data path when synthetic recognition does not transfer to the owner. Import **existing recordings**; the importer does not start any microphone. Use short, uncompressed **PCM16 mono 16 kHz WAVs** and pseudonymous speaker/session IDs. For bounded Echo capture and retention choices, see [DELIVERY.md](DELIVERY.md).

Before collecting a series, verify one complete utterance and a usable start cue. EchoLocal 0.0.8 has a configurable per-slot wake tone; manual wake requests that tone, but an enabled setting does not prove the participant heard it. Red feedback can indicate timeout/failure, and the configured ring color/effect is not a universal recording indicator. Delayed chat messages are also unsuitable for precise synchronization. Agree on an audible or participant-controlled start, confirm it actually works, and retain a quiet margin after the final syllable. Never infer spoken content from the intended prompt, WAV duration, or a successful download. Keep unsuccessful attempts unlabelled until reviewed.

A longer capture may contain silence, unrelated speech, or an incomplete phrase at an edge. Keep the original immutable. Derive any complete-phrase crop into a new private file, recording source checksum and start/end times; never crop off a word to fit the model context. A timeout without an STT transcript does not prove either that the person stayed silent or that the target phrase was recorded correctly.

```bash
python3 training/pipeline.py --work-dir "$WORK" import-recording \
  --wav /absolute/path/train-phrase.wav --speaker speaker-a --session morning-01 \
  --split train --label positive --transcript 'Привет, Мышка'
python3 training/pipeline.py --work-dir "$WORK" import-recording \
  --wav /absolute/path/validation-phrase.wav --speaker speaker-a --session evening-02 \
  --split val --label positive --transcript 'Привет, Мышка'
"$WORK/.venv/bin/python" training/recordings.py check --work-dir "$WORK"
python3 training/pipeline.py --work-dir "$WORK" features-real
python3 training/pipeline.py --work-dir "$WORK" train --candidate personalized-1 --with-recordings
```

Import all intended positives and negatives before `features-real`; those arrays are immutable. Include near-miss phrases, distances and ordinary room conditions. All clips from a session stay in one split. The same person may contribute different sessions to train and validation/test for personal adaptation; that measures a known speaker in another session. `--split-by speaker` enforces the stricter unseen-speaker design. Identical PCM cannot cross partitions even if its WAV header or filename changes.

The training option mixes up to eight real positives and eight real negatives into each batch. It uses real validation arrays when present and never reads real test arrays. The input pipeline refuses a positive phrase that exceeds its approximately 2.5-second context; do not truncate one word to make it fit.

For short Mac recordings, an optional feature policy retains the original level and complete waveform instead of peak-normalizing and trimming it. Use a fresh work directory with **TRAIN/VAL only** imported:

```bash
python3 training/pipeline.py --work-dir "$WORK" features-real \
  --real-policy preserved-level-v1 --workers 4
```

This policy extracts the exact Go frontend after three seconds of leading digital silence, then retains 250 frames. Each TRAIN source contributes 12 deterministic variants: variant zero preserves its level; the others vary gain, tail, reflections and noise. VAL remains unaugmented. The complete source plus at least 20 ms of tail must fit the context; longer recordings are rejected, never automatically cut. All variants retain their source partition and do not increase the number of independent recordings. The historical policy remains the default. Record the chosen policy in feature receipts and compare **raw streaming VAL audio**, since a low nonstreaming feature loss can still conceal misses or false activations. Do not import or extract final TEST audio until the selected model and threshold are frozen.

To adapt an existing compatible checkpoint instead of starting from random weights, add both `--initial-weights /absolute/path/best.weights.h5` and `--initial-weights-sha256 THE_RECORDED_64_CHARACTER_SHA256` to the training command. The adjacent `recipe.json` must describe the same architecture; current and historical pilot formats are supported. Verify the source checksum before starting and use a smaller learning rate in a new private recipe. The optimizer is fresh; its old state is not resumed.

Warm-start training evaluates and saves the initial checkpoint at step 0. Later weights replace it only when validation loss improves. `baseline-validation.json` and `training-complete.json` record the baseline and selected step. A selected step of 0 means fine-tuning did not improve the selection metric. This nonstreaming comparison still needs exact-Go streaming validation and a fresh human test before any device replacement.

Repeat export, parity, calibration, freeze and test for the new candidate. Include real validation/test recordings in separate [evaluation manifests](validation/README.md#prepare-evaluation-audio-without-scoring-it): use `label: "positive"` or `"negative"`, the corresponding WAV path, `leading_ms: 3000` and `trailing_ms: 1000`. Preparing real features does not automatically add recordings to streaming evaluation. Retain the frozen old report. If you used old test failures during training decisions, collect a new final holdout; the scripts cannot detect human knowledge of a test outside their ledger.

## 13. Package, verify and make an explicit HA copy

A trial candidate with failed/unrun acceptance gates must be labelled experimental:

```bash
python3 training/pipeline.py --work-dir "$WORK" package \
  --candidate "$CANDIDATE" --model-id "$MODEL_ID" --cutoff 0.90 \
  --evaluation "$WORK/evaluation/$RUN/test.json" \
  --evaluation "$WORK/evaluation/$RUN/protocol.json" --experimental
"$WORK/.venv/bin/python" training/delivery.py verify --package "$WORK/delivery/$MODEL_ID"
```

Packaging verifies matching model/operating-point evidence, preserves source-sidecar bytes and reports, and sets the delivered sidecar's cutoff to the explicit calibrated value. It does not modify the training artifact. The package remains private: evaluation reports may contain local paths and recording metadata. Checksums establish local consistency, not independent signed certification.

Only when ready to write to the actual **existing local or mounted HA configuration directory**:

```bash
HA_CONFIG="/absolute/path/to/the/home-assistant/configuration"
python3 training/pipeline.py --work-dir "$WORK" stage-ha \
  --package "$WORK/delivery/$MODEL_ID" --ha-config-dir "$HA_CONFIG" --experimental
```

This command writes just the verified `.json`/`.tflite` pair to `HA_CONFIG/custom_wake_words/`. It has no HA credentials, network discovery, restart, activation or device flashing code. Repeated identical staging is allowed; conflicting files are refused. For remote HA, copy the verified pair through your established administration method into the real configuration volume. Do not copy private evaluation reports into an HTTP-served folder.

## 14. Register in HA, configure slot 2, and test the actual room

Follow [model delivery and HA controls](../docs/custom-wake-word.md#5-make-the-validated-model-available-to-the-echo) and [DELIVERY.md](DELIVERY.md). The standard HA 2026.9.1 catalog route requires preparing the files before a coordinated HA restart. A single ESPHome reload is not a reliable catalog refresh. A separate no-global-restart native-API procedure was demonstrated privately; these public scripts do not automate it.

In **Settings → Devices & services → ESPHome → your Echo**, preserve **slot 1: Okay Nabu** and its tested assistant. Select the working Russian Assist pipeline for **Assistant 2**, set that slot's **Wake word sensitivity** to the evaluated cutoff, then select the new phrase as **Wake word 2**. EchoLocal 0.0.8 ignores the sidecar's cutoff for runtime control, so verify the actual HA value. Lower values permit more detections and false activations.

First confirm model download and active slots, then independently say the custom wake phrase and a command. A correct STT transcript inside an Okay Nabu conversation does not prove custom wake detection. Record successes/misses at different distances, difficult negative activations, room-noise duration and reboot/reconnect behavior. Keep counts and untested conditions explicit. To roll back, restore the saved second-slot model, assistant and threshold; disable that slot only if it was previously empty. A Myshka-to-Kotik upgrade must retain the current Myshka baseline for rollback. The first slot remains the working fallback.

## Reproducibility and publication

This workflow makes inputs, stages, versions and failure states reproducible. It does not promise bit-identical model bytes across hardware, TensorFlow builds or changes to data preparation. The public feature stage also adds a complete-positive guard after reverb augmentation that was absent from the historical script; a new run is not asserted to reproduce the historical checksum.

The original refactor was checked with offline fixture tests, Go tests/vet, bounded feature extraction and a two-update training/export exercise. Those checks verify script integration, not acoustic quality. A later complete Kotik training/evaluation run is recorded separately in the [stage history](../docs/training-history.md#new-target-привет-котик); its failed and unrun gates remain explicit. Run the small source-based regression suites with:

```bash
python3 training/test_pipeline.py -v
python3 training/test_delivery.py -v
python3 training/test_warm_start.py -v
"$WORK/.venv/bin/python" -m unittest discover -s training/data -p 'test_*.py' -v
python3 -m unittest discover -s training/validation -p 'test_*.py' -v
(cd training/validation && go test ./... && go vet ./...)
```

Fixtures use temporary directories, generated samples and a local HTTP test server; they do not download external datasets or contact a device. Numerical data fixtures need NumPy and report skips if it is absent. Run each directory separately because the helper modules are standalone CLI modules.

Public source includes recipes, requirements, tests and documentation. Audio, voice models, trained detectors, checkpoints, feature arrays, private logs and reports stay out of the allowlist. Voice/dataset terms include unknown and non-commercial restrictions; this repository does not grant model redistribution rights. Read [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) and the [publication procedure](../docs/publication.md) before exporting.
