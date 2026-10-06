# Device controls, readable data and limits

This reference covers the two converted **Echo Dot 2 / BISCUIT** devices inspected
on **October 4, 2026**, running **EchoLocal 0.0.8**, with **Home Assistant 2026.9.1**
and the **EchoLocal HACS companion v0.0.7**. It is not a compatibility promise for
other Echo generations or later firmware.

## Evidence and scope

Both devices returned the same native API contract: **100 entities and 3 device
services**. The [sanitized JSON catalog](reference/echolocal-0.0.8-entities.json)
contains every advertised entity, numeric range, step, unit, select option,
light effect, default-disabled flag and service argument captured in that check.
It contains definitions, not household state, addresses or credentials.

The contract consists of 18 numbers, 21 selects, 9 switches, 13 lights, 1 media
player, 6 buttons, 5 events, 15 numeric sensors, 10 text sensors, 1 binary sensor
and 1 firmware-update entity. HA also creates assistant, wake-word, VAD and
Assist-satellite entities; those are not additional firmware settings in this
catalog. HA registry names can differ from native `object_id` values.

The bounds below are **advertised UI bounds**, read from both devices. They are
not hardware safety ratings, recommended tuning targets, or proof that every
direct API/config-file path clamps values. Runtime behavior and fixed limits
are identified from the pinned source. A command's presence or help output does
not establish that its disruptive operation has been tested.

## Where to read and change things

- **Overview → Media → EchoLocal card:** Ring, Microphone, Playback, Assistant 1,
  Assistant 2, Activity, Settings and Diagnostics.
- **Settings → Devices & services → ESPHome → the Dot:** native entities and its
  related sub-devices. Enable individual ring-segment entities here if needed.
- **Settings → Voice assistants:** providers, languages, preferred pipeline,
  exposed household entities and local intents. These settings live in HA.
- **EchoLocal sidebar:** shared wake-word library, activity, groups and health.
- **ADB:** files, Android state, logs and hardware tools. See
  [device access](device-access.md) before using commands that change hardware.

Use the actual entity selected from the device page. For automation, HA uses
`number.set_value`, `select.select_option`, `switch.turn_on`/`turn_off`,
`light.turn_on`/`turn_off`, media-player actions and `button.press`. For example,
this changes a selected Dot's gain; it is an example, not an automatic step:

```yaml
action: number.set_value
target:
  entity_id: "<MICROPHONE_GAIN_ENTITY>"
data:
  value: 20
```

Change one variable, read it back, perform the relevant listening or playback
test, then retain or restore it. Do not copy another unit's full configuration,
device identity, PSK or Wi-Fi files when matching settings.

## Microphone

- **Microphone mixing** (`microphone_mixing`): **Center mic**, **Delay and sum**,
  or **Beamformer**. This changes how the microphone array is combined. No
  alternate mix has been established here as universally better for the owner.
- **Microphone gain** (`microphone_gain`): **0–59 dB**, step **1 dB**. This is
  analog microphone gain; it is not speaker volume or a wake-word threshold.
  More gain can amplify background noise or cause clipping.
- **Microphone leveling** (`microphone_leveling`): on/off automatic leveling.
- **Microphone echo cancellation** (`microphone_cancel_echo`): on/off cancellation
  of speaker output from the microphone path.
- **Microphone noise reduction** (`microphone_noise_reduction`): on/off denoising.
  These three processing switches affect audio presented to recognition;
  changing them can alter both detections and speech transcription.
- **Room sensitivity** (`microphone_sensitivity`): **4–20 dB**, step **1 dB**.
  This is the margin above the estimated room floor used by room activity
  processing, not a second wake-model probability threshold.
- **Microphone mute** (`mic_mute`): on/off hardware microphone mute.
- **Mute LED brightness** (`mute_led_brightness`): **Dim** or **Bright**.
- **Mute sound** (`mute_sound`): **None**, **Mute tones**, **Chirp**, **Ding**, **Rise**.
- **Stop word sensitivity** (`stop_word_sensitivity`): **0.50–1.00**, step **0.01**.
  A value of **1.00 disables** this local interruption detector. It is separate
  from the two assistant slots and does not start an HA pipeline. The source
  ignores it while a command is being listened to or when there is nothing
  audible to stop. This does not configure a Russian stop phrase.

