# Operational findings and remaining limits

This record brings together the two-Dot configuration, voice diagnosis,
EchoLocal companion installation and ADB checks through **October 4, 2026**.
It is a dated deployment record. It does not imply that every feature has been
tested or that every issue listed below is fixed.

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

Both assistant slots on both Dots select **FCC Russian Backup**. The active
wake models are **Okay Nabu** and **Привет, Мышка**. The latter's stored 0.35
cutoff is outside the advertised 0.50–0.99 HA number range. It remains an existing
deployment exception, not a newly recommended tuning value.

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

## Public evidence boundary

Public documentation contains versioned facts, generic paths, advertised
definitions, examples and validation limits. Live HA configurations, addresses,
MACs, serials, Noise PSKs, tokens, signed media URLs, personal transcripts,
audio, trained weights and identifying screenshots stay in ignored private
storage. The JSON contract intentionally exports no state values.

This documentation update queried entity metadata and binary version only.
It did not change device controls, activate a model, enable recording, restart
a Dot or modify the firewall. A future check should record its date/version and
update this ledger when an unresolved item is actually reproduced or fixed.
