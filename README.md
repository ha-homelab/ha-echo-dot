# ha-echo-dot — Echo Dot 2 as a Home Assistant voice satellite

[ha-homelab/ha-echo-dot](https://github.com/ha-homelab/ha-echo-dot) documents conversion of an existing Amazon Echo Dot 2 into an EchoLocal voice satellite. This repository contains conversion instructions, USB-host helpers, and an explicit wake-word training/evaluation workflow. Firmware, audio datasets, trained weights, device backups, Wi-Fi credentials, and encryption keys are not included.

**Start with the [ordered runbook](docs/runbook.md).** It explains what runs on the USB host, what changes on the Echo, and what to configure in Home Assistant, with a completion check before each next stage.

## Tested result

One **Echo Dot 2 / BISCUIT** completed this path on 2026-10-02 UTC:

**amonet-biscuit 2.0.0 → TWRP 3.7.0_9-0 → verified post-unlock backup → Fire OS 6 NS6574/7623 in both slots → EchoLocal 0.0.8 → Home Assistant ESPHome integration → Assist.**

The USB host was a Synology DS620slim running a dedicated Linux container. Home Assistant Core 2026.9.1 ran remotely over an existing private route. The user confirmed a spoken Russian reply following **Okay Nabu**, using a Homeway-backed Assist pipeline. The flashing container was stopped, and the speaker continued to connect independently over Wi-Fi.

This confirms one basic end-to-end voice test. Cold power cycling, a 20-command acceptance series, extended stability, recovery from backup, and unattended batch conversion have not been validated here. [Acceptance record](docs/acceptance-and-batch.md).

A custom **Привет, Мышка** model is also installed in the second slot, with Okay Nabu retained in the first. Offline evaluation and deployment are complete, with two documented hard-negative errors. The initial user trial reported a problem; diagnosis is in progress and human spoken acceptance remains unconfirmed. See the [experiment and limitations](docs/custom-wake-word.md).

A separate **Привет, котик** recipe and candidate have now been trained and evaluated. The candidate remains private and undeployed: it detected 398/400 held-out synthetic positives, produced two hard-negative events, and failed strict numerical parity. The first verified ordinary-voice recording was missed in an offline diagnostic; personal adaptation and spoken acceptance remain pending. See the [Kotik stage record](docs/training-history.md#new-target-привет-котик).

## Required components

- **Hardware:** an Echo Dot 2, commonly labelled RS03QR, verified as BISCUIT over USB; a USB data cable; stable power; and a compatible Linux USB host. These images are not for other Echo generations.
- **Echo software:** the matched unlock/recovery/Fire OS/EchoLocal versions in the [conversion guide](research/conversion.md).
- **Home Assistant:** the built-in **ESPHome integration** and a working **Assist pipeline** with speech recognition, a conversation agent, and speech synthesis for the chosen language.
- **Network:** HA must reach the Echo on TCP 6053. The Echo must reach the actual HA media URL when URL playback is used. Manual IP-based pairing works across a private routed network.

**ESPHome Device Builder, HACS, Music Assistant, and a separate Linux Voice Assistant are not required for basic voice operation.** EchoLocal implements the ESPHome API on the Echo; it is not an ESP32 firmware project to compile in Device Builder.

## What runs where

```mermaid
flowchart LR
    U[Linux USB host: temporary conversion tools] -. USB during conversion .-> E[Echo Dot 2: EchoLocal and wake word]
    E <-->|Wi-Fi: ESPHome native API, TCP 6053| H[Home Assistant: ESPHome integration]
    H --> A[Assist pipeline: STT, conversation, TTS]
    E -->|Fetch HA media URL when used| H
    A --> S[Chosen local services or cloud provider]
```

The USB host is needed for conversion and later USB maintenance, not as a permanent voice controller. Wake-word detection runs on the Echo; HA selects speech processing. Removing Alexa does not make a remotely hosted HA or cloud speech service work offline.

## Documentation

Read these in order for the first device:

1. [Hardware families and compatibility](docs/hardware-compatibility.md): identify the generation, choose a supported route, and understand wrong-image risks.
2. [Ordered runbook](docs/runbook.md): execution locations, dependencies, and completion checks.
3. [Identify existing speakers](docs/known-devices.md): saved HA records, one-at-a-time power tests, and USB identity.
4. [USB host setup](docs/usb-host.md): Synology build, exact-device USB access, and cleanup.
5. [Conversion commands](research/conversion.md): pinned downloads, unlock, backup, A/B installation, and EchoLocal.
6. [Home Assistant setup](research/ha-integration.md): integrations, pipeline, pairing key, wake word, Area, exposed entities, and tests.
7. [Acceptance and repeated conversion](docs/acceptance-and-batch.md): what passed and what to test next.

Supporting material:

- [Device controls and limits](docs/device-controls.md): what can be read, changed or triggered, numeric ranges, options and fixed limits.
- [Operational findings](docs/operations-findings.md): dated checks on both Dots, resolved steps, remaining failures and evidence boundaries.
- [EchoLocal companion and dashboard](docs/echolocal-companion.md): HACS installation, cards on an existing media view, activity and diagnostics.
- [Device access and ADB diagnostics](docs/device-access.md): USB/Wi-Fi shell access, verified capabilities and maintenance boundaries.
- [Music startup latency](docs/music-latency.md): distinguish HA response time from Sendspin output delay and diagnose a disturbed clock estimate.
- [Custom Russian wake phrase](docs/custom-wake-word.md): train and validate a second phrase while retaining Okay Nabu.
- [Training commands, in order](training/README.md): environment, data, features, training, export, calibration, frozen test, recordings, packaging, and HA configuration.
- [Training history and unresolved results](docs/training-history.md): decisions, measured results, failed checks, and the first human trial.
- [Inventory template](inventory/devices.example.json): copy to an ignored local file.
- [Alternative projects](research/ecosystem.md): dated research, not extra required installation steps.
- [Echo Show 5 research](docs/show5-plan.md): a separate experimental route, not the tested Dot 2 procedure.
- [Publication checklist](docs/publication.md): clean export, attribution, and release decisions.
- [Third-party notices](THIRD_PARTY_NOTICES.md): upstream projects and redistribution boundaries.

## Tools and publication status

`python3 scripts/host_preflight.py` reports local host tools without contacting a device. Read the prerequisites before using any script under `host/synology/`.

`python3 training/pipeline.py --help` lists the separate training stages. Start with the [training instructions](training/README.md); commands keep downloads, recordings and model artifacts in a private work directory. Training and evaluation do not require a USB connection to the already converted Echo.

Prepare a fresh public copy with:

```bash
python3 scripts/prepare_public_release.py /path/to/new/ha-echo-dot-public
```

The destination must not exist. This copies only [allowlisted files](public-files.txt); it does not create a remote repository or publish anything. Review the output before sharing. No license for the original material has been selected; public visibility does not grant a separate reuse license. Keep the original workspace's private records, downloads, logs, and backups out of the repository.

## Related projects

- [Echo Show 5 Gen2 conversion](https://github.com/ha-homelab/ha-echo-show-5) is a
  separate Android display/voice-client route. Its firmware and recovery steps
  do not apply to the Echo Dot 2.
- [Amazon Echo Home Energy](https://github.com/4alvit/amazon-echo-home-voice)
  keeps the Alexa platform and adds a read-only energy skill. It does not convert
  the Echo into an EchoLocal satellite.
- [HA Homelab project directory](https://github.com/ha-homelab) lists the other
  public integrations and hardware guides.
