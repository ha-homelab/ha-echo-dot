# Record owner wake words on macOS

This local browser application collects deliberate, repeatable voice recordings for two separate targets: **Мышка** and **Привет, Мышка**. The user controls every start and stop. It does not record through Echo, change Home Assistant, upload audio, or deploy a detector.

## Start the recorder

Requirements: Python 3, `ffmpeg` on PATH, and a current desktop browser with microphone permission. The collection server needs no training environment or third-party Python packages.

From the repository root:

```bash
python3 training/recorder/server.py
```

Open **http://127.0.0.1:8766** on the same Mac. Keep the server running while collecting. `Ctrl+C` stops a foreground server. Restarting with the same data directory resumes saved progress. A browser page loaded before a server restart must be refreshed because the local access token changes.

The default data directory is `private/mac-wakeword-recordings/`, already excluded from Git and the public allowlist. An explicit alternative must also be private:

```bash
python3 training/recorder/server.py --data-dir /absolute/private/collection --port 8766
```

If Codex's embedded browser or a browser extension blocks localhost or microphone access, open the local URL yourself in the normal Safari or Chrome browser. Do not disable browser security protections. When needed, allow that browser under **macOS System Settings → Privacy & Security → Microphone** and allow the microphone for this local page. Prefer the Mac's built-in microphone rather than a Bluetooth headset. The page's microphone-list button briefly obtains permission to enumerate device names, then stops its tracks without recording.

## Participant workflow

The interface, instructions, recording cues, status messages and documentation are English. Only the phrases to say remain in Russian, including similar words and everyday commands.

1. Select **1. Training**. Start in a quiet room approximately 40–60 cm from the Mac. The first click on **Record** opens the session automatically; there is no separate session-start confirmation.
2. Read the displayed phrase and intonation cue. Click **Record**. Wait for **SPEAK — recording**. Do not speak while the permission dialog is open.
3. Leave about half a second of quiet, say the phrase once in a comfortable voice, leave another half-second, then click the **same button**, now labelled **Stop**.
4. The page saves immediately, advances to the next prompt, and returns the button to **Record**. It never starts the next recording automatically. There are no review, retake or next-phrase buttons in the participant flow. The attempt list is read-only.
5. Complete the entire **Мышка** batch before the **Привет, Мышка** batch begins, then record the shared negatives. In TRAIN this means 24 short-word attempts, then 24 full-phrase attempts, then 12 negatives. The current batch and attempt counter remain visible. Only the intonation/distance cue varies within a target batch.
6. Progress survives page reloads and server restarts; take breaks whenever needed. On the last saved prompt the session is automatically marked ready for analysis. Tell the assistant which session is ready. The marker does not silently start an agent, upload audio or train a model.
7. Before **2. Validation** and **3. Final test**, take a real break and change position slightly. The first recording in each tab opens its own immutable session/split. The software cannot verify that the participant actually took a break. Prefer a later session/day for the final control set.

The initial protocol contains 108 prompts: TRAIN has 24 recordings of each target plus 12 shared negatives; VAL and TEST each have 8 recordings of each target plus 8 negatives. There are **40 recordings per displayed target phrase and 28 shared negative phrases**. This is a starting collection, not a statistical guarantee or a claim that 28 negatives replace a long room-noise test. Normal voice is deliberately emphasized; there is no need to imitate an artificially high pitch.

A single recording is capped at 12 seconds in the audio worklet. Leaving the tab stops active capture; closing it releases the browser's microphone. Wait for the save receipt before closing. If saving fails, the microphone is already off and the WAV remains in the page. The same main button becomes **Retry save**; an exceptional backup-download link is also available. Retrying uses the same take ID, so a timed-out but successful save is recovered without duplication or a skipped prompt. A rejected invalid WAV leaves the current prompt in place for a fresh recording. An unsaved in-memory attempt cannot survive a browser crash.

## Format, privacy and provenance

The AudioWorklet collects mono PCM at the AudioContext's actual sample rate without sending sound to the speakers. Capture requests echo cancellation, noise suppression and automatic gain control to be off; actual browser settings and the microphone label are recorded so ignored constraints remain visible. Browser/OS processing cannot be ruled out from the request alone.

Each take stores an immutable `source.wav`, an anti-aliased `ffmpeg` conversion to mono 16 kHz PCM16 `audio.wav`, SHA-256 hashes, recording time, intended prompt, intended target labels, source format, microphone settings and level/clipping/duration checks. The campaign selects attempts separately. These checks do **not** recognize words and are not an acoustic model evaluation.

`content_review` starts as `pending`. Intended text is never automatically promoted to a verified transcript. Incorrect attempts and silence must not become negative training examples merely because recognition failed. Source WAVs and manifests stay private, with restrictive filesystem permissions when the server is launched normally. No external scripts, analytics or cloud requests are used. The server binds only to IPv4 loopback, checks Host/Origin, and requires a fresh per-process token for data endpoints; it does not serve arbitrary files.

Participant-supplied labels are a separate evidence source. If the participant explicitly confirms correct prompted recordings, an experiment can retain those labels through `training/recordings.py`, with a private attestation, source hashes and any local ASR disagreements recorded alongside the import. This is **not** independent operator transcription: do not mark `content_review` as operator-verified without that review. The owner experiment in the training history used this explicitly documented participant-label path; the strict reviewed-export command below remains unchanged.

