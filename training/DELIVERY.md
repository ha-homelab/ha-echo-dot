# Real recordings and model delivery

These two standard-library Python tools cover deliberate recording import and
the final packaging/staging steps. They do not access a microphone, discover
credentials, call Home Assistant, or select a wake-word slot.

The initial Russian candidate remains experimental. Its held-out hard-negative
test produced 2 false activations in 250 clips, strict numerical parity failed,
and the first human trial did not recognize the custom phrase. A later 0.70
sensitivity trial is a different operating point from the frozen 0.90 test.
Successful installation and synthetic recall do not resolve those failures.

## Import deliberate real-voice recordings

Use pseudonymous speaker labels. Record short, intentional clips and export
uncompressed **mono 16 kHz PCM16 WAV**. Importing reads an existing file; it never
starts recording. Clips must contain audio and be at most 30 seconds long.

Choose split assignments before recording. Give each acquisition session a
globally unique label, including when several people participate in that session.
All clips and derived augmentations from a session belong to the same split.
Keep the test sessions unavailable to training and threshold selection.

```sh
python3 training/recordings.py import \
  --work-dir /path/to/private-work \
  --wav /path/to/deliberate-clip.wav \
  --speaker speaker-01 --session session-01 \
  --split train --label positive \
  --transcript 'Привет, Мышка' --max-seconds 8

python3 training/recordings.py check --work-dir /path/to/private-work
```

Repeat with separate `val` and `test` sessions. Include negatives containing
similar phrases and natural speech; use `--label negative` and transcribe what
was actually said. Non-speech negatives may omit `--transcript`. A positive is a
clip containing the intended wake phrase, not merely a clip from the intended
speaker.

By default, the same speaker may appear in different sessions across splits.
The checker reports this as **known-speaker session evaluation**. It is useful
for personalization and does not demonstrate generalization to unseen speakers.
Pass `--split-by speaker` on every import and check to additionally enforce
disjoint speakers within this imported dataset. Checks cover this manifest;
synthetic voices and other datasets still need their own leakage audit.

The importer rejects a session crossing splits, duplicate PCM audio with changed
metadata, invalid sample formats, and checksum failures. Importing exactly the
same audio with exactly the same metadata is idempotent. It normalizes the WAV
container without resampling or modifying samples. It does not silently move,
relabel, overwrite or delete an existing recording. New audio and manifests use
private filesystem permissions where the platform supports them.

Output contract:

- Index: `WORK/recordings/manifest.jsonl`.
- **Manifest path base:** `WORK/recordings`.
- Audio: `audio/<full-pcm-sha256>.wav` relative to that base.
- Pipeline fields: `source_id`, `path`, `split` (`train`, `val`, `test`), `label`
  (1 positive, 0 negative), `voice`, `text`, `duration`, and `sha256`.
- Provenance: `speaker`, `session`, `source_kind=real_recording`, `pcm_sha256`,
  `samples`, `sample_rate`, `channels`, `sample_width_bytes`, and import time.
- `voice` aliases `speaker`; `text` aliases `transcript`; `source_id` and `id`
  are `real-<full-pcm-sha256>`.

Feed these WAVs to the same pinned Go frontend used for synthetic data and
evaluation. Preserve split and source/session provenance through augmentation.
Do not independently split augmented variants or move a failed held-out clip
into training while continuing to claim that old test as unseen. Add new held-out
sessions when the model or threshold is revised in response to test results.

Raw voice recordings, transcripts and generated work files belong in a private
work directory. Packaging a model does not grant permission to publish its
training recordings or third-party model/data assets.

## Optional manual EchoLocal recording

Live device capture is deliberately outside these portable scripts. Existing
WAV import is the supported universal path. A supervised EchoLocal 0.0.8 session
can provide device-processed audio if a knowledgeable operator implements its
native API procedure, with an explicit device identity and pairing key.

The relevant native objects for the second slot are `keep_recordings_2`,
`max_listen_2`, and `wake_assistant_2`. Read and retain their actual starting
values. Start only when the satellite is idle and the speaker is ready; use one
manually triggered, bounded turn so the failing wake word is included in the
recording. A natural wake-triggered turn can omit the wake phrase itself.

An operator would temporarily enable retention for that one turn, set a short
listen limit, compare recording IDs before and after it, and retrieve only the
new turn through `recordings` and paginated `turn_audio`. Preserve the original
settings and restore retention and listen limits in a `finally` path. Restoring
retention to zero deletes retained device recordings, so never assume zero or
reset another operator's retention setting. Do not activate unrelated slots,
change pipelines, enable broad logging, or run a second raw microphone consumer.

The public tools here do not implement or execute this procedure. See the
version-pinned upstream [recording implementation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/recording/recording.go),
[voice turn handling](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/voice/conversation.go),
and [wake-word controls](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/wakeword/wakeword.go)
before developing an adapter.

## Package the exact evaluated artifact

The candidate directory must contain the actual model and its version-2 micro
manifest with matching basenames:

