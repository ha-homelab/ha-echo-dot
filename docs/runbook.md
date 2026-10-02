# Ordered runbook: from an existing Echo to Home Assistant

First read [hardware families and compatibility](hardware-compatibility.md) to establish whether this route applies. Then use this order for one stock Echo Dot 2. The [conversion guide](../research/conversion.md) contains device commands; the [USB guide](usb-host.md) contains host/container commands. Complete one checkpoint at a time rather than combining all stages into an unattended script.

The demonstrated versions are EchoLocal 0.0.8, amonet-biscuit 2.0.0, TWRP 3.7.0_9-0, Fire OS NS6574/7623, and HA Core 2026.9.1. Other generations, Android SDKs, or installer versions require a fresh compatibility check.

## 1. Identify one physical candidate

**Where:** the speaker and, optionally, HA's device registry.

Use an existing Alexa device record to narrow the model search. Power one candidate at a time and compare availability to identify it. Inspect its label and record its serial if visible. This is provisional identification; USB product **BISCUIT** and the serial will be checked after preparing the host in step 4. A room name does not prove its current location. [Identification procedure](known-devices.md).

Assign a neutral asset ID such as `echo-001`. Copy [the inventory template](../inventory/devices.example.json) to `inventory/devices.local.json` and fill it privately.

**Continue when:** one physical candidate is associated with a provisional inventory record and its label/HA information indicates Dot 2. Do not select images for an Echo Show, full-size Echo, or another Dot generation using this route.

## 2. Prepare the HA voice pipeline

**Where:** Home Assistant, preferably before changing the speaker.

In **Settings → Voice assistants**, prepare an assistant with speech-to-text, a conversation agent, text-to-speech, and compatible language settings. Test it from an HA client with microphone access. A saved pipeline without STT cannot serve a physical voice satellite.

The pilot used an existing Homeway service and a separate Russian pipeline. That provider is an example, not a requirement. Choose one backend path from the [HA guide](../research/ha-integration.md); do not install every alternative.

**Continue when:** HA understands a test utterance and generates a reply in the intended language. This can be prepared independently of the USB conversion.

## 3. Prepare networking and private storage

**Where:** router, HA host, and USB host.

Choose Wi-Fi for the Echo and plan a DHCP reservation once its Wi-Fi MAC is known. Permit HA to initiate TCP 6053 to the Echo. For URL playback, the Echo must reach the actual media URL HA returns, including DNS and HTTP/HTTPS routing. Do not expose the API to the public Internet.

For HA on another subnet or behind a private VPN, pair by IP; cross-subnet discovery is not required. If HA produces an unreachable media URL, review **Settings → System → Network** and the [HA network guidance](../research/ha-integration.md).

Create protected per-device storage for credentials, keys, installer logs, and backups. Allow room for a full uncompressed eMMC image, boot regions, and a verified working copy. The pilot's main eMMC was approximately 3.9 GB; measure the actual device size.

**Continue when:** storage is ready and both the API route and reply-audio route are understood.

## 4. Prepare the USB host and artifacts

**Where:** a Linux USB host; the pilot used Docker on the physical Synology NAS.

Follow [USB host setup](usb-host.md). Download the pinned artifacts, verify their hashes, and build the host image for the Synology route. This container is temporary tooling, not an HA add-on.

Use a data-capable cable: a lit ring proves power, not USB data. Expose only the intended speaker to the conversion environment. Keep the complete amonet directory and its bundled fastboot for unlocking.

**Continue when:** tools run, verified files are available, and read-only inspection in stock fastboot confirms **BISCUIT** and the intended serial. Use the inspection commands at the start of the conversion guide, then return to step 5 only after the identity matches. Do not unlock an unidentified device.

## 5. Unlock and verify recovery

**Where:** commands on the USB host; button/power actions on the Echo.

Follow the matched unlock stage in the [conversion guide](../research/conversion.md). The stock-fastboot pilot used the Action button while connecting USB power, followed by upstream `fastbrick.sh`.

Unlocking changes the boot chain before this procedure provides full backup access. Script success alone is not the recovery check.

**Continue when:** the same serial appears in ADB recovery, TWRP runs, and root access is verified. Record the active slot and partition aliases.

## 6. Save and verify the post-unlock backup

**Where:** read the Echo over ADB; save images on the USB host.