Browser microphone access requires a secure context; browsers treat localhost as a supported local context. References: [getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet), [AudioWorklet sample rate](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletGlobalScope/sampleRate).

## Review and import, after recording

Run the quality summary without any microphone or network access:

```bash
python3 training/recorder/review.py \
  --data-dir private/mac-wakeword-recordings summary
```

Listen locally and, where useful, run local ASR for assistance. Verify the actual complete utterance, background interference, cut-off syllables and clipping. ASR text is a hypothesis, not automatic approval. Review an accepted take by its ID from `campaign.json`:

```bash
python3 training/recorder/review.py \
  --data-dir private/mac-wakeword-recordings review \
  --take TAKE_ID --transcript 'Привет, Мышка'
```

The two detectors require different labels. Complete **Мышка** is positive for the short detector, including when spoken inside **Привет, Мышка**. Standalone **Мышка** is negative for the long detector. **Мишка**, **Миша**, and other listed near misses are negative for both. A short acoustic detector cannot infer whether a mention of the exact word was intended as a command; selecting the short phrase accepts that limitation.

Export refuses selected unreviewed or changed recordings and derives labels from the explicitly verified transcript. It uses the existing hash- and split-checking importer. TRAIN and VAL are imported by default; TEST remains excluded:

```bash
python3 training/recorder/review.py \
  --data-dir private/mac-wakeword-recordings export \
  --destination private/mac-owner-import-v1
```

This creates separate `myshka/recordings/manifest.jsonl` and `privet_myshka/recordings/manifest.jsonl` datasets. `--include-frozen-test` explicitly includes reviewed TEST recordings for final evaluation after the model and threshold have been fixed. Never score or use the frozen test for candidate selection. All descendants/crops of a source must keep its original split; copying the WAV or changing its filename does not create a holdout.

Original clips can be longer than the model's 2.5-second context. If silence trimming is necessary, preserve the source, document a complete-word/complete-phrase crop and its hash, and keep its split. Do not cut syllables to satisfy the context size. Exporting imports audio only; it neither extracts features nor trains.

## Train the two candidates and validate transfer

Follow the existing [staged training workflow](../README.md), using fresh private work directories and immutable candidate IDs:

- **Short target:** [myshka.json](../configs/myshka.json), synthesis profile `m-v1`. Its source vocabulary is separate from the long-phrase profile; old long-phrase negatives containing the full word must not be reused as short-target negatives. This profile has been synthesized and trained experimentally; it has not passed deployment acceptance.
- **Long target adaptation:** [privet-myshka-owner.json](../configs/privet-myshka-owner.json), profile `pm-v1`, proposed ID `privet_myshka_owner_v2`, reduced learning rate. Use the existing matching checkpoint only after verifying its hash and architecture with the supported warm-start arguments. The initial checkpoint remains eligible so an unsuccessful fine-tuning run cannot be called an improvement.

Sequence: verify/import all intended TRAIN and VAL audio → extract real features in a new work directory → train with recordings and correct synthetic/background data → export → exact-Go structural/inference and strict parity checks → streaming evaluation/calibration on VAL → freeze model bytes and threshold → evaluate untouched TEST → test ordinary live speech on Echo. Keep observed parity failures visible; do not silently weaken a failing check.

Mac recordings have a different acoustic path from Echo's microphone array. Training success or held-out Mac accuracy alone does not prove far-field Echo performance. Validate both false rejections and false activations on Echo at realistic distances, then add targeted on-device recordings if the remaining failure is device-specific. Keep Okay Nabu as the fallback and compare short/long candidates separately before choosing slot 2. No deployment or threshold change is performed by this recorder.

## Verification

```bash
python3 -m unittest discover -s training/recorder -p 'test_*.py' -v
node --check training/recorder/web/app.js
node --check training/recorder/web/capture.js
```

The browser smoke test requires Playwright and Chrome (`CHROME_PATH` may override its executable). It uses a generated sine-wave file as a **fake microphone**, an isolated temporary dataset, and an ephemeral local port. It never captures the real microphone:

```bash
node training/recorder/test_browser.cjs
```

It covers no capture on load, one-button start/stop, automatic prompt advancement, the boundary between all 24 short-word prompts and the first full-phrase prompt, 16 kHz saved audio, microphone-track release, reload/resume, failed-save recovery, automatic 12-second stop, automatic idempotent session completion, and browser JavaScript errors. The Python tests cover source conversion, idempotent retry, retake selection, persistence, duplicate/split rejection, transcript-review gates, final-test exclusion and loopback access restrictions. These are recorder tests, not evidence of a trained detector's accuracy.

## Restarting an existing collection with a new prompt order

The English interface can resume an existing campaign with the original Russian hints. It translates known hints for display and compatibility checks without rewriting saved campaign data, changing prompt IDs or moving recordings between splits. This presentation-only update does not require a new campaign.

The server still refuses a changed collection plan (phrases, labels, order or splits) in an existing campaign. Stop that collection server, move its entire data directory to a new private archive name, and start a fresh campaign. Retain source audio, metadata, selection history and session IDs together; do not delete previous voice samples or silently reassign their splits. The owner-requested batch restart used this approach. Archived and new recordings must be audited together for provenance before any future reuse; archived TRAIN audio is never a new holdout.