Observed baseline: Center mic, gain 20 dB, leveling and echo cancellation on,
denoising off, room sensitivity 8 dB, microphone unmuted, Bright mute LED,
Mute tones and stop threshold 0.70. These are deployment observations, not
newly recommended values or universally optimal settings.

## Assistant slots 1 and 2

There are **two active wake-word slots**. HA's **Assistant / Assistant 2** choose
each slot's pipeline; **Wake word / Wake word 2** choose its model. The suffix
`_1` or `_2` in the following native IDs identifies the corresponding slot.

- **Wake word sensitivity** (`wake_threshold_1`, `_2`): **0.50–0.99**, step
  **0.01**. The value is a score cutoff: a higher value requires a higher score
  and generally rejects more candidates; a lower value increases sensitivity.
  Scores are model-specific and are not comparable accuracy percentages.
- **Wake word tone** (`wake_tone_1`, `_2`): **None**, **Chirp**, **Ding**, **Rise**.
- **Wake word effect** (`wake_effect_1`, `_2`): None or one of the ring effects.
- **Thinking / Replying effect** (`thinking_effect_1`, `_2`, `replying_effect_1`,
  `_2`): **Default**, **None**, or a named ring effect. Default leaves the phase
  override unset; it is distinct from explicitly choosing no effect.
- **Reply delivery** (`reply_delivery_1`, `_2`): **Whole file** or **Streamed**.
  Whole file fetches the completed reply URL; streaming can start sooner but is
  sensitive to chunk delivery gaps. Neither choice changes the speech provider.
- **Reply buffer** (`reply_buffer_1`, `_2`): **0–3000 ms**, step **50 ms**. This
  buffers streamed speech before playback; it is not a Plex/Sendspin music buffer
  and does not reduce STT or conversation-server latency.
- **Follow-up time** (`follow_up_1`, `_2`): **0–30 s**, step **1 s**. Zero disables
  automatic follow-up listening; an explicit HA request can still open a turn.
- **Max listening time** (`max_listen_1`, `_2`): **5–60 s**, step **1 s**. This is
  a backstop if the listening phase does not finish normally, not a recording
  duration request and not a guarantee that HA waits that long for speech.
- **Max thinking time** (`max_think_1`, `_2`): **5–300 s**, step **5 s**. It bounds
  waiting for a reply. Raising it cannot restore provider quota or fix a failed
  STT request.
- **Recordings kept** (`keep_recordings_1`, `_2`): **0–10 turns**, step **1**,
  independently per slot. Zero disables retention and prunes retained files for
  that slot. This setting is a count, not seconds or a start-recording button.
- **Wake** (`wake_assistant_1`, `_2`): starts a turn in that slot without proving
  acoustic wake-word recognition. It is an action, not a read-only status field.

The physical action button starts slot 1 when idle; a short press can instead
stop a current activity. Holding it reaches slot 2; the source's hold threshold
is **700 ms**. A button-started turn can report the slot's configured wake phrase
even though no phrase was detected acoustically.

### Existing threshold exception

The observed baseline is **Okay Nabu at 0.85** and **Привет, Мышка at 0.35**, both
using **FCC Russian Backup**. The second value is **outside the advertised HA
range**. It was already present before the companion installation, and was not
changed during this documentation audit. The source's stored threshold writer
does not itself impose the UI bounds. That explains why a persisted/runtime
value can differ from what an ordinary HA number control permits; it does not
make arbitrary out-of-range writes supported tuning.

Do not round 0.35 up to 0.50 just to make a form happy, or lower thresholds as a
substitute for validation. Record this exception during backup/restore and use
the existing [wake-word evaluation workflow](custom-wake-word.md). The previous
short **Мышка** candidate was withdrawn after frequent false activations.

Both slots otherwise used Chirp, Pulse, Default phase overrides, Whole file,
650 ms buffer, zero follow-up, 15 s listening limit, 90 s thinking limit and
zero retained recordings. The 650 ms value remains stored even with Whole file
selected; that does not mean it adds a streaming buffer to whole-file playback.

## Playback and music

- **Speaker** (`speaker`): volume, mute, play/pause/stop, media playback and
  announcements. HA represents volume as **0–1**; the device has **0–30 steps**.
  Fine slider values can therefore map to the same hardware step.
- **Voice resampling** (`voice_resampling`): **Band limited**, **Linear**,
  **Repeat samples**. This controls voice sample-rate conversion to the speaker
  path; a cheaper conversion is not automatically an improvement in quality.
