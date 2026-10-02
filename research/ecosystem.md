# EchoLocal and related projects

Research snapshot: **2026-10-01**. Release versions, repository activity, issue status, and support claims below describe that snapshot. They are not statements about the latest available software. Recheck upstream before selecting files for a device.

**Recommended starting point for this project:** one identified **Echo Dot 2 (2016, RS03QR, `biscuit`)**, the compatible unlock/Fire OS branch, and pinned **EchoLocal 0.0.8** connected directly to Home Assistant through its ESPHome integration. Verify one device before repeating the procedure. This recommendation compares the documented components and installation paths; it is not a measured conversion time or a successful hardware result from this project.

The research inspected upstream documentation, release metadata, commits, issues, and installer source. It did not unlock, flash, or test a physical Echo. The [conversion research](conversion.md) and [Home Assistant integration guide](ha-integration.md) cover the next checks.

## EchoLocal findings

- The [upstream project](https://github.com/ygelfand/echolocal) describes a Dot 2 voice satellite implemented by `echod`, replacing Amazon services and speaking the ESPHome native API. It is a Go application on the Echo, not an ESP32 board or an ESPHome YAML firmware build.
- [Release 0.0.8](https://github.com/ygelfand/echolocal/releases/tag/0.0.8) was published on **2026-09-30 at 16:47 UTC**. The inspected [commit `6eff3b1`](https://github.com/ygelfand/echolocal/commit/6eff3b12db168223df3871f0a56250e736d3954a) was dated **2026-09-30 at 12:31 UTC**. This was evidence of active development at the research date, not a guarantee of reliability across every feature.
- Upstream advertised on-device openWakeWord and microWakeWord, speaker playback, the LED ring, a BLE advertisement proxy, and a light sensor. The [EchoLocal HACS companion](https://github.com/ygelfand/echolocal-hacs) adds management and diagnostics; it is optional for basic voice integration. Its recorded release was `v0.0.7`, published on **2026-09-20**.
- `echoctl` expects a device that has already been unlocked with a suitable recovery such as TWRP. **`echoctl install` is not the initial factory-device unlock.** Use the model-specific [amonet-biscuit source instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-2nd-gen-2016-biscuit.4761416/) for that separate stage.
- The [0.0.8 installer source](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/installer/installer.go#L164) explicitly requires **SDK 25 / Fire OS 6**. It rejects SDK 22 / Fire OS 5 and points to installer `0.0.6` or earlier. [Issue #45](https://github.com/ygelfand/echolocal/issues/45) documents this distinction. Do not mix a Fire OS 5 installation guide with the 0.0.8 installer. This installer requirement alone does not establish the compatibility of every existing daemon installation or OTA upgrade.

For a new stock-device pilot, select a consistent unlock, Fire OS, and installer combination. For an already unlocked Fire OS 5 device, evaluate the separate legacy branch in the conversion research before adding an OS migration.

## Model boundaries

Use the [hardware compatibility and identification guide](../docs/hardware-compatibility.md) to distinguish families and generations, understand the model-specific constraints, and assess the consequences of selecting the wrong image. The list below records this research snapshot; missing support is not a claim that a future port is impossible.

1. **Echo Dot 2, RS03QR / `biscuit`:** the upstream EchoLocal target in the inspected release. Confirm the physical label, software state, and working USB data connection.
2. **Full-size Echo 2, AEORD / `radar`:** [PR #64](https://github.com/ygelfand/echolocal/pull/64) was an open draft at the snapshot. Its author reported device testing and several Bluetooth, light-sensor, Sendspin, and output-switching limitations. Treat it as a separate experimental port. A Dot 2 image must not be assumed suitable.
3. **Echo Show and Echo Spot:** the [TECHO5 family](https://github.com/HuskerMinion/techo5) documented several model-specific ports, with different amounts of author testing. This project keeps **Show 5 second-generation research in a separate, untested appendix**: [Show 5 plan](../docs/show5-plan.md). It does not extend the Dot 2 procedure to a display device.
4. **Dot 3/4/5 and other Echo models:** support was not established by the inspected EchoLocal release. [EchoMuse](https://github.com/wilbowes/EchoMuse) described other ports as work in progress at the snapshot. An old Echo is not necessarily a compatible Echo.

No household inventory is included here. Compatibility must be established per physical device before choosing an image.

## Setup Wi-Fi and unattended batches

**Verified source behavior:** the [0.0.8 CLI](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/cli/echoctl/install.go#L146) provides `--serial`, `--name`, Wi-Fi options, and reboot options. It can address a particular USB device after the unlock stage. `--yes` approves a boot-partition overwrite; it is not a diagnostic option. The presence of `--zero-psk` does not make that mode necessary for a normal pilot.

The inspected documentation described Wi-Fi provisioning through `echoctl` and an encryption key printed by the installer. Inspection of the README and Go source in the 0.0.8 archive did not establish a built-in batch command, captive portal, or initial setup access point. This is a source review, not a hardware test.

**Interpretation:** a third-party sales post describing its own setup Wi-Fi, web pairing page, and unattended conversion process cannot establish those as upstream EchoLocal features. A reproducible public source for that particular workflow was not identified. This project does not depend on it.

**Recommendation:** keep a private per-device record of model, software state, serial, backup, room, installed version, and acceptance result. Repeat the proven procedure one explicitly selected serial at a time. Do not put Wi-Fi passwords, pairing keys, device backups, or real serials into a public repository. USB-hub batch unlocking and automatic recovery of arbitrary connected devices require separate validation; `--serial` in EchoLocal does not validate amonet or fastboot batch behavior. See [acceptance and repeated installation](../docs/acceptance-and-batch.md).

## Alternatives considered

**EchoMuse: a candidate when managing multiple devices matters.** The snapshot recorded [v2.17.0](https://github.com/wilbowes/EchoMuse/releases/tag/v2.17.0), published on **2026-09-29**, and repository activity on **2026-10-01**. Its documented controller runs in Docker or as a Home Assistant add-on, manages devices, and coordinates which device answers a shared wake word. It supports Dot 2; the emOS path described unlocked Fire OS 5 and 6 devices. The additional controller is an operating dependency. The inspected README contained differing statements about the default location of wake-word detection, so verify the selected version's actual setting. Evaluate it after a direct EchoLocal pilot if overlapping rooms or device administration become a problem. [Project documentation](https://github.com/wilbowes/EchoMuse).

**TECHO5 Dot: a separate Linux runtime.** The recorded [dot-v0.5.51](https://github.com/HuskerMinion/techo5-dot/releases/tag/dot-v0.5.51) was published on **2026-10-01**. The project builds on EchoLocal with Alpine, on-device activation, ESPHome API, and signed updates with rollback. The inspected README reported daily use on three units. It is useful for a separate OS/audio comparison, but adds a runtime replacement to the first-conversion path. [Project documentation](https://github.com/HuskerMinion/techo5-dot).

**postmarketOS/Nura with Linux Voice Assistant: an early experimental alternative.** The recorded first [v1.0 release](https://github.com/liamtw22/pmaports-biscuit/releases/tag/v1.0) was published on **2026-09-30**. It advertised seven-microphone processing, echo cancellation, setup Wi-Fi, and ESPHome integration through Linux Voice Assistant. The inspected documentation identified repartitioning, a patched release-candidate kernel, testing on two units, and an unverified end-to-end Fire OS restore. Those limits make it a later research candidate, not the first repeated-installation procedure. [Project and known issues](https://github.com/liamtw22/pmaports-biscuit).

**Overdub: retaining Alexa while adding controls.** The recorded [v0.2.0](https://github.com/bboe/overdub/releases/tag/v0.2.0), published on **2026-09-25**, adds buttons, entities, and Sendspin to a rooted Dot 2 while retaining Alexa. Its [documented purpose](https://github.com/bboe/overdub) differs from replacing the voice assistant with local Home Assistant Assist.

## ESPHome API, Linux Voice Assistant, and Wyoming

The snapshot recorded [Linux Voice Assistant](https://github.com/OHF-Voice/linux-voice-assistant) release `v1.1.15` from **2026-08-02** and a main-branch commit from **2026-09-29**. This Open Home Foundation project uses the ESPHome API and supports local wake-word processing, playback, announcements, conversation control, and timers. It requires a supported Linux and audio environment; it is not an Echo unlock tool or a universal package for stock Amazon software. The pmaports-biscuit project supplies a separate OS port for that approach.

[Wyoming Satellite](https://github.com/rhasspy/wyoming-satellite) was deprecated and archived at the snapshot, with its README directing users to Linux Voice Assistant. That is a reason not to choose it for a new satellite implementation. **It does not deprecate the Wyoming protocol:** Home Assistant also uses Wyoming to connect speech services such as STT and TTS. [Home Assistant Wyoming integration](https://www.home-assistant.io/integrations/wyoming/).

EchoLocal already implements the device side of the ESPHome API. It does not need a Linux Voice Assistant service inserted between the Dot and Home Assistant.

## Language, audio quality, and local operation

The [0.0.8 assets](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/assets/models.go) include `okay_nabu`, `hey_jarvis`, and `hey_mycroft`; the [default](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/lib/wake/models.go#L19) is `okay_nabu`. A bundled Russian wake-word model was not established. A practical multilingual pilot starts with a bundled activation phrase and tests commands in a language supported by the selected Assist pipeline.

Wake-word detection, speech recognition, conversation handling, and speech synthesis are separate stages. Removing Amazon services from the Echo does not make a cloud STT, conversation agent, remote Home Assistant server, or TTS service local. On-device activation also does not establish that the Dot runs the complete STT or LLM workload itself.

Test quiet and noisy rooms, music playback, false activations, stopping an answer, microphone recovery, power cycling, and overlapping rooms. At the research date, reports included [stop during playback #85](https://github.com/ygelfand/echolocal/issues/85), [microphone recovery #24](https://github.com/ygelfand/echolocal/issues/24), [false activations #71](https://github.com/ygelfand/echolocal/issues/71), and [announcements #77](https://github.com/ygelfand/echolocal/issues/77). These are historical user reports, not proof that every device or later release has the same defect. [Dev OTA #93](https://github.com/ygelfand/echolocal/issues/93) concerned a development-channel free-space failure; do not automatically apply that finding to stable 0.0.8.

## Existing Alexa skills

An Alexa custom skill and a Home Assistant voice satellite are separate integrations. Converting a Dot through the selected EchoLocal route removes its normal Alexa voice service, so custom-skill invocation does not transfer automatically. Existing Alexa skills can continue serving unconverted devices.

To preserve an existing reporting use case, implement equivalent Assist intents or scripts against the same authorized source of data. Preserve any read-only access and freshness rules in that source. A working Alexa backend does not prove that the corresponding Home Assistant entities, intents, permissions, or speech pipeline are configured. No private application paths or deployment details are required by this research.

## Remaining evidence needed

- Exact model and software state of each candidate device.
- A successful physical pilot and its measured conversion time, audio quality, and recovery behavior.
- Any public source for the third-party setup-AP and unattended workflow, if those features become necessary.
- A two-device test before choosing direct satellites or a coordinating controller.
- Verification of the intended language and speech pipeline in the target Home Assistant deployment.

The reproducible research baseline is EchoLocal `0.0.8` at `6eff3b12db168223df3871f0a56250e736d3954a`, paired with an identified Dot 2 and the compatible installation branch. The baseline is a source pin, not a certification or a claim that it remains the newest release.
