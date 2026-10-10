# A Russian wake word for EchoLocal

Changing **Okay Nabu** to **«Привет, Мышка»** requires a detector trained for that phrase. Renaming a selector, editing a manifest's display text, or choosing Russian in Assist does not change what an existing model recognizes. Wake detection runs on the Echo; the selected Assist pipeline handles the subsequent command and reply. Start with the working [Home Assistant integration](../research/ha-integration.md).

For commands, follow the [complete staged training workflow](../training/README.md). It implements source preparation, training/export, exact-runtime validation, threshold calibration, an immutable final test, personal-recording import and verified HA file staging. The [training history](training-history.md) records what actually ran and which checks remain failed or unconfirmed. This page explains the model and HA integration requirements behind those commands.

**Last observed deployment, 2026-10-08 Pacific / 2026-10-09 UTC:** both Dots used slot 1 **Okay Nabu / 0.95** and slot 2 **Привет, Мышка / 0.90**, with the existing `privet_myshka_v1` artifact and **FCC Russian Backup** in both slots. The thresholds were raised after native logs confirmed unwanted detections at the former 0.85 / 0.35 settings. Both devices' model bytes matched; `myshka_owner_raw_v1` was inactive at that checkpoint. This is a conservative false-activation mitigation, not retraining or acoustic acceptance. The higher cutoff can miss genuine utterances, especially given the long model's poor recorded owner recall. See the [incident and verification record](operations-findings.md#unwanted-wake-activations--2026-10-08-pacific--2026-10-09-utc).

**Historical rollback, 2026-10-04 UTC:** the owner reported frequent false activations from `myshka_owner_raw_v1` in a nearly quiet room and requested rollback. Both devices then used slot 1 **Okay Nabu / 0.85** and slot 2 **Привет, Мышка / 0.35**. The long model was restored on the first Dot and, at the owner's explicit request, also installed on the second. These historical thresholds are superseded above. See the [rollback record](training-history.md#rollback-after-false-activations-2026-10-04-utc).

**Owner collection, 2026-10-03:** the [Mac recording studio](../training/recorder/README.md) collected 108 user-controlled recordings across three separate sessions for standalone **Мышка**, **Привет, Мышка**, and negatives. The short word is also present inside the longer phrase. The [training history](training-history.md#owner-controlled-mac-collection-and-adaptation-2026-10-03) records the completed adaptation and its limits.

**New target, 2026-10-02:** a separate [Привет, котик recipe](../training/configs/privet-kotik.json) now uses its own synthesis vocabulary and data partitions. Its first candidate is trained and evaluated but remains undeployed, with two hard-negative errors and failed strict numerical parity. The installed-model details below describe Myshka; the [Kotik stage record](training-history.md#new-target-привет-котик) records the new candidate separately.

**Experiment status, 2026-10-01:** the model was trained, evaluated with the exact EchoLocal runtime, downloaded to the pilot Echo Dot 2, and activated in slot 2 with the existing Russian Assist pipeline. Slot 1 still uses Okay Nabu. Home Assistant was not restarted. Human spoken acceptance of the new phrase and room-noise testing remain pending; the earlier Okay Nabu → Russian Assist exchange was already demonstrated.

**Historical human feedback:** the owner reported that the earlier long phrase was not understood. HA correctly transcribed it during an Okay Nabu conversation, but that did not demonstrate independent custom activation. Temporary second-slot trials used **0.70**, and later **0.35**; the recorded offline evaluation below remains frozen at **0.90**. The short-word model was inactive at the latest recorded checkpoint; neither its threshold nor the historical 0.35 setting should be restored automatically.

This guide targets **EchoLocal 0.0.8** and **Home Assistant Core 2026.9.1**. Their behavior is pinned below; recheck it when changing versions. EchoLocal provides two wake-word slots, each paired with its own assistant and settings. Keep the working first slot as a fallback while evaluating the Russian phrase in slot 2. [Two-slot implementation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/wakeword/wakeword.go).

## Recorded result and limits

The historical long-phrase artifact is `privet_myshka_v1`, 51,344 bytes, SHA-256 `20b28cd466a8c65aee5ac827b3e6a6d492b73645a510dffb2aacd81e1ae591eb`. It uses a 10 ms feature hop, stride 3, an averaging window of 5 scores, and an initially deployed threshold of **0.90**. This threshold was fixed on validation before the final test; it is not a universal recommendation for other models.

With the exact deployed Go runtime, validation detected 400/400 synthetic positives, produced no events on 250 synthetic negatives at that threshold, and produced no events on 3,872.485 seconds of held-out clean speech. The final independent test detected 400/400 synthetic positives but produced **2 events on 250 negative clips**: one rendering each of **«Компьютер не видит мышку»** and **«Привет, мышь»**. A separate 3,601.99-second clean-speech test produced no events. The threshold was not adjusted to eliminate these test errors.

The long speech checks concatenated complete LibriSpeech utterances with continuous frontend/model state; they were not recordings of a household room, TV, or music. Synthetic positive splits share four TTS voices, so perfect synthetic recall does not establish recognition of a new human speaker. This is a controlled second-slot trial, not production acoustic acceptance. The real-speech source and its CC BY 4.0 attribution are documented by [LibriSpeech / OpenSLR](https://www.openslr.org/12).

Graph, quantization, explicit Go inference, and public-detector consistency checks passed. TensorFlow Lite and Go were **not byte-identical** on every trace: the strict one-output-unit comparison failed on two Russian examples, with maximum differences of 2 and 16 raw UINT8 units. Both runtimes made the same 0.90 threshold-side decision at every compared step in those traces. Calibration and the reported acoustic tests used Go directly; no interpreter patch or silently relaxed parity tolerance was used.

## 1. Establish the model contract before training

Use a streaming, quantized **microWakeWord** TFLite model with internal streaming state and a matching JSON sidecar. A valid `.tflite` container or successful TensorFlow inference is insufficient: EchoLocal uses a small Go interpreter with a specific operator implementation. Release 0.0.8 pins `github.com/zserge/microwakeword` to `bfaf3840114ece54665c15e6e202ddb1463c3d37`. [EchoLocal dependency pin](https://github.com/ygelfand/echolocal/blob/0.0.8/go.mod).

For this workflow, validate a single INT8 input shaped `[1, stride, 40]`, a single UINT8 output score, static tensor shapes, quantization parameters, and every operator in every subgraph. The intended export uses input scale approximately `26/255`, input zero point `-128`, output scale `1/256`, and output zero point `0`; verify the actual exported model. Reject a trainer's fallback to float or nonstreaming output.

The pinned interpreter implements `CALL_ONCE`, `VAR_HANDLE`, `READ_VARIABLE`, `ASSIGN_VARIABLE`, `RESHAPE`, `CONCATENATION`, `STRIDED_SLICE`, `CONV_2D`, `DEPTHWISE_CONV_2D`, `FULLY_CONNECTED`, `LOGISTIC`, `QUANTIZE`, and `SPLIT_V`. A familiar architecture name does not guarantee that its converted graph uses only these operators or supported options. Check initialization and repeated inference with the exact Go revision, including explicit `Invoke()` errors: the public detector returns no detection when inference fails. [Operator dispatch](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/interpreter/ops.go), [detector behavior](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/microwakeword.go).

Use an immutable model ID such as `privet_myshka_v1`, with matching `privet_myshka_v1.json` and `privet_myshka_v1.tflite`. The sidecar needs `type: "micro"`, `wake_word: "Привет, Мышка"`, the model filename, `trained_languages: ["ru"]`, and the actual `micro.feature_step_size` and `micro.sliding_window_size`. Preserve additional exporter metadata. EchoLocal reads the feature step and averaging window but deliberately ignores the manifest's `probability_cutoff`; the per-slot Home Assistant control supplies that threshold. [Manifest interpretation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/models.go).

## 2. Match audio features to the deployed runtime

The reference frontend consumes mono 16 kHz audio, uses 30 ms windows and 40 frequency channels over 125–7500 Hz, and supports the configured feature hop. This experiment uses a 10 ms hop. Its raw features are packed as `clip((raw * 256 + 333) / 666 - 128, -128, 127)` with integer division. [Go frontend](https://github.com/zserge/microwakeword/blob/bfaf3840114ece54665c15e6e202ddb1463c3d37/audiofrontend/frontend.go).

Do not assume Python/C `pymicro_features`, precomputed training arrays, and this Go frontend produce identical values. Local comparison against public reference audio found differences despite matching frame counts and nominal window settings. Before a long training run:

1. Feed the same unchanged PCM recording through both frontends; compare alignment, hop, scale, and values.
2. Feed identical quantized feature frames into TensorFlow Lite and the pinned Go interpreter; compare output bytes through initialization, steady streaming, and reset.
3. Test the complete Go audio-to-detection path. Match its sliding average calculation, which divides UINT8 scores by 255, when calibrating the deployed threshold.

Prefer extracting new training audio with the deployed frontend where practical. Existing background features require separate compatibility checks: the pinned `kahrendt/microwakeword` dataset card documents a **20 ms** hop and raw UINT16 values, with float scaling by `0.0390625`. Rescaling does not make those features equivalent to a different frontend or hop. Record any approximation and test its effect on held-out audio. [Pinned dataset description](https://huggingface.co/datasets/kahrendt/microwakeword/blob/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/README.md).

## 3. Prepare and inspect the data

An initial synthetic set uses 4,000 complete target-phrase recordings and 2,500 negatives across four Russian Piper voices. This is a starting experiment, not a recommended production minimum. Record each voice revision, model/config hashes, synthesis parameters, source ID, text, audio hash, and partition. Use cached native Piper sessions for generation; isolate dependencies and bound worker/thread counts. The inspected trainer is useful as a starting point, but its stock negative-window split and permissive export fallbacks need correction. [Pinned trainer](https://github.com/interkelstar/microwakeword-trainer/blob/8fdbadc3b969a8c1993108c0d655910440dfb762/train_mww.py).

Positives must retain both words. Include normal punctuation and intonation variants of the complete phrase. Useful negatives include **«Привет, Миша»**, **«Привет, Мишка»**, **«Мышка»**, **«Привет»**, **«Где моя мышка?»**, ordinary commands, conversation, music, and room noise. Avoid labeling the exact target phrase as negative merely because it occurs in a conversation: the acoustic detector cannot infer the speaker's intention.

Generate a small audition set first. Listen to every voice and inspect stress, pronunciation, pauses, clipping, silence, and duration. Preserve complete utterances as 16 kHz mono PCM16; add room/noise augmentation later. The initial positive set measured 0.708–2.183 seconds, so a fixed 1.5-second crop would lose speech in some examples. A 2.5-second context covers those raw examples, but augmentation and real speech still need duration checks. Phoneme inspection alone is not human listening approval.

Assign **original recordings** to train/validation/test before augmentation. The initial synthetic partition is 80/10/10: 3,200/400/400 positives and 2,000/250/250 negatives. Keep every derived window and augmentation of one source in its original partition. Split long background audio by source recording/session, not by adjacent windows. Synthetic splits sharing TTS voices do not establish recognition of unseen real speakers.

## 4. Train, export, and evaluate independently

Record the actual optimizer-update count, configuration, dependencies, random seeds, checkpoints, data manifests, and final artifact hashes. Use a bounded first run and benchmark the selected CPU/accelerator. Complete the exact-runtime export check before committing to a long run.

Choose the threshold and averaging window on a separate calibration set. Keep the final test set untouched while tuning. Evaluate complete audio streams, recording detected events and their timing; overlapping above-threshold windows are not independent false activations. Report missed utterances and false activations per hour with the amount of audio tested.

Before acceptance, use real recordings from separate sessions: different speakers, near/far positions, quiet speech, normal conversation, TV/music, and the near-miss phrases above. A practical initial check includes 40–60 real positive utterances, 80–150 difficult negatives, and at least one hour of continuous background audio. These counts are a starting protocol, not a statistical reliability guarantee. If failures become training data for the next revision, reserve a new independent test set.

## 5. Make the validated model available to the Echo

### Standard Home Assistant catalog

Place the matching pair in the Home Assistant configuration directory:

```text
<HA_CONFIG>/custom_wake_words/privet_myshka_v1.json
<HA_CONFIG>/custom_wake_words/privet_myshka_v1.tflite
```

HA 2026.9.1 scans same-basename pairs, calculates the model's byte size and SHA-256, and offers a manifest under `/api/esphome/wake_words/<id>.json`. The Echo must be able to fetch the manifest and sibling model from the offered HA URL. ESPHome API connectivity alone does not prove this HTTP path works. [Catalog implementation](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/esphome/assist_satellite.py#L891).

For this pinned HA version, prepare the files before a coordinated HA restart. Its catalog is cached globally, and directory HTTP routes depend on setup-time registration. Reloading only an ESPHome entry is not a reliable way to discover newly added files, particularly if the directory did not exist at startup. Do not modify HA's internal caches or storage to bypass that lifecycle. [Singleton cache](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/helpers/singleton.py), [static-path registration](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/http/server.py).

### Controlled alternative without a global HA restart

This route was demonstrated on the pilot: stage, verified device download, target-entry reload, and second-slot activation succeeded without a global HA restart. It requires a small native-API client and a model URL reachable from the Echo; the site-specific helper remains private, and no turnkey HA action is claimed here.

1. Preserve the canonical pair above for a later normal HA startup. Serve an identical pair from an already available HTTP directory, for example `<HA_CONFIG>/www/echolocal_wake_words/<id>/`, exposed under `/local/echolocal_wake_words/<id>/`. These files are fetched without an HA login; place only the intended model and manifest there.
2. Authenticate to the intended Echo's native API with its existing individual encryption key. Verify device identity and capture both slots' current settings.
3. Advertise an external wake-word offer containing the immutable model ID, phrase, language, type, byte size, SHA-256, and manifest URL. Offering alone does not download the model: selection triggers adoption. Preserve `okay_nabu` in the active list; briefly selecting the candidate also arms it, so use an idle speaker and an explicitly configured second assistant.
4. Verify download and persistence, then return slot 2 to its previous disabled state if adoption and activation are separate steps. EchoLocal verifies size/hash, writes temporary files, and advertises installed models independently of external offers.
5. Reload only this Echo's ESPHome entry so HA learns the installed model. Explicitly select the phrase through HA's second-slot selector during activation: HA's slot mapping must agree with the device's active-ID list.

A target-entry reload may briefly interrupt that satellite. Validate the Echo's own successful fetch; a fetch from the HA host is not equivalent. On a timeout or partial failure, inspect state before retrying and restore the captured second-slot settings. [EchoLocal adoption](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/external.go), [installed/offered library](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/library.go), [HA slot selection](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/esphome/select.py).

## 6. Select slot 2 and perform the spoken test

In **Settings → Devices & services → ESPHome**, open the Echo and its configuration controls. Labels may appear under associated sub-devices.

1. Preserve the first **Assistant**, **Wake word: Okay Nabu**, and its current sensitivity value.
2. Set **Assistant 2** to an already tested Russian pipeline. **Russian Assist** is an example label here; select the pipeline that actually exists in your installation.
3. Set the second assistant's **Wake word sensitivity** to the evaluated cutoff, then choose **Wake word 2: Привет, Мышка** once the model is available.
4. Verify that the device reports exactly the intended two active model IDs and that HA shows the corresponding two slot selections.

Despite its UI name, sensitivity is a **threshold**: higher values require a stronger score; lower values admit more detections and potentially more false activations. EchoLocal 0.0.8 exposes 0.50–0.99 in steps of 0.01. Do not assume an example cutoff or the manifest value has been applied. [Threshold control](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/wakeword/wakeword.go#L90).

Say each activation phrase and a Russian command, confirm the intended assistant runs, and listen for the reply. Repeat across distances and background conditions. Then test reconnect/reboot recovery and normal-room false activations using the [acceptance checklist](acceptance-and-batch.md). Model download, selection, and an idle state do not demonstrate acoustic acceptance.

To stop the experiment, select **No wake word** for slot 2 and restore its previous assistant and threshold. Keep the first slot working. Removing an HA-hosted file does not remove the model already cached on the Echo; inactive artifacts can remain for inspection.

## Publication boundaries

This guide does not establish permission to redistribute the experiment's audio, datasets, checkpoints, or trained detector. Keep those artifacts and recordings private until the actual sources and intended release have been assessed. Publishing instructions is separate from publishing model/data assets, and this work does not authorize a public upload. Never include pairing keys, HA tokens, household recordings, device identities, or site-specific URLs in an export.

Record per-source terms rather than relying on a trainer repository's code license:

- Piper voice cards at the pinned revision list the **Dmitri/Denis training datasets as CC0**, **Irina as Unknown**, and **Ruslan as CC BY-NC-SA 4.0**. Those statements do not resolve every right in generated audio or a derived detector. [Dmitri](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/dmitri/medium/MODEL_CARD), [Denis](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/denis/medium/MODEL_CARD), [Irina](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/irina/medium/MODEL_CARD), [Ruslan](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/ruslan/medium/MODEL_CARD).
- The pinned precomputed-feature card declares **CC BY-NC 4.0** and identifies constituents including FMA, FSD50K, WHAM, LibriSpeech, VOiCES, CHiME6, and DiPCo. Track which exact archives and underlying partitions were used; the card's descriptions do not supply uniform per-recording rights. [Dataset card](https://huggingface.co/datasets/kahrendt/microwakeword/blob/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/README.md).
- FMA distinguishes MIT-licensed code, CC BY metadata, and audio distributed under each artist's chosen license. A cached music/noise archive or transformed spectrogram is not evidence of unrestricted publication. Preserve attribution and license records for the actual material used. [Pinned FMA license explanation](https://github.com/mdeff/fma/blob/607364e7d8263f890d23c838802f29637600611f/README.md#acknowledgments-and-licenses).

If a publicly distributable model is a goal, establish an appropriate source set and recording permissions before training that release; do not merely relabel the private experiment as redistributable. Follow the repository's [publication process](publication.md) for the documentation export.
