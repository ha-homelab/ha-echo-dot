# Operational findings and remaining limits

This record brings together the two-Dot configuration, voice diagnosis,
EchoLocal companion installation and ADB checks, with incident updates through
**October 8 Pacific / October 9 UTC, 2026**.
It is a dated deployment record. It does not imply that every feature has been
tested or that every issue listed below is fixed.

## Unwanted wake activations — 2026-10-08 Pacific / 2026-10-09 UTC

The owner reported both Dots activating without speech. Native detector logs
confirmed acoustic wake events before HA started recognition. The short
`myshka_owner_raw_v1` model was inactive on both; the active pair was
`okay_nabu` and `privet_myshka_v1`. Both installed executables remained EchoLocal
0.0.8. Reading the model files over ADB confirmed identical bytes on the two Dots:

- `okay_nabu.tflite`: 60,264 bytes, SHA-256
  `0689abe1912a95a3318a0d8cb2e67bad0cbcfe3e24dd6e050c75debddfb6f891`.
- `privet_myshka_v1.tflite`: 51,344 bytes, SHA-256
  `20b28cd466a8c65aee5ac827b3e6a6d492b73645a510dffb2aacd81e1ae591eb`.

The first Dot's available 44-minute log contained one custom-word detection at
startup, with peak/crossing score **0.443** against cutoff **0.35**. No HA voice
subscriber was connected yet, so that event did not open a conversation. The
second Dot's available 196-minute log contained two custom-word detections
(peaks **0.743** and **0.449**, cutoff **0.35**) and one Okay Nabu detection
(peak **0.921**, cutoff **0.85**). These three turns ended in recognition failure
or a listening timeout. No household audio was retained for this audit, so the
logs alone cannot establish what acoustic input caused each event. Counts from
these unequal retained windows are not a measured false-activation rate.

The low custom cutoff admits the observed weak detections. EchoLocal 0.0.8
invokes the wake callback when the detector score crosses its cutoff; it does
not first require a separate speech/VAD decision. Its 300 ms detector `Hold`
tracks the peak **after** the callback; it is not a 300 ms confirmation gate.
The subsequent 800 ms refractory interval only suppresses immediate repeats.
Changing HA end-of-speech VAD therefore does not directly fix these wake events.
See the pinned [detector implementation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/detect/engine.go).

Both Dots were changed through HA's existing number controls:

- Slot 1, Okay Nabu: **0.85 → 0.95**.
- Slot 2, Привет, Мышка: **0.35 → 0.90**.

These are conservative operating cutoffs above the observed incident peaks,
not probabilities of correctness or a newly validated calibration. Comparison
of all 62 native controls per device found only those two changes on each.
Both active model IDs and both FCC assistant selections were retained. ADB
readback of `/data/misc/echolocal/state.json` confirmed persistence. Follow-up
listening and recording retention remained zero. Existing differences in speaker
volume and denoising were left unchanged. No audio was recorded or played, no
model was retrained, and no firmware or provider was replaced.

### HA selector mismatch

HA initially displayed `no_wake_word` in both first-Dot selectors while the
native API and persisted state showed both models active. Reloading that
device's ESPHome config entry alone did not correct it. The HA selector code
restores its previous display selection and only automatically adopts a native
selection when there is exactly one active model; a two-model device can thus
remain misleadingly displayed as disabled.

Selecting Okay Nabu and then the custom phrase restored the native pair, but an
immediate config response left the second HA selector showing `no_wake_word`
during model activation. After verifying that both native models were loaded,
reselecting the custom phrase synchronized the display. All four HA selectors
then matched the native configuration. The brief first-slot selection cleared
and reloaded the second model; it was not a firmware reboot. This is an
operational recovery, not a patch to HA's selector synchronization.

### Acceptance and recurrence

After selector synchronization, a second passive observation covered **175 s**
of first-Dot logs and **180 s** of second-Dot logs. Neither contained a new wake
detection, near-miss event or turn start; both continued processing about
50 microphone frames per second. This short window confirms that detection was
running without an immediate recurrence. It does not establish an acceptable
long-term false-activation rate, and no attended spoken-phrase test was performed.

The change requires continued room-noise and attended phrase testing. The older
long model detected only **1/8** raw owner validation positives even at 0.35 in
the prior adaptation evaluation. Raising its cutoff cannot correct that weak
recall and can make genuine phrases harder to trigger. Do not restore 0.35 to
compensate without evaluating representative negatives. The frozen synthetic
results at 0.90 remain historical evidence, not proof of present household
reliability. See [training history](training-history.md).

For another incident:

1. Note the time, affected Dot, and whether it chirped/listened or only showed a
   ring effect. Read the native active IDs and thresholds as well as HA's display.
