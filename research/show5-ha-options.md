# Echo Show 5 second generation: Home Assistant client options

**Research-only experimental appendix.** This document compares candidate software for **Echo Show 5 Gen 2 (2021), `cronos`**. It is separate from the Dot 2 / EchoLocal installation path. No ROM installation, device operation, or Home Assistant configuration change was performed for this research.

The evidence cutoff is **2026-10-01**. Versions below are historical pins, not claims about the latest release. Tagged release metadata and selected tagged TECHO5 sources were rechecked for this English edition. Other links to documentation or main branches are moving sources and should be reviewed again before implementation.

## Candidate order

First use the [hardware compatibility and identification guide](../docs/hardware-compatibility.md) to establish the exact target. Application choices do not make an incompatible unlock or OS image safe for a different generation.

For an Android display, the proposed first experiment is **model-specific unlock → TWRP → unofficial LineageOS 18.1 → Home Assistant Companion**. First verify the dashboard and button-triggered Assist. A dedicated voice/display application can be evaluated after the basic client works.

The ROM recorded at the cutoff was [LineageOS `cronos` v0.4](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4), published on **2026-09-05**. Its provenance, device boundaries, and limits are documented in the separate [Android source research](show5-android-sources.md). An ordinary Android tutorial cannot replace its model-specific unlock instructions.

**View Assist Companion App (VACA)** is a further Android option. **TECHO5** is a different operating environment: it replaces the Android runtime with Alpine Linux. Neither is a required extension of an EchoLocal Dot 2 installation.

## Android clients

### Home Assistant Companion