```text
WORK/models/CANDIDATE/MODEL_ID.tflite
WORK/models/CANDIDATE/MODEL_ID.json
```

The sidecar must identify the spoken phrase, languages, model filename,
`micro.probability_cutoff`, `micro.sliding_window_size`, and
`micro.feature_step_size`. A training export can contain a provisional cutoff.
Packaging preserves that original sidecar byte-for-byte under `source/`, records
its hash and original cutoff, and uses explicit `--cutoff` to set only
`micro.probability_cutoff` in the delivered copy. The model bytes and training
artifact are unchanged. The frozen protocol and gate report must match the
selected cutoff. To change an evaluated operating point, freeze and evaluate a
new protocol first; packaging does not evaluate or optimize the threshold.

```sh
python3 training/delivery.py package \
  --work-dir /path/to/private-work \
  --candidate candidate-1 --model-id privet_myshka_v1 --cutoff 0.90 \
  --evaluation /path/to/private-work/evaluation/run-1/protocol.json \
  --evaluation /path/to/private-work/evaluation/run-1/test.json \
  --experimental

python3 training/delivery.py verify \
  --package /path/to/private-work/delivery/privet_myshka_v1
```

Repeat `--evaluation` for calibration, additional tests and failure reports.
The package preserves every supplied report byte-for-byte under `reports/`.
Include all relevant failures; do not use a convenient passing subset to claim
acceptance. Report files may themselves contain private paths or transcripts;
review them before sharing a package.

Output is the immutable directory `WORK/delivery/MODEL_ID`, containing the
model, delivered and source sidecars, reports, `manifest.json`, and
`manifest.sha256`. Every payload
has an exact size and SHA256. Verification checks them, rejects unexpected files
and symlinks, and recomputes the reported release status. SHA256 provides
integrity checks, not a digital signature or proof of model quality. The TFLite
header check is structural; exact-runtime evaluation remains a separate gate.

Without `--experimental`, a matching-model gate report must explicitly pass
**runtime, strict_parity, positive_recall, zero_negative_events,
negative_duration, clean_holdout, human_trials, and room_soak**, with
`all_gates_passed: true`. Its `cutoff` must match and its `protocol_sha256` must
identify frozen protocol bytes included among the reports. That protocol must
bind the same model hash, cutoff and sliding window, record the exact validator
hash, and report strict parity as passed. Missing, failed or
unrun gates block accepted packaging. Offline evaluation leaves human and room
gates unrun. `--experimental` preserves these facts; it never turns them into
passes. An explicit experimental flag keeps a package experimental even if all
supplied gates pass.

The output directory is never replaced. Use an immutable model ID for each
revision and preserve the old package and evidence.

## Stage files explicitly, then configure Home Assistant

Staging is an intentional filesystem write to the configuration directory you
supply. It copies only the verified `.tflite` and matching `.json` into
`custom_wake_words`. It does not copy recording data or evaluation reports into
Home Assistant.

```sh
python3 training/delivery.py stage \
  --package /path/to/private-work/delivery/privet_myshka_v1 \
  --ha-config-dir /path/to/home-assistant-config \
  --experimental
```

The configuration directory must already exist. Experimental staging requires
`--experimental` again. Identical installed bytes are idempotent; different bytes
under the same ID are rejected. The filesystem must support hard links within
the configuration directory so staging can create complete files without
overwriting a concurrent writer. The manifest is created after the model.

In Home Assistant 2026.9.1, the custom wake-word catalogue is cached and its HTTP
route is registered during setup. Merely copying files or reloading one ESPHome
entry does not reliably discover a new custom model. Coordinate a Home Assistant
restart after staging when using the standard canonical-directory path. These
scripts never restart Home Assistant. A native offer/download adapter can avoid
a restart, but requires separate, version-specific integration code and an HTTP
URL reachable from the Echo; that site-specific procedure is not bundled here.

After discovery, use the paired Echo's ESPHome device page to select the custom
word for the **second** wake-word slot, select the intended Assist pipeline for
the second Assistant slot, and explicitly set that slot's sensitivity to the
evaluated cutoff. Preserve the working first slot. EchoLocal 0.0.8 uses the
per-slot sensitivity setting; copying `probability_cutoff` in the sidecar does
not configure that runtime value. A model download may fail if the Echo cannot
reach the Home Assistant URL serving the manifest and model.

Confirm the model's ID, size/hash and slot settings, then perform deliberate
human trials from idle and a separate realistic room/TV/music soak. A model
appearing in a selector proves availability, not acoustic acceptance. If trials
fail, restore the previously working second-slot selection/settings; retain the
artifact and failure evidence for analysis. This tool does not perform live
activation or rollback.

See [Home Assistant integration setup](../research/ha-integration.md) for pairing,
Assist pipelines and network prerequisites, the pinned
[Home Assistant custom wake-word loader](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/esphome/assist_satellite.py),
and EchoLocal's [external model download](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/external.go)
and [model loading](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/models.go).
