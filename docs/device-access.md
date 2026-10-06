# Device access and ADB diagnostics

Converted Echo Dot 2 devices run EchoLocal on the retained Android/Fire OS base.
ADB is the maintenance shell. The ordinary HA connection uses the encrypted
ESPHome native API on TCP 6053; it does not require ADB or a permanent USB host.

## Connect

For USB maintenance, attach the Dot to the prepared USB host and select its exact
serial from `adb devices -l`. For network maintenance, use the device's verified
address and ensure network ADB is available on TCP 5555:

```bash
ECHO_ADB='<ECHO_IP>:5555'
adb connect "$ECHO_ADB"
adb -s "$ECHO_ADB" shell id
adb -s "$ECHO_ADB" shell
```

Use `exit` to leave the shell. Always specify `-s` when more than one device is
connected. `adb disconnect "$ECHO_ADB"` disconnects the client; it does not disable
the device's network listener.

EchoLocal exposes **Remote adb** under its diagnostic settings. Verify actual
reachability after changing it: an unrelated firewall rule can leave port 5555
reachable even when this switch is off. In the two-device October 4 audit, both
switches were off but an additional INPUT rule accepted TCP 5555. Both devices
accepted a root ADB connection without an authentication challenge. No firewall
rules or authentication settings were changed during this audit. Keep this
maintenance path on a trusted network; it is not a public login service.

The audit also found a client-specific limitation: the installed macOS `adb`
client returned `No route to host`, while bounded ADB protocol connections from
Python on the same Mac, and an earlier check from the HA pod, succeeded. A TCP
port test alone therefore does not prove that a particular ADB client works.
Check the client's route and macOS network access rather than changing the Dot's
firmware to address this host-side symptom.

This does not establish the cause of the macOS client failure: no specific
permission, VPN, firewall or routing diagnosis was confirmed. Do not describe
the standard Mac client as tested successfully just because another client works.

## Confirmed capabilities

Both converted Dots passed these live checks:

- Root shell: `uid=0(root)`.
- Reading uptime, memory, disk space, process information and firewall rules.
- Reading Android logs and the `echolocal` log tag.
- Reading the installed runtime location and the model directory listing.
- Sending a disposable file to `/data/local/tmp`, reading it back byte-for-byte,
  and removing it. No existing device file was changed.

Useful read-only commands, using the same selected `ECHO_ADB` target:

```bash
adb -s "$ECHO_ADB" shell uptime
adb -s "$ECHO_ADB" shell cat /proc/meminfo
adb -s "$ECHO_ADB" shell df /data
adb -s "$ECHO_ADB" shell getprop init.svc.ledcontroller
adb -s "$ECHO_ADB" shell getprop echolocal.state
adb -s "$ECHO_ADB" shell ls -l /data/misc/echolocal/models
adb -s "$ECHO_ADB" logcat -d -t 100 -s echolocal
adb -s "$ECHO_ADB" shell /system/app/echod/echod tools --help
```

EchoLocal 0.0.8 takes over Android's `ledcontroller` service. Both tested devices
reported that service as `running` and EchoLocal state as `resident`. Its binary
is `/system/app/echod/echod`; runtime settings and models live under
`/data/misc/echolocal`. That directory also contains the private ESPHome PSK: do
not publish a recursive backup or print its contents into public diagnostics.

The installed tools list includes `mic`, `wake`, `echo`, `mixer`, `mute`, `play`,
`voice`, `media`, `led`, `buttons`, `info`, `i2c` and `remount`. These provide
hardware diagnostics, capture, playback and maintenance capabilities. Their help
output was verified; microphone capture, audio playback, service restart,
filesystem remount and firmware modification were not exercised by this audit.

For voice diagnosis, prefer EchoLocal's normal retained-turn mechanism because
it follows the active microphone-processing path. Direct `mic`/`tinycap` capture
can contend with the running audio service and is not automatically equivalent
to the audio sent to HA. Coordinate a short recording before using it, and restore
the normal service and retention settings afterward.

Root access also permits backing up or replacing models and restarting the
service, but use the existing validated deployment workflow for such writes.
The dashboard/ESPHome controls are preferable for normal parameter changes.

## Files and persistence

The following locations are confirmed by the 0.0.8 layout/source; binary, service
symlink and model directory existence were also checked on both live devices:

- `/system/app/echod/echod`: installed executable. Both returned
  `echod version 0.0.8 (6eff3b1, 2026-09-30T16:45:06Z)`.
- `/system/bin/ledcontroller`: service executable symlink to that binary.
- `/data/misc/echolocal/state.json`: persisted runtime settings.
- `/data/misc/echolocal/models/`: installed model and manifest pairs. Presence
  does not mean a slot has selected that model; withdrawn candidates can remain
  cached here.
- `/data/misc/echolocal/recordings/`: retained-turn WAV files and metadata,
  subject to per-slot retention and pruning.
- `/data/misc/echolocal/name` and `/data/misc/echolocal/psk`: device identity and
  the private native-API encryption key. Do not clone these between speakers.
- `/data/local/tmp/`: appropriate location for a disposable diagnostic file;
  it is not the durable model/configuration directory.
- `/system/etc/echolocal/echod.yaml`: the CLI's optional startup configuration
  path. Do not confuse it with the live runtime state JSON.

Backups belong in a private directory on the workstation. A successful
`adb pull` establishes file transfer, not that restoring the file while the
service runs is safe. For example, after substituting the exact target:

```bash
umask 077
mkdir -p private/device-backup
adb -s "$ECHO_ADB" pull /data/misc/echolocal/state.json private/device-backup/state.json
```