Save any needed device configuration privately before wiping. Unmount the relevant eMMC filesystems and follow the [backup procedure](../research/conversion.md). Verify decompressed image byte counts and SHA256 against the device. The helper stores eMMC, boot0, boot1, and a manifest.

**Continue when:** every required image is complete and verified. A `.partial` file is not a backup. This is a post-unlock backup; RPMB and a proven return to the original factory boot chain are outside the demonstrated result.

## 7. Install compatible Fire OS in both slots

**Where:** TWRP on the Echo, controlled from the USB host.

After the backup passes, follow the wipe and OTA commands in the [conversion guide](../research/conversion.md). In the pilot, the first OTA wrote inactive B and selected B automatically. After rebooting recovery into the selected slot, the second OTA wrote inactive A and selected A automatically.

Do not blindly switch to the opposite slot after the OTA has already switched it. Check the actual target and active slot each time. The guide also covers read-only build checks for the system-as-root layout.

**Continue when:** both slots report the intended build and SDK 25, with recovery in the expected active slot.

## 8. Install EchoLocal and configure Wi-Fi

**Where:** `echoctl` on the USB host, with the Echo connected over ADB.

Supply the exact serial, a unique name, and the chosen Wi-Fi credentials. The private wrapper captures full installer output because it may contain the ESPHome key. It intentionally writes boot and reboots; use it only after the preceding checks.

Wait for Wi-Fi association as well as the EchoLocal resident state. In the pilot, the service became resident before the Wi-Fi control socket was ready. Save the unique Noise key privately and record the Wi-Fi MAC and assigned IP.

**Continue when:** boot is complete, EchoLocal is resident, Wi-Fi is connected, the key is saved, and HA can reach TCP 6053.

## 9. Pair with HA's ESPHome integration

**Where:** Home Assistant UI.

Open **Settings → Devices & services → Add integration → ESPHome**. Enter the reachable Echo IP and port **6053**, then its own encryption key when prompted. If discovery already presents it, configure that entry rather than creating a duplicate.

Use the built-in ESPHome integration. Do not adopt or compile the Echo in ESPHome Device Builder. [Detailed HA instructions](../research/ha-integration.md).

**Continue when:** the integration loads and the Echo has an Assist satellite and a speaker/media-player entity. Record your actual entity names; documentation examples are placeholders.

## 10. Select the assistant, wake word, and room

**Where:** the Echo's HA device page and HA voice settings.

Select the working pipeline for the first assistant slot and **Okay Nabu** for its wake word. Turn microphone mute off and set moderate volume. Assign the speaker to its actual HA Area and expose a suitable light or test entity to Assist for the later control test.

The pilot used Russian speech with an English activation phrase. Pipeline language does not replace the wake-word model. You do not need to change the global preferred assistant to configure one speaker.

After the basic voice test works, follow the [custom wake-word guide](custom-wake-word.md) to add a phrase such as **Привет, Мышка** in the second slot. Keep the working first slot while validating the new model.

**Continue when:** the intended pipeline and wake word are selected, and microphone and speaker are enabled.

## 11. Test the complete voice path

**Where:** at the physical Echo, with HA available for diagnostics.

Send a short announcement from HA. Then say **Okay Nabu**, wait for the listening cue, and ask for a brief spoken reply in the configured language. Hearing the answer verifies more than a successful API connection. Separately test one harmless, reversible entity action.

The pilot user confirmed the requested Russian response, “Ready.” This establishes the basic voice path, but not room-light control, cold boot, or long-term stability.

**Continue when:** a spoken reply is physically audible and the record reflects the actual test. Follow the [acceptance checklist](acceptance-and-batch.md) for extended checks.

## 12. Stop temporary tooling and repeat deliberately

**Where:** USB host, inventory, and the final speaker location.

Stop the dedicated conversion container, then the serial-specific USB proxy. Keep downloads, backups, and keys. The speaker works over Wi-Fi without those processes. It can use an appropriate USB power supply; its first full power cycle remains an acceptance check.

Record the installed version, reserved IP if configured, Area, assistant, and actual test results. Identify the next speaker by model and serial and repeat from step 1. Never clone one speaker's full backup or encryption key onto another.

For public sharing, use the [publication procedure](publication.md) to export only reviewed files.