2. Fetch native `logs` and correlate `wake detected` (model, crossing, peak,
   cutoff) with `turn started` and the HA pipeline result. A button/API start or
   follow-up turn is not evidence of acoustic phrase detection.
3. Preserve private logs before restarting. Diagnose recognition/provider
   failures separately: a false wake can open an empty recognition turn, while
   the same generic error can also arise from an independent provider failure.
4. If a model continues firing, temporarily select **No wake word** for that
   slot and verify the native active list actually excludes it. The physical
   button remains available. Collect any additional labelled room audio only
   through an explicitly coordinated recording session, then use the
   [training/evaluation workflow](../training/README.md) before redeployment.

## Runtime identity and configuration

Both converted units are Echo Dot 2 / BISCUIT and report
`echod version 0.0.8 (6eff3b1, 2026-09-30T16:45:06Z)` from the installed executable.
The native device-info project-version field was empty during the latest query;
the advertised ESPHome compatibility version must not be reported as the
EchoLocal daemon version.

Both advertise the same **100 native entity definitions and 3 response services**.
The full contract, without identities or live values, is in the
[JSON reference](reference/echolocal-0.0.8-entities.json). Their earlier 62-entry
native setting comparison differed only in speaker volume: 26/30 versus 25/30.
There is no automatic configuration-sync mechanism implied by this comparison.
The practical settings and ranges are documented in [device controls](device-controls.md).

At the October 8 Pacific / October 9 UTC checkpoint, both assistant slots on
both Dots selected **FCC Russian Backup**. The active wake models were
**Okay Nabu** and **Привет, Мышка**, with cutoffs **0.95** and **0.90**
respectively, after the unwanted-activation incident above. The earlier 0.35
custom cutoff was outside the advertised 0.50–0.99 HA number range and was no
longer the deployed setting at that checkpoint.

The short **Мышка** candidate was removed from active use after the owner reported
frequent quiet-room false activations. Its files can remain in the model cache;
file presence does not mean active detection. Neither the new dashboard nor ADB
access constitutes retraining or acceptance of a replacement. See
[training history](training-history.md) and [custom wake words](custom-wake-word.md).

## Companion installation and dashboard

EchoLocal HACS **v0.0.7**, commit
`3b92d727f00b32ceca65442e984010fbad89ec04`, was installed through HACS as a custom
Integration repository. All **14 installed files** matched that release. The
integration loaded, its frontend was served, and the wake-word-library API
answered successfully on HA Core 2026.9.1.

Two device cards were added to **Overview → Media** (`/lovelace/media`), retaining
the five existing top-level media cards and all other views. The optional
`/echolocal` panel discovers exactly two satellites. The browser verified live
values, idle status, Diagnostics and historical Activity with Listen/Think/Reply
durations. No EchoLocal frontend or HA error was observed in the checked logs.

All **106 pre-existing select/number/switch states** across the Dots matched the
pre-install snapshot afterward. Recording retention remained **zero in all four
assistant slots**. The install did not change the provider, threshold, active
model, microphone tuning or media buffering.

Configuration snapshots and dashboard rollback copies are retained privately.
Installation and removal instructions are in the
[companion guide](echolocal-companion.md). The companion is optional; ESPHome
continues to provide the underlying device connection.

## ADB, ports and maintenance

Both Dots accepted root ADB connections on TCP 5555 without an authentication
challenge. The audit read system health, Android/EchoLocal logs, runtime paths,
the service state and model listings. A disposable file was sent, read back
byte-for-byte and removed on each device. Both runtime services reported
`running` / `resident`.

The **Remote adb** switch was off on both, yet a separate INPUT firewall rule
accepted TCP 5555. The switch's state did not reflect effective network
reachability. No firewall/authentication change was made; the origin and
persistence of that extra rule were not resolved by the audit.

The stock macOS ADB client returned `No route to host`; a bounded Python ADB
client on the same Mac succeeded, as did an earlier ADB check from the HA pod.
The particular macOS client problem remains undiagnosed. This is not evidence
that either Dot lacks network ADB, nor that the standard Mac command is working.

No usable device administration webpage was found. HTTP 80 was empty nginx;
HTTPS validation failed on 443; HTTP on 8080 failed. SSH/Telnet ports were
unreachable or filtered. The working web administration surface is HA's
companion dashboard. USB/Synology is not needed for routine Wi-Fi operation.