Keep each speaker's backup separate. Changes made through HA/native controls are
normally persisted by the daemon. Raw mixer or LED-register writes may be
temporary and can disagree with the running daemon's state. Editing state JSON
while the process runs can be overwritten by its next save. Prefer the exposed
controls; stage deliberate offline repairs with a backup and a recovery route.

## Hardware command reference

Run `/system/app/echod/echod tools <command> --help` through the selected ADB
target to inspect the installed command before using it. The root tools list
was checked live; the details below come from the pinned 0.0.8 command source.
Only help/version, ordinary system reads and the disposable file-transfer test
were exercised in this access audit.

### Inspection and commands with both read and write modes

- **`info`** enumerates audio and hardware information.
- **`mixer`** lists ALSA controls without arguments; `mixer <name>` reports a
  control's current value, type, count and numeric bounds or enumerated choices.
  Adding a value writes it. Mixer bounds are driver/control-specific, so there
  is no valid universal mixer gain range. `--card` defaults to 0.
- **`mute`** reads hardware mute without an argument; `on`, `off` or `toggle`
  writes it. It is distinct from speaker mute.
- **`led show`** reads ring driver state; **`led current`** reads global drive
  current. Adding a current value writes hardware, not just HA brightness.
- **`buttons --seconds 20`** observes physical events for a bounded period;
  20 s is the default. It does not synthesize a press.
- **`i2c dump`** reads a register range; **`i2c set`** writes one register.
  The generic command description says “Read”, but a write subcommand exists.
  Its `--force` flag defaults to true and can address hardware already owned by
  a kernel driver. This is specialist hardware access, not an ordinary health
  check; even register reads can have device-specific side effects.

### Audio capture and model diagnosis

- **`mic`** defaults to ALSA card 0/device 24, **9 channels at 16 kHz**, packed
  **24-bit S24_3LE**, period 256 frames × 10 periods, for 5 s. The command's help
  identifies channels 0–6 as microphones and 7–8 as playback references, and
  says the hardware accepts only 9 channels/16 kHz. `--raw` writes interleaved
  raw data, not a ready-to-train mono WAV. The source warns that opening an
  already owned capture device may block; merely setting `--seconds` does not
  bound a blocked device-open call. Do not blindly stop a service named in
  generic help: first identify the owner in the converted system.
- **`wake`** can use the microphone or `--wav` with a 16 kHz mono WAV. Options
  include `--models`, `--seconds` (default 30), `--gain` (default 1), and
  `--compare` for comparing channel mixes on captured audio. The inspected
  implementation chooses the **first slot's** saved model and constructs its
  detector from the model configuration. It is not a generic selector for the
  second slot or a guarantee of the production per-slot cutoff. Match model,
  frontend, state and threshold explicitly before interpreting a score.
- **`echo`** measures speaker leakage into microphones. It both plays and
  captures audio. Defaults include `--secs 4` and `--level 0.25`; `--noise`
  changes the stimulus and `--save` writes raw capture. This is not a passive
  diagnostic or an automatic acoustic calibration.

For retained speech sent to HA, use the
[recording limits and procedure](device-controls.md#fixed-limits-and-boundaries).
Do not train directly on raw nine-channel samples or silently include command
recordings as positive wake-phrase examples.

### Playback, LEDs and service changes

- **`play`** produces a test tone: default card 0/device 23, 440 Hz, 1 s,
  amplitude 0.2; the documented level range is 0–1. `--channel` selects left,
  right or both, and `--silence` writes zeros. These are test parameters, not
  proof the upper level is appropriate for prolonged playback.
- **`voice <file.wav>`** exercises the voice playback path; **`media <url>`**
  exercises streamed media. Both accept `--volume`, with −1 meaning the saved
  volume and the device using 0–30 steps. Media also provides `--duck` and
  `--hold` to exercise interruption timing. Signed/private media URLs must not
  be copied into public examples.
- **`led fill`** accepts 0–255 per channel; **`led set`** takes a 36-byte frame
  encoded as 72 hex characters; **`led seg`** selects segment 0–11 and a
  six-digit RGB color. Other subcommands include `off`, `all`, `walk` and
  `segwalk` (default 1200 ms per segment). These writes can compete with the
  running animation engine; use HA lights for ordinary control.
- **`remount rw|ro`** changes the system partition's mount mode. Normal settings,
  model selection and dashboard installation do not need a writable `/system`.
- **`setprop ctl.restart ledcontroller`** requests an EchoLocal service restart;
  **`reboot`** restarts the whole device. HA's **Restart** button is the latter
  kind of operation. Both interrupt active use; neither was needed or tested
  during the companion/access audit.

These low-level tools do not replace amonet/TWRP recovery, install a compatible
boot image on an unsupported Echo, or remove HA/provider-side limits. Use the
[conversion guide](../research/conversion.md) for firmware and recovery work.

## Web, SSH and Telnet

Neither device exposed a usable SSH or Telnet service in the audit. HTTP port 80
returned an empty nginx response; no standalone device administration page was
found. The working web interface is the [EchoLocal companion in HA](echolocal-companion.md),
which communicates through the existing ESPHome integration.

The HTTP checks established an empty nginx response on port 80, a certificate
validation error on HTTPS 443, and a failed HTTP exchange on 8080. They did not
establish a working administration site; certificate validation was not bypassed.
Ports 22/23 were unreachable or filtered, which is not proof that no matching
binary exists anywhere in the firmware.

For every exposed setting and advertised limit, see the
[controls reference](device-controls.md) and [findings ledger](operations-findings.md).

Source references: [EchoLocal 0.0.8 layout](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/layout/layout.go),
[diagnostic controls](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/diag/diag.go)
and [device tools](https://github.com/ygelfand/echolocal/tree/0.0.8/internal/cli/echod).
