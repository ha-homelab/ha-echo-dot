# Music startup latency

This is a measured EchoLocal **0.0.8** / Sendspin Go **1.8.2** finding from 2026-10-02, not a general claim about every Echo or Music Assistant installation. Basic Assist voice operation does not require Music Assistant. This page concerns the optional path **spoken command → HA intent/script → Music Assistant/Plex → Sendspin → Echo speaker**.

## Separate the timing stages

Measure command capture, recognized text, intent/script completion, spoken acknowledgement, first decoded music chunk, and actual output separately. An HA media player reporting `playing`, or a service call returning successfully, does not prove music is already audible.

In the observed spoken request:

- HA script execution took **3.001 seconds**: reading the existing queue took about **0.5 ms**, and the `media_play` call took **2.995 seconds**. The playlist was not rebuilt.
- The Echo received the first FLAC chunk while finishing its acknowledgement.
- The first chunk was scheduled **22.463 seconds into the future**. Only 96 ms of PCM was queued; that number did not include the future silence.
- The spoken turn finished about **0.06 seconds** after the chunk arrived, but the audio-reference log became active roughly **22.56 seconds** after arrival.
- A later correction re-anchored playback by about **21 seconds**. Subsequent observations showed corrections around milliseconds and a much smaller stream lead.

The participant confirmed both audible playback and a long delay. Audio-reference activity is supporting timing evidence, not a calibrated acoustic measurement. Earlier text-only service timings must not be reported as spoken-command-to-audible latency.

## Why the first chunk can wait

EchoLocal converts the server timestamp to a speaker frame when it anchors the first chunk. Its renderer returns silence until that frame, before running clock correction. A bad future anchor can therefore preserve a long initial gap even if the estimate improves during the wait. See [the pinned output implementation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/output.go#L181).

The first two recorded synchronization offsets differed by approximately **3189.5 seconds**, followed by nearly stable offsets. Sendspin's filter derives initial drift directly from its first two samples; this version has no clock-step reset at that initialization point. Adaptive forgetting starts only after 100 samples. This provides a mechanism for a disturbed initial estimate to recover slowly. The observed summaries do not establish whether the device clock or the server reference changed. See [filter initialization](https://github.com/Sendspin/sendspin-go/blob/v1.8.2/pkg/sync/timefilter.go#L109).

There is also a timing mismatch: EchoLocal refreshes synchronization about every **10 seconds**, while the library marks an estimate lost after **5 seconds**. The first anchor was logged with quality 2 (Lost); conversion still used the initialized filter, and output correction was disabled at that quality. Quality 1 (Degraded) later allowed correction. See [EchoLocal synchronization](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/session.go) and [clock quality](https://github.com/Sendspin/sendspin-go/blob/v1.8.2/pkg/sync/clock.go#L95).

These findings do not establish the cause of a separate unexpected reboot near an earlier music test. Keep reboot diagnosis separate from startup-latency diagnosis.

## Diagnose before changing settings

1. Confirm the exact spoken command reaches the intended music intent and existing queue. Avoid rebuilding a large Plex playlist on every request.
2. Keep the original firmware version, current queue, volume and private diagnostic evidence.
3. Compare HA timestamps with native `stream first chunk`, `anchored`, `turn ended`, and clock-correction lines. Use intervals within one clock domain unless their correspondence is independently established.
4. Distinguish network/download delay from an already decoded chunk scheduled in the future. The advertised buffer capacity is not a mandatory startup wait.
5. Check whether synchronization has already settled. Do not interrupt working playback simply to clear a historical estimate.

There is no exposed EchoLocal setting for these filter parameters or synchronization intervals. A fixed negative playback offset would conceal one transient error and misalign later correctly synchronized audio.

## Recovery boundary

A fresh Sendspin connection creates a new clock filter. A normal track stop or `stream/end` does not. After clocks are stable, reconnecting only the Echo's Sendspin transport is a possible recovery path that avoids a full Echo or HA reboot. It interrupts music and is **source-verified, not yet a measured recovery trial** in this setup.

The native `sendspin` enable switch can stop and recreate its listener. If using this route, first save the queue position and volume, disable the intended device's Sendspin switch, verify the transport has actually disconnected, and only then enable it again. Shutdown is asynchronous; rapid off/on can race it. Verify a fresh connection, new synchronization samples, queue continuity and restored volume before judging the next start. Do not reset it on every command or reconnect repeatedly while the reference clock is still changing. See [listener lifecycle](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/sendspin.go) and [per-connection session](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/session.go).

No firmware, wake-word model, recording setting or playback offset was changed for this diagnosis. Raw device logs, household identifiers and voice data remain private. A persistent fix would need regression coverage for a clock step, stale synchronization quality and correction of a future anchor before output starts.

## Crackling or intermittent freezes during playback

The participant later reported occasional rough audio and freezes after playback had started. This is a separate symptom from the initial future-anchor delay: by then clock corrections had settled to milliseconds.

One saved render diagnostic showed only **8–<9 ms** of queued PCM inside a **21.333 ms** output period. The implementation clears the output buffer before rendering, so approximately **12–13 ms** of that period remained silent. This software starvation need not produce an ALSA `playback underrun` warning. `dropped=0` and an unchanged count of wholly expired chunks do not exclude partial audio gaps. See [speaker rendering](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/hardware/speaker/speaker.go) and [Sendspin rendering](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/output.go).

Explicit `snapped earlier` or `snapped later` lines describe deleting PCM or inserting silence. Ordinary `off_ms` values describe clock error and must not be counted as audio edits. A reconnect is not a demonstrated fix for intermittent PCM supply once the clock has settled.

High resource contention was independently observed on the Music Assistant host. The current manual Plex track/playlist imports were cancelled as a reversible load reduction while preserving playback, volume, imported records and scheduled synchronization. In the first roughly one-minute observation afterward, logged queue depth stayed above 218 ms and the late-chunk counter did not increase. The logs are sampled, and listener confirmation was still pending: this does **not** establish that all audible defects were fixed or prove the server load caused them. Compare further audible results and stream/CPU evidence before changing buffer offsets, restarting services or blaming Wi-Fi.