- **Music during a turn** (`media_on_turn`): **Duck** or **Pause**.
- **Music ducking** (`media_duck_level`): **−40 to −3 dB**, step **1 dB**.
  More negative means quieter background music while ducking.
- **Speaker EQ** (`speaker_eq`): on/off vendor speaker tuning.
- **White noise layer 1 / 2** (`noise_layer_1`, `_2`): independently **None**,
  **White**, **Pink**, **Brown**, **Rain**, **Ocean**, **Brook**, **Wind**, **Fire**,
  **Crickets**, **Fan**, **Cabin**. Selecting a sound can start audible output.
- **Sendspin** (`sendspin`): enables/disables participation as a Sendspin player.
  Turning it off leaves the group/connection; it is not merely pause.

Observed baseline: Band limited, Duck at −15 dB, Speaker EQ on, both noise layers
None and Sendspin on. A prior parity snapshot found speaker levels of 26/30 on
one Dot and 25/30 on the other; all other compared native settings matched.
This is a dated observation, not a volume lock or an instruction to equalize it.

The native API advertises PCM16 WAV at **48 kHz stereo** for ordinary media and
**16 kHz mono** for announcements. The direct URL media path expects converted
WAV, not arbitrary MP3/AAC input. HA/media providers perform the needed
conversion. Sendspin has its own transport and codec handling; do not infer its
codec support from the WAV-only direct URL path. See [music latency](music-latency.md).

## Ring, colors and feedback

There is one whole-ring light plus **12 RGB segment lights**. Segment entities
are disabled by default in HA. HA names them 1–12; the low-level `led seg` CLI
indexes them **0–11**. The native light API uses normalized RGB/brightness;
ordinary HA RGB values and brightness use the usual **0–255** representation.

The whole-ring light sets the base appearance. Conversation, mute and failure
feedback can temporarily cover it; changing the base does not cancel an active
voice turn. **Ring on failure** (`failure_effect`) and **Ring while muted**
(`ring_muted`) select feedback effects independently.

The advertised effect choices are: None, Pulse, Heartbeat, Ripple, Standing Wave,
Twinkle, Crimson Heartbeat, Aurora Pulse, Candle, Fireplace, Embers, Aurora,
Sunset Drift, Ocean Ripple, Rainbow Twinkle, Forest Twinkle, Comet, Chase,
Scanner, Pinwheel, Spiral, Wipe, Helix, Orbits, Bounce, Spring, Rainbow,
Fire Comet, Ice Comet, Rainbow Chase, Ice Scanner, Rainbow Pinwheel,
Sunset Spiral, Rainbow Orbits, DNA, Pac-Man, Alert and Beacon.

**Ring follows the room** (`room_reaction`) offers None, Room Compass, Room Glow,
Room Meter, Room Ocean, Room VU, Room Fire, Room Spin, Room Aurora, Room Twinkle
and Room Embers. The observed deployment uses None, with Alert for failures.
Because effects are configurable, a color or animation alone is not a reliable
error code; correlate it with Activity and logs.

## System settings and actions

- **Metrics interval** (`metrics_interval`): **10–3600 s**, step **10 s**;
  observed 300 s. Diagnostic readings may be older than the current voice turn.
- **Minimum CPU cores** (`min_cores`): **1–4**, step **1**, on these units;
  observed 2. It sets a minimum, not a maximum or an overclock. The upper bound
  comes from detected hardware, not a universal Echo value.
- **Bluetooth proxy** (`bluetooth_proxy`): on/off, observed off. This build
  advertises passive BLE scanning/raw advertisement forwarding. It does not
  advertise an active GATT proxy or a Bluetooth audio-speaker service. Wi-Fi
  and Bluetooth share radio resources.
- **Remote adb** (`remote_adb`): on/off firewall control for TCP 5555, observed
  off. An additional allow rule still made root ADB reachable on both devices.
  The switch alone did not establish that network ADB was closed.
- **Skip certificate checks** (`insecure_tls`): on/off HTTPS certificate
  validation bypass, observed off. Fix endpoint/certificate problems rather
  than treating this as a normal playback option.
- **Update channel** (`update_channel`): **stable** or **dev**, observed stable.
  **Check for updates** queries availability; the **Firmware** update entity
  installs device firmware. HACS companion updates and Dot firmware updates
  are separate operations.
- **Restart** (`restart`): reboots the **whole Dot**. It does not only reload
  the companion or reconnect ESPHome.
