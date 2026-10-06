# EchoLocal companion and dashboard cards

The [EchoLocal HACS companion](https://github.com/ygelfand/echolocal-hacs)
adds a device card, diagnostics, activity history and a wake-word library to Home
Assistant. ESPHome remains the device connection, and Assist remains the voice
pipeline. The companion does not replace either integration.

## Install, then add the cards

1. Pair each converted Dot through ESPHome first. Confirm that its Assist
   satellite and configuration entities are available.
2. Use Home Assistant 2026.8 or newer. In **HACS → Custom repositories**, add
   `https://github.com/ygelfand/echolocal-hacs` with category **Integration**.
3. Download a released version. The deployment checked here uses **v0.0.7**,
   commit `3b92d727f00b32ceca65442e984010fbad89ec04`.
4. Restart HA after installation, as instructed upstream. Wait for startup and
   for the existing ESPHome devices to reconnect.
5. Open **Settings → Devices & services → Add integration → EchoLocal**.
   Enable the optional sidebar panel to access its shared activity and model
   library. One integration entry covers all EchoLocal satellites.
6. Open the existing media-player dashboard, choose **Edit dashboard → Add
   card → EchoLocal Satellite**, and select the first Dot. Repeat for the second.
   Select the main device with its ESPHome child devices, rather than a separate
   Music Assistant/Sendspin device with the same name.
7. Reload the browser if it was open before the integration loaded. The
   integration loads its frontend bundle automatically; a second manual
   Lovelace resource entry is unnecessary.

The equivalent manual card configuration is:

```yaml
type: custom:echolocal-satellite-card
device_id: <HA_DEVICE_REGISTRY_ID>
```

`device_id` is the main device's HA registry ID, not an entity ID, MAC address,
ESPHome entry ID or IP address. Use the visual card editor to select it.

## Where to find each control

The device illustration exposes volume, microphone mute and the action button.
The adjacent controls open Ring, Microphone, Playback and each assistant slot.
The footer opens Activity, Settings and Diagnostics. Diagnostics includes live
network signal, temperature, memory/disk information and diagnostic log download.

The **EchoLocal** sidebar panel lists all detected satellites and provides
**Wake words**, **Activity**, **Groups** and **Health** pages. Uploading a model to
the shared library is separate from selecting it for a device's wake-word slot.
An installed dashboard does not retrain, calibrate or activate a new model.

Activity can play microphone audio only when the corresponding recording was
retained. Installing the integration does not require enabling recording. Keep
retention at zero for ordinary use; enable a bounded capture only for an agreed
diagnostic attempt. Treat exported logs, conversation text and audio as private.

## Verified deployment, October 4, 2026

HACS v0.0.7 was installed on HA Core 2026.9.1, and all 14 installed source/bundle
files matched the pinned release. The integration loaded successfully after HA
startup. Two cards were added at the beginning of the existing **Overview → Media**
view (`/lovelace/media`), with a link to `/echolocal`. The five existing top-level
media cards and every other dashboard view were preserved.

The browser rendered both Dot cards with live readings and idle state. The
dedicated panel discovered exactly two satellites, and the diagnostic dialog
displayed live device values. Activity loaded existing conversation history and
per-phase timings, with no EchoLocal frontend errors observed. The frontend bundle and wake-word-library API
responded successfully. All 106 existing Dot select/number/switch states matched
their pre-install values, including FCC pipeline selection, Okay Nabu and
**Привет, Мышка**. Recording retention remained zero in all four assistant slots.

These checks establish integration and dashboard operation. They do not establish
improved wake-word accuracy or fix the previously observed STT `no-speech` error.

## Remove or recover

Remove the two custom cards before removing the companion, or Lovelace will show
an unknown-card error. Remove the EchoLocal integration entry, uninstall its HACS
repository, and restart HA when requested. Keep the ESPHome entries: they provide
the voice and speaker connection independently. A saved dashboard configuration
can restore the pre-install layout; reconcile concurrent edits before restoring it.

For shell access and lower-level diagnostics, see [device access](device-access.md).
For every exposed option, its range and its operational effect, see
[device controls](device-controls.md). The [findings ledger](operations-findings.md)
separates verified results from remaining problems.