The official Android client is a candidate for the initial dashboard and Assist test. The [Android Assist documentation](https://www.home-assistant.io/voice_control/android/) describes on-device microWakeWord from Companion **2026.2.3**, with Home Assistant selected as the default digital assistant and a configured Assist pipeline. Wake-word detection is explicitly experimental.

This avoids adding a VACA integration for the first trial, but general Android feature support does not prove that the unofficial Show ROM supplies every required permission, audio behavior, or service correctly. Test the application on the selected image. Installing Android alone does not configure a voice pipeline.

### View Assist Companion App

The snapshot recorded [VACA v0.13.4](https://github.com/msp1974/ViewAssist_Companion_App/releases/tag/v0.13.4), published on **2026-09-28**. Its release notes report wake-word memory-leak and settings fixes. The application and its **VACA custom integration** should use matching versions; the release directs users to update the integration first.

The integration/release repository is `ViewAssist_Companion_App`; the Android source repository is `ViewAssistCompanionApp`. Their Releases pages did not show equivalent versions at the research date. The v0.13.4 APK was published with the integration release linked above.

VACA provides a WebView-based Home Assistant display plus voice and device controls. Its integration is distinct from the optional **View Assist integration**, which supplies additional views and scenarios. VACA requires its own integration even when used without View Assist. If automatic discovery fails, the setup page documents manual entry of the address and port displayed on the application's waiting screen. [VACA setup](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Getting-Started).

The recorded View Assist release was [2026.7.0](https://github.com/dinki/view_assist_integration/releases/tag/2026.7.0). This is a compatibility reference, not evidence that a particular Home Assistant installation has either custom integration installed.

For a small device, the proposed first VACA wake-word engine is microWakeWord: upstream configuration guidance describes it as lighter than openWakeWord. The selected Home Assistant pipeline still supplies STT, conversation handling, and TTS. Music ducking and noise reduction are not proof of stock Alexa far-field performance or fully effective echo cancellation. Avoid having several applications continuously compete for the same microphone. [Configuration options](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Configuration-Options).

### ShowAssist availability

The original research found historical descriptions of a Show-specific VACA fork named ShowAssist, but the [repository URL](https://github.com/HuskerMinion/showassist) and API returned 404 at the cutoff. The cause was not established. Do not infer present availability or active support from an old search result, and do not make an unverified mirror a dependency of the proposed installation.

## Android resources, camera, and media

The inspected [cronos hardware notes](https://github.com/HuskerMinion/techo5/blob/v0.9.25/docs/hardware.md) reported four Cortex-A53 cores, approximately **996 MB MemTotal**, **7.6 GB eMMC**, and a **960 × 480** display. These are upstream measurements, not this project's hardware measurements. Start with a small dashboard and one application, then measure the selected device. Memory findings from Show 8 / `crown` cannot be transferred to Show 5 / `cronos`.

The separate [camera/Bluetooth project](https://github.com/jxlarrea/lineageos-echo-show-camera) contains patches and implementation research. That alone does not prove their inclusion in every ROM. The selected `cronos` v0.4 changelog already reported a camera fix; see the [ROM sources](show5-android-sources.md). Additional patching on top of that release was not validated here. Its [echo-cancellation analysis](https://github.com/jxlarrea/lineageos-echo-show-camera/blob/main/docs/echo-cancellation.md) includes work on `crown`; do not present those measurements as `cronos` results.

Evaluate camera capture, VACA motion detection, Bluetooth, and concurrent audio separately. Compatible APKs and a functioning WebView do not establish DRM playback, particular codecs, video calls, or stable multi-day audio. A first media test can be limited to TTS, one ordinary audio stream, and one camera view.

## TECHO5 as a separate Linux option

The snapshot recorded [TECHO5 v0.9.25](https://github.com/HuskerMinion/techo5/releases/tag/v0.9.25), published on **2026-10-01**. The release explicitly labels its newly added AirPlay and Spotify Connect functions as **untested by the author**. Release frequency and a small upstream test fleet do not prove stability on another device.

TECHO5 uses Alpine armv7 and an EchoLocal-derived `echod` rather than an Android application or launcher. Its documented features include an ESPHome-compatible voice satellite, local microWakeWord, playback, a native display interface, camera support, and A/B updates. Its documented recovery arrangement includes returning to LineageOS, but no such transition was tested in this project. [Pinned project documentation](https://github.com/HuskerMinion/techo5/tree/v0.9.25), [architecture](https://github.com/HuskerMinion/techo5/blob/v0.9.25/docs/overview.md).

The pinned [cronos audio source](https://github.com/HuskerMinion/techo5/blob/v0.9.25/echod/internal/hardware/mic/device_cronos.go) distinguishes **two microphone channels and two playback-loopback channels**. It disables the vendor beamformer. A [WebRTC helper](https://github.com/HuskerMinion/techo5/blob/v0.9.25/echod/internal/hardware/mic/webrtc.go) provides an echo-cancellation path. An older description of four audio channels must not be read as four physical microphones or preserved stock Alexa processing. Practical performance during music and television playback remains a test requirement.

The pinned dashboard documentation describes two display modes:

- **Drawn:** the device renders supported card descriptions itself. It does not run arbitrary custom-card JavaScript as a browser would.
- **Streamed:** a separate **dashcast** service runs Chrome near Home Assistant, sends the rendered image, and accepts touch events. This can render the actual frontend and custom cards, but adds a service, network traffic, and latency. It does not add Android applications to TECHO5.

See [dashboard modes](https://github.com/HuskerMinion/techo5/blob/v0.9.25/docs/dashboards.md). The [dashcast README](https://github.com/HuskerMinion/techo5/blob/v0.9.25/dashcast/README.md) estimates **150–250 MB RAM per displayed dashboard**. Treat that as an upstream planning estimate, then measure one screen on the intended server.

The pinned [setup documentation](https://github.com/HuskerMinion/techo5/blob/v0.9.25/docs/setup.md) also describes camera views, music, Sendspin, Bluetooth, and SIP. These are Linux application features, not transfers of Android APKs, Alexa skills, or Amazon Drop In. Add them after the core voice/display trial passes.

## Network requirements by client

The following is a generic planning model. No household addresses, DNS names, VPN configuration, or live Home Assistant inventory are included. Replace symbolic hosts with values kept in private deployment configuration.

1. **Companion:** the Show initiates HTTP(S)/WebSocket connections to the reachable Home Assistant endpoint. It also needs access to any referenced media. This path does not require adding an ESPHome or VACA listener to the Show.
2. **VACA:** Home Assistant connects to the application's TCP server, recorded as default **10800**. Use the actual port shown on the waiting screen. This is the VACA/Wyoming path, **not ESPHome port 6053**. The Show also opens the Home Assistant frontend and media/TTS URLs. Add it through the VACA integration; manual IP/port setup is available when discovery does not reach it. The inspected server is ordinary TCP, so keep its traffic on an appropriate trusted private network or protected tunnel. [Server implementation](https://github.com/msp1974/ViewAssistCompanionApp/blob/main/app/src/main/java/com/msp1974/vacompanion/wyoming/WyomingTCPServer.kt), [integration manifest](https://github.com/msp1974/ViewAssist_Companion_App/blob/v0.13.4/custom_components/vaca/manifest.json).
3. **TECHO5:** Home Assistant connects to **TCP 6053** using the device's ESPHome encryption key. The pinned voice implementation uses the API audio path and does not implement legacy UDP audio. The Show separately needs a reachable Home Assistant URL for functions such as REST access, media, weather, and cameras. The pinned setup requests a direct internal address and an HA access token. Do not assume an external proxy or `.local` name is an equivalent working endpoint. [Voice transport](https://github.com/HuskerMinion/techo5/blob/v0.9.25/echod/internal/feature/voice/conversation.go), [HA access setup](https://github.com/HuskerMinion/techo5/blob/v0.9.25/docs/setup.md#1-give-the-device-access-to-home-assistant).
4. **Optional TECHO5 services:** a streamed dashboard adds Show → dashcast **TCP 9555**. The pinned setup describes Music Assistant connections to **TCP 8095 and 8927** on the Music Assistant host, including routed/VPN use. These services can have different hosts. Do not assume the Home Assistant address is also their address.
5. **MQTT is not required** for these basic client paths. Likewise, ESPHome Device Builder does not compile VACA or TECHO5. Install optional companion services using the deployment mechanism actually available: Home Assistant Container does not acquire HA OS add-ons simply because a guide mentions them.

mDNS discovery should not be assumed to cross routed subnets or a VPN. Check both connection directions and URL reachability from the device, not just from an administrator's computer. Store API keys and access tokens outside tracked examples.

On-device wake-word detection does not imply that the whole conversation is local. A remote Home Assistant deployment depends on its network path; cloud speech services remain cloud services after the client is converted. For an offline goal, evaluate the location and dependencies of every stage.

## Proposed acceptance evidence

After a separately reviewed unlock/ROM procedure, test Android boot, Wi-Fi, a small dashboard, text Assist, button-triggered voice, wake word, repeated commands, speech during playback, stop/recovery, mute/unmute, power cycling, and reconnection after network loss. Record one full day of operation before adding cameras or more media services. For TECHO5, test its selected native or streamed display path instead of Android application behavior.

If the Home Assistant frontend stalls at the logo, test transfer reliability on the same route before concluding that Android or WebView is incompatible. [Frontend issue #53819](https://github.com/home-assistant/frontend/issues/53819) was recorded as a case resolved by fixing an access point. It is a diagnostic example, not evidence about another network.

Physical compatibility, a complete recovery, application/integration interoperability, language quality, echo cancellation, and long-term stability remain **unverified by this project**. The [Show 5 plan](../docs/show5-plan.md) turns these research questions into staged evaluation checkpoints; it is not a claim that any Show has been converted.
