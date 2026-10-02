# Connect EchoLocal to Home Assistant

This guide covers the Home Assistant side after a supported Echo Dot has been converted and EchoLocal is running. Hardware identification, unlocking, installation, and recovery are covered in the [conversion guide](conversion.md).

The reference pilot used **EchoLocal 0.0.8 and Home Assistant Core 2026.9.1**. The ESPHome integration loaded successfully, a Russian Homeway/Sage pipeline was assigned, an announcement completed, and the owner confirmed a spoken Russian reply to a voice command. This establishes a working basic voice exchange. Cold power-on recovery, prolonged operation, repeated-command accuracy, and multi-device behavior remain untested.

All angle-bracket values below are placeholders. Keep actual addresses, device identifiers, Wi-Fi details, encryption keys, and diagnostic recordings in private deployment records.

## What is required

- One running Home Assistant installation with Assist available.
- A complete Assist pipeline: a conversation agent, speech-to-text (STT), and text-to-speech (TTS), with compatible language settings.
- A converted Echo running EchoLocal, its network address, and its own ESPHome API encryption key.
- Network reachability from Home Assistant to the Echo and, for URL-based playback, from the Echo back to Home Assistant.

The **ESPHome integration** is the primary connection. EchoLocal implements the ESPHome native API; the Echo is not an ESP32 that needs an ESPHome YAML build. Its standard voice, speaker, and device controls work without the optional EchoLocal HACS integration. [EchoLocal 0.0.8 overview](https://github.com/ygelfand/echolocal/blob/0.0.8/README.md).

An `assist_satellite` entity is created through ESPHome. Do not try to add a separate integration named Assist Satellite: it is a building block supplied by device integrations. [Assist Satellite documentation](https://www.home-assistant.io/integrations/assist_satellite/).

## 1. Prepare network access

Give each Echo a unique device name and reserve its current address in the router's DHCP settings. Record the reservation against that Echo's MAC address privately. A reservation prevents manual HA entries from pointing to a different device after a lease changes.

Check these paths:

- **Home Assistant → `<ECHO_IP>:6053/TCP`:** HA opens the native API connection. Commands, microphone audio, and supported streamed responses use this connection.
- **Echo → the URL issued by HA for TTS/media:** commonly `http://<HA_REACHABLE_HOST>:8123`, or the configured HTTPS endpoint. DNS, routing, and any applicable firewall rules must work from the Echo's network.
- **Home Assistant → speech providers:** the selected STT/TTS services must be reachable independently of the Echo.

EchoLocal 0.0.8 explicitly does not implement the legacy negotiated UDP voice path. Do not open an arbitrary UDP port range for its microphone audio. Its response handling supports both API streaming and URL retrieval. [Voice transport implementation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/voice/conversation.go#L200).

Across VLANs, a routed VPN, or a remote HA host, add the Echo by IP. Do not assume mDNS discovery crosses the route. Check return routes and Wi-Fi client isolation if TCP connections fail. No public port forward is required for the Echo.

### Check the Home Assistant playback URL

Open **Settings → System → Network** and inspect the **Home Assistant URL** settings. The local URL must be reachable from the Echo, not merely from the HA server or an administrator's browser. On a routed or containerized installation, an automatically selected address might not be usable from the device network. If the URL is managed in YAML, change it through that configuration's normal validation and activation process. [HA TTS network settings](https://www.home-assistant.io/integrations/tts/#troubleshooting).

Use the actual URL from a failed playback attempt when diagnosing sound. A working API connection does not establish that this URL resolves or downloads successfully. EchoLocal's URL player performs an HTTP GET, expects HTTP 200, and decodes the returned audio; a login page or proxy authentication challenge is not an audio response. [EchoLocal media fetch](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/media/fetch.go#L34).

The pilot exposed this distinction: a hostname worked from the HA side but failed from the device network. Correcting the reachable internal URL restored the playback path. Keep signed media URLs private.

## 2. Select or create an Assist pipeline

Before pairing the Echo, open **Settings → Voice assistants** and inspect the assistants under **Assist**. If a suitable complete pipeline already exists, reuse it. A text-only assistant with no STT engine is not sufficient for this voice satellite.

To create a separate pipeline:

1. Select **Add assistant**.
2. Set **Name** to `<PIPELINE_NAME>` and **Language** to the language you will speak.
3. Under **Conversation agent**, choose the installed agent you intend to use. **Home Assistant** is the built-in option for ordinary home-control intents and custom sentences. An installed LLM agent is a separate choice.
4. Under **Speech-to-text**, select an installed STT provider and its matching language.
5. Under **Text-to-speech**, select an installed TTS provider, the response language, and a compatible voice if offered.
6. Save the assistant. Leave other devices' preferred assistant unchanged; the Echo can select this pipeline individually.

These fields are described in the [official Assist setup guide](https://www.home-assistant.io/voice_control/voice_remote_local_assistant/#installing-a-local-assist-pipeline). If the Assist section is missing because the installation does not use `default_config`, follow the [HA configuration guidance](https://www.home-assistant.io/voice_control/troubleshooting/#i-do-not-see-any-assistant) before continuing.

### Backend used in the pilot

The pilot reused **Homeway/Sage**, with Russian selected for the assistant, STT, and TTS. Its already-installed conversation and speech services were tested before the Echo was paired. Homeway is a third-party cloud backend; it is not required by EchoLocal and is distinct from Home Assistant Cloud by Nabu Casa.

On another installation, choose providers that are actually installed and available in these selectors. Copying a pipeline name does not install its engines or establish access to the provider. Verify a short voice exchange in the HA phone app with the intended assistant before debugging the Echo hardware.

## 3. Add the Echo through ESPHome

Use the key provided for this particular Echo by the installation/provisioning process. It is a base64-encoded 32-byte Noise PSK. Do not reuse another Echo's key or copy a device's full identity when preparing additional units.

1. Open **Settings → Devices & services**.
2. Select **Add integration → ESPHome**. If ESPHome is already installed, choose to add another device when prompted.
3. Enter **Host** as `<ECHO_IP>` and **Port** as `6053`.
4. Submit the form. When asked for the encryption key, paste this Echo's PSK.
5. Complete setup and open the new device. Check that the identity belongs to the intended Echo and that its entities become available.

If discovery already offers the correct device, its setup flow can be used instead. Manual IP entry is the predictable route across subnets. [ESPHome configuration and encryption fields](https://www.home-assistant.io/integrations/esphome/#configuration).

If HA reports an existing device or a conflicting name, inspect the existing entry before proceeding. Do not choose a replacement or migration operation just to dismiss a conflict. Correct the device name or address and reuse the matching entry where appropriate. No HA restart or ESPHome Device Builder firmware compilation is normally required for this pairing step.

## 4. Choose the assistant and wake-word slot

On the Echo's device page, find its configuration entities. The first pair is **Assistant** and **Wake word**; the second pair is **Assistant 2** and **Wake word 2**. Depending on the frontend layout, some controls may appear under associated sub-devices.

1. Set **Assistant** to `<PIPELINE_NAME>`. Selecting an explicit pipeline avoids following later changes to the global **Preferred** assistant.
2. Set **Wake word** to **Okay Nabu** for the initial test, matching the successful pilot.
3. Leave the second wake-word slot unused for the baseline test. Later, a second phrase can select the same or a different assistant; see the [custom wake-word guide](../docs/custom-wake-word.md). A slot with no wake word does not listen for activation.
4. Confirm that microphone mute is off and speaker volume is audible.

Each wake-word slot is paired with its own assistant. Selecting **Assistant 2** does not change the pipeline used by the first wake word. The **Reply delivery** control also belongs to an individual slot; keep its initial setting until basic voice operation works. [EchoLocal slot behavior](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/feature/wakeword/wakeword.go), [HA assistant selector labels](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/assist_pipeline/strings.json).

The wake word and the spoken-command language are separate settings. A Russian pipeline can use the English wake phrase **Okay Nabu**. Changing the pipeline language does not translate or retrain the wake-word detector; another phrase needs a compatible model and separate testing.

## 5. Assign an area and expose one test entity

Assign the Echo to `<ROOM>` on its device page: open the device settings/edit dialog, choose **Area**, and save. Assign the test light to the appropriate area too. Use an explicit light name for the first test; try contextual requests such as “turn on the lights” only after the area assignments are correct. [HA areas](https://www.home-assistant.io/docs/organizing/areas/).

Open **Settings → Voice assistants → Expose**. Select one reversible test entity, such as a lamp, and enable exposure to **Assist**. Use its actual HA name or add an alias in the language of the pipeline. Pairing a microphone does not automatically make every household entity available to its conversation agent. [Expose entities to Assist](https://www.home-assistant.io/voice_control/voice_remote_expose_devices/).

For custom sentences, select the built-in Home Assistant conversation agent and the matching language. An LLM-based pipeline does not automatically guarantee the same custom-intent behavior. Test the command as text before testing the microphone.

Area assignment and DHCP reservation were not completed in the reference pilot. They are deployment steps in this guide, not claimed pilot results.

## 6. Test playback separately from the microphone

Open HA's **Actions** tool: **Developer tools → Actions** in the reference UI, or **Settings → Tools → Actions** in frontends using the newer navigation. Choose **Assist satellite: Announce**, select the Echo's actual Assist satellite entity, and enter a short sentence in the pipeline's TTS language.

The equivalent YAML is:

```yaml
action: assist_satellite.announce
target:
  entity_id: "<ECHO_ASSIST_SATELLITE_ENTITY>"
data:
  message: "This is a speaker test."
```

Replace the target with the entity selected from the device page and adapt the message language. Do not guess the generated entity ID. This action uses the satellite's selected pipeline for TTS. [Announce action](https://www.home-assistant.io/actions/assist_satellite.announce/).

Listen for the message and verify that the satellite returns to idle. A successful action or an idle state alone does not prove audible output. If no sound is heard, check volume/mute, the selected TTS provider, and the URL playback path before adjusting wake-word sensitivity.

## 7. Test the complete voice exchange

Say **Okay Nabu**, then a short command in the selected pipeline's language. Start with the explicitly named test lamp. Verify both the physical action and the spoken response; record them separately.

For diagnosis, open **Settings → Voice assistants**, select the relevant assistant, choose **Debug**, and select the latest run. Separate failures by stage:

- No activation: microphone mute, selected wake word, slot, or local detector.
- Activation but no transcription: STT availability, selected language, or microphone/audio transport.
- Correct transcription but no intended action: entity exposure, names/aliases, area, or conversation agent.
- An answer appears in Debug but nothing is heard: TTS generation, speaker settings, or response delivery.

A typed pipeline test executes commands but does not test the microphone. An announcement tests the output path but does not test STT. [Assist troubleshooting](https://www.home-assistant.io/voice_control/troubleshooting/).

After the first successful exchange, separately test microphone mute, a software restart, a cold power cycle, Wi-Fi/VPN recovery, and a longer observation period. These recovery and soak checks have not yet been established by the reference pilot. Use the [acceptance checklist](../docs/acceptance-and-batch.md) before converting a batch.

## Optional integrations and alternative speech backends

**EchoLocal HACS companion:** optional dashboard/card, activity views, and wake-word library management. The documented companion requires HA 2026.8 or newer. If needed later, add `ygelfand/echolocal-hacs` as an Integration custom repository in HACS, install it, restart HA, then use **Settings → Devices & services → Add integration → EchoLocal**. It supplements the ESPHome connection. It is not needed for the basic voice path and was not part of the acceptance evidence above. [Companion installation](https://github.com/ygelfand/echolocal-hacs#installing).

**ESPHome Device Builder:** not required for EchoLocal installation, pairing, or updates. Do not treat the Dot as a generic ESP32 firmware target. Use EchoLocal's own supported installation and update process.

**Music Assistant:** optional for music features and multi-room work. Test it after voice is stable. Its server, player setup, and network paths are separate from the basic Assist pipeline. A working spoken reply does not demonstrate synchronized music playback.

**MQTT:** not required for the EchoLocal native API voice connection.

**Self-hosted STT/TTS:** Whisper or Speech-to-Phrase plus Piper are alternatives, not services deployed by this pilot. HA OS can install their apps. HA Container users run separate supported services and add them using **Settings → Devices & services → Add integration → Wyoming Protocol**, entering each service's host and port. Then select those providers in a separate Assist pipeline. HA supports Wyoming services on another computer. [Wyoming integration](https://www.home-assistant.io/integrations/wyoming/).

Whisper handles open-ended transcription and needs more compute. Speech-to-Phrase targets a supported command grammar and is lighter; its project lists Russian, but custom free-form requests still need testing. Piper provides local TTS with language-specific voices. Benchmark the chosen models on existing hardware before scaling. [Whisper server](https://github.com/OHF-Voice/wyoming-faster-whisper), [Speech-to-Phrase](https://github.com/OHF-Voice/speech-to-phrase), [Piper server](https://github.com/OHF-Voice/wyoming-piper).

EchoLocal detects wake words on the Echo, so this setup does not require a separate server-side wake-word service. Removing Amazon Alexa from the device does not by itself make the whole system offline: a remote HA host, a routed WAN connection, or a cloud speech provider remains an external dependency. Fully local operation requires the entire selected voice path and HA to remain reachable within the home when Internet access is unavailable.