The installed hardware command tree exists, but raw microphone capture, speaker
stimulus tests, I2C writes, service restart, remount and firmware replacement
were not executed as part of this access audit. See
[ADB commands and operation boundaries](device-access.md#hardware-command-reference).

## Voice error: recognized activity is not recognized speech

A first-Dot button attempt at **20:43:36 UTC on October 4** failed in HA with
`stt-stream-failed`; the matching FCC speech-service result was **`no-speech`**.
VAD reported a **4.51 s** interval, but no transcript or intent was produced.
The music-command stage was not reached, so this attempt does not establish a
Plex playback failure. A VAD interval alone does not prove useful speech content.

A known synthetic speech clip passed through the same recognition service in
approximately **0.93 s**. That establishes that the service could transcribe the
probe at that time; it does not prove that the failed household recording was
audible, unclipped, complete, correctly timed or transcribable. The failed
attempt's audio had not been retained. No fix for this incident is claimed.

The next useful evidence is a participant-triggered, short retained turn from
the affected Dot. It must be clearly separated from wake-word training data.
The later armed capture timed out without a participant start and produced no
WAV; settings were restored. Do not infer that a person recorded a phrase from
an instruction or readiness message alone.

Earlier `provider-unavailable` incidents and exhausted Homeway allowance are
different failures. Correlate the HA run with the provider and device logs;
the generic red feedback and `stt-stream-failed` wrapper are not a root cause.
The [HA integration guide](../research/ha-integration.md) records the FCC switch.

## Timing, recordings and acceptance

Recordings become available only when their whole turn closes, which can be
later than the end of speech. Reducing retention to zero before exporting can
remove the device copy. Retention is a turn count; the recording buffer's
approximately 30-second cap differs from the configurable 60-second listening
maximum. The [controls reference](device-controls.md#fixed-limits-and-boundaries)
lists paging and timeout details.

One second-Dot wake-phrase attempt produced a private 7.66-second WAV with a
verified capture/restore receipt. It was not yet verified for utterance content
or accepted as a labelled training example at this checkpoint. No successful
first-Dot diagnostic WAV was established by the timed-out attempts. Existing
Mac training sessions and their train/validation/test split remain separate.

For music, distinguish speech-provider latency, reply playback, the music
command itself and Sendspin output timing. The assistant's Reply buffer is for
streamed speech, not a universal music-startup control. Existing analysis is in
[music latency](music-latency.md); neither installing the companion nor obtaining
root fixes audio glitches by itself.

## Cloud speech connection recovery — 2026-10-06

The recorded incident affected the shared FCC speech adapter used by both Dots.
Its existing process returned four 30-second timeouts (three recognition probes
and one synthesis probe). A fresh client in the same Pod, using the same cloud
functions and credential, completed recognition in 2.566 seconds and synthesis
in 2.369 seconds. The original process still timed out immediately afterward.
This supports a stale connection/session diagnosis; the initial trigger was
not established.

The [0.1.1 adapter implementation](https://github.com/ha-homelab/ha-echo-show-5/blob/114331a9ab17d484f8b738846ed8190eb69ec4f1/integrations/fcc-voice-backup/cloud_speech.py)
opens a dedicated TLS gRPC connection for each recognition request or complete
synthesis operation and closes it on success, failure or cancellation. It no
longer shares one process-lifetime connection across recognition and synthesis.
The recorded rollout verified the runtime source hash against the tested code.
Dot firmware, wake models, sensitivity, assistant selections and recording
retention were unchanged by that rollout.

Afterward, direct recognition probes took 1.874 and 1.527 seconds, and a complete
synthesis probe took 2.969 seconds. Synthetic HA runs using each Dot's device
context returned decodable, non-error answer audio. Their complete answers
became available 16.624 and 16.191 seconds after input ended, so long-answer
synthesis latency remained substantial. A recognition probe after a 35-second
idle gap also passed. The recorded checks included 41 bridge/audio tests and
five recovery-manifest tests.

A separate short text-to-speech/local-intent check, without recognition input,
returned fresh audio in 2.513 seconds. Repeating the same question in the other
device context returned the identical cached audio in 0.097 seconds; that cache
hit is not a cloud synthesis measurement.

These are historical observations, not a current service-health check. The
same incident window also contained no-speech results and conversation
provider timeouts; the connection fix does not establish that those causes
were resolved. Live probes used synthetic input and fetched audio without
speaker playback. No attended microphone/speaker acceptance test was completed;
private diagnostics and audio are not included here.

## Public evidence boundary

Public documentation contains versioned facts, generic paths, advertised
definitions, examples and validation limits. Live HA configurations, addresses,
MACs, serials, Noise PSKs, tokens, signed media URLs, personal transcripts,
audio, trained weights and identifying screenshots stay in ignored private
storage. The JSON contract intentionally exports no state values.

The October 4 documentation update queried entity metadata and binary version only.
It did not change device controls, activate a model, enable recording, restart
a Dot or modify the firewall. A future check should record its date/version and
update this ledger when an unresolved item is actually reproduced or fixed.