- **Test playback** (`test_playback`): audible diagnostic output.
- **Purge cache** (`purge_cache`): removes unused wake-model files and manifests,
  retaining models selected by active slots. It is not a harmless refresh.
  Preserve a private copy of a model that cannot be downloaded again.

## Readable status and history

Diagnostics exposes Wi-Fi signal in dBm, sent/received rates in kB/s, BLE
advertisement rate, CPU/radio temperatures, total/online cores, load average,
available memory, free space, unused model-cache size, illuminance and hardware
color. **Load average is not CPU utilization in percent.** Room level and room
floor are processing measurements without a published physical SPL unit.

Other read-only data includes headphone-jack presence, IP addresses, the last
heard text/reply/wake phrase, Sendspin state/artist/title, timer summaries and
firmware update status. Physical-button events carry `press` or `hold` for
action, mute, volume down and volume up; volume-repeat events are intentionally
not emitted as separate HA events. Firmware outcomes are `installed`,
`rolled_back` or `failed`.

The companion's Activity page reads recorded `esphome.echolocal_turn` events
and shows outcome, slot, phrase/transcript/reply, and phase timings. Its v0.0.7
activity query covers **14 days**; that is a frontend query window, not a
guarantee of HA Recorder retention. Last-value sensors are not full history.
Recording links can outlive their device files after pruning.

The native response services are **`recordings`** (no arguments), **`turn_audio`**
(`id`: string, `page`: integer), and **`logs`** (`page`: integer). Use the actual
ESPHome action name registered by HA, rather than guessing a device prefix.
Use the companion's playback/log-download controls for ordinary inspection.

## Fixed limits and boundaries

- A retained turn is mono **16 kHz PCM16 WAV** and is capped at approximately
  **30 s** of audio by the recording buffer. This remains separate from the
  maximum **60 s** listening setting. The frame-based limit can include the
  frame that crosses the cap; it is not a sample-exact trimming promise.
- Up to **10 recordings per slot**, nominally 20 on one Dot, can be retained.
  WAV plus metadata is finalized when the whole turn closes. A slow reply can
  delay its availability after the user stops speaking. Export before lowering
  retention; setting it back to zero prunes the device copy.
- Audio responses use **32 KiB raw pages**, base64 encoded in the API response.
  Log pages target **32 KiB** of text and keep lines intact. Page numbering is
  zero-based. Reassemble all pages; the first page is not necessarily a full WAV.
- Companion upload checks accept `.tflite` files up to **8 MiB** and require an
  HA administrator. Uploading creates/overwrites model and JSON files under
  HA's `custom_wake_words/`; the filename/ID matters. A size/extension check is
  not model compatibility, accuracy, false-activation or numerical-parity testing.
- HA library metadata, the selected device model and the per-slot threshold
  are separate state. Deleting a library entry is not verified revocation of a
  cached model already on a Dot. Purging the Dot cache is a separate operation.
- Sendspin listens on **TCP 8928** when enabled and accepts **one server
  connection at a time** in this build. The source has a 60-second ahead-queue
  bound; that is not a user-selectable latency target.
- Completed voice-file fetching has a **30 s HTTP timeout**. URL music streaming
  instead has a **30 s stalled-read limit**. These are not the adjustable
  Max thinking time, nor a limit on the total length of a music track.
- Native API **6053**, ADB **5555**, Sendspin **8928**, and HA media URLs are
  different network paths. One reachable port does not establish the others.
  See [access findings](device-access.md) for HTTP, SSH and Telnet results.

## Source and related records

All source claims above refer to EchoLocal **0.0.8**:
[microphone](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/microphone/microphone.go),
[wake settings](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/wakeword/wakeword.go),
[stored slot configuration](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/config/wake.go),
[recordings](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/recording/recording.go),
[playback](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/media/player.go),
[diagnostics](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/diag/diag.go)
and [Sendspin](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/sendspin/listen.go).
The companion references are pinned to
[v0.0.7 model management](https://github.com/ygelfand/echolocal-hacs/blob/v0.0.7/custom_components/echolocal/wakewords.py)
and [activity](https://github.com/ygelfand/echolocal-hacs/blob/v0.0.7/src/tabs/activity.ts).

Read the [findings and unresolved issues](operations-findings.md),
[companion installation](echolocal-companion.md), [ADB reference](device-access.md),
[voice integration guide](../research/ha-integration.md) and
[training history](training-history.md) for the corresponding operational steps.
