# Echo Dot 2 to Home Assistant: conversion runbook

Research checked on October 1, 2026; the physical pilot completed on October 2 UTC. This guide pins the artifacts used in that pilot, rather than tracking `latest` automatically.

**Proven on one device:** stock Echo Dot 2 → amonet 2.0.0 → TWRP → verified post-unlock backup → Fire OS 6 in both slots → EchoLocal 0.0.8 → ESPHome pairing → a spoken command and audible reply. A Russian Assist pipeline and the English-trained **Okay Nabu** wake word worked in that basic test. The installer also completed a warm reboot. **Cold power-on, extended acoustic testing and a 24-hour soak remain untested.** Use the [acceptance checklist](../docs/acceptance-and-batch.md) before repeating the conversion across a collection.

## 1. Confirm the device and route

This route is for the **2016 Echo Dot, second generation, model RS03QR, codename `biscuit`**. Confirm the label and then the USB product `BISCUIT`. EchoLocal runs `echod` on a modified Fire OS base and replaces Amazon services; the hardware does not become an ESP32. The resulting satellite connects directly to Home Assistant's ESPHome integration. [Pinned README](https://github.com/ygelfand/echolocal/blob/0.0.8/README.md).

Do not apply these images to an Echo Show, another Dot generation, or the full-size Echo 2. Consult the [hardware compatibility guide](../docs/hardware-compatibility.md) for other models. At the research checkpoint, full-size Echo 2 support (`radar`) was a separate proposal, outside this tested stable route. [PR 64](https://github.com/ygelfand/echolocal/pull/64), [issue 65](https://github.com/ygelfand/echolocal/issues/65).

An already unlocked **amonet 1.x / Fire OS 5 / SDK 22** device is a separate branch: installer **0.0.6** can avoid an OS migration for an initial test. The maintainer clarified that 0.0.7+ dropped Fire OS 5 from the installer; existing-device OTA builds still cover both architectures. Do not rerun fastbrick on an unlocked device. [Maintainer explanation](https://github.com/ygelfand/echolocal/issues/45), [0.0.6 release](https://github.com/ygelfand/echolocal/releases/tag/0.0.6).

Prepare a Linux or Windows USB host, a reliable micro-USB **data** cable, stable power and one identified Dot. The amonet 2 author documents Linux and Windows (`fastbrick.sh` / `fastbrick.bat`); initial unlocking on macOS was not verified. EchoLocal itself has Linux, macOS and Windows binaries.

The commands below use Bash on native Linux or the [scoped Synology container](../docs/usb-host.md). **Prepare that host first.** Its guide defines `adbe`, `fbe`, `run_fastbrick`, `backup_echo`, `install_echo_private`, `HAE_PRIVATE` and `OTA_FILE`. The same conversion commands then work with either host adapter.

## 2. Pin and verify the artifacts

- **amonet-biscuit 2.0.0:** [author's XDA attachment](https://xdaforums.com/attachments/amonet-biscuit-v2-0-0-zip.6383906/), 55,989,416 bytes. Observed SHA-256: `98297293701082bc7272efe077f941c56fc7b6e1f27ef6f2e93b6e4c6fc7b62d`. Source branch `mt8163-biscuit`, pinned commit [`0aac01a5daa60b0a4b958dd127c46feb9daaaceb`](https://github.com/R0rt1z2/amonet/tree/0aac01a5daa60b0a4b958dd127c46feb9daaaceb), September 11, 2026. Use the complete ZIP with payloads, TWRP and modified `bin/fastboot`; a source checkout or distribution fastboot is not equivalent.
- **Fire OS 6.5.7.4, NS6574/7623**, incremental build `13121734532`: `update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin`, 112,957,575 bytes. Observed SHA-256: `64ab6d2dd85f8093abdd62c275d229c7e9fdd68e4d46892b48bdbd1d100d46d8`. Catalog MD5: `f1678283cc18d681740410883eee3e2c`. Download from the [Amazon update CDN](https://d1s31zyz7dcc2d.cloudfront.net/2026/8/3/f49aaff7-dd63-4d9c-9e9a-c17498267de5/update-kindle-biscuit_puffin-NS6574_user_7623_0013121734532.bin); [catalog metadata](https://ftvdb.com/echo/firmware/com.amazon.biscuit.android.os/f1678283cc18d681740410883eee3e2c-13121734532-fire-os-6-5-7-4-ns6574-7623-2026-08-03/). This is EchoLocal's tested boot-image baseline. Newer builds are a different test, not a silent substitution.
- **EchoLocal 0.0.8:** [release](https://github.com/ygelfand/echolocal/releases/tag/0.0.8), September 30, 2026 at 16:47:07 UTC; commit [`6eff3b12db168223df3871f0a56250e736d3954a`](https://github.com/ygelfand/echolocal/commit/6eff3b12db168223df3871f0a56250e736d3954a). Linux x86-64 binary `echolocal_linux_x86_64`: SHA-256 `a350601761bc52ef865eba63b7117e6a63315c9541a780bd1f6d6984b7bde396`. macOS arm64: `aeb38d0287110cab662e81c18e12c4b042f9360f8b4b80c91f852ac4f8c4b3b5`. Compare your selected binary with the [release checksums](https://github.com/ygelfand/echolocal/releases/download/0.0.8/checksums.txt).

The amonet and OTA SHA-256 values record downloaded pilot artifacts, not publisher signatures. MD5 is an additional catalog comparison, not authentication. The host guide gives verification and extraction commands.

No separate `boot-root.zip` is needed. Release `echoctl` embeds the boot image, `echod`, system patches and initial wake models, and can install from TWRP with an offline USB host. ADB must already be installed. [Release build](https://github.com/ygelfand/echolocal/blob/0.0.8/.goreleaser.yaml), [embedded assets](https://github.com/ygelfand/echolocal/tree/0.0.8/internal/host/assets).

## 3. Unlock the selected stock Dot

On native Linux, disconnect any other fastboot target: `fastbrick.sh` does not take a serial argument. The Synology proxy exposes only the selected serial and physical port.

1. Disconnect the cable **at the Dot**. Hold **Action**, the button marked with a dot, while reconnecting it. Release the button when the ring turns **green**: stock fastboot.
2. Inspect identity without writing:

   ```bash
   fbe devices
   fbe getvar product
   fbe getvar unlock_status
   fbe getvar lk_build_desc
   ```

   Require the intended serial, `BISCUIT` and a locked stock device. Record the LK build privately. Stop if the identity differs or unlocking is already reported.
3. Run the author's script with its bundled fastboot:

   ```bash
   run_fastbrick
   ```

   Check its device and selected payload, then enter `YES`. Keep USB and power connected during the exploit. The script's “most likely successful” message is not the completion checkpoint: it uses a fastboot timeout as an indication that the payload took over.
4. Wait for **TWRP with a white ring**, then verify it directly:

   ```bash
   adbe get-serialno
   adbe get-state
   adbe shell id
   adbe shell getprop ro.twrp.version
   adbe shell bcbtool get_active
   adbe shell getprop ro.boot.slot_suffix
   adbe shell 'ls -l /dev/block/current-* /dev/block/platform/bootdevice/by-name/'
   ```

   The pilot reached TWRP `3.7.0_9-0`, ADB state `recovery`, root and the same serial. Do not infer success from the LED alone.

The script rejects device mismatch and diagnoses permanent read-only eMMC as `eMMC-RO`. That is a storage failure, not a reason to keep retrying writes. [Pinned script](https://github.com/R0rt1z2/amonet/blob/0aac01a5daa60b0a4b958dd127c46feb9daaaceb/fastbrick.sh), [author's complete instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-2nd-gen-2016-biscuit.4761416/).

## 4. Verify a post-unlock backup before erasing anything

**Unlock has already changed the boot chain.** This is the first verified full-backup opportunity in the stock fastbrick route. It preserves the post-unlock state, without promising restoration of the untouched stock bootloader or Alexa service.

Save the starting state outside version control:

```bash
adbe shell getprop > "$HAE_PRIVATE/twrp-properties.txt"
adbe shell bcbtool get_active > "$HAE_PRIVATE/initial-active-slot.txt"
adbe shell 'ls -l /dev/block/current-* /dev/block/platform/bootdevice/by-name/' > "$HAE_PRIVATE/partitions.txt"
adbe shell cat /proc/mounts
```

Resolve block-device aliases in that output before deciding which filesystems are backed by eMMC:

```bash
adbe shell 'while read source target rest; do
  case "$source" in
    /dev/*) printf "%s on %s resolves to " "$source" "$target"; readlink -f "$source" ;;
  esac
done < /proc/mounts'
```

If a mounted source resolves to a device-mapper node such as `dm-0`, inspect its `/sys/class/block/dm-0/slaves/` entries as well. The helper only rejects a literal `/dev/block/mmcblk0` mount string; that check alone is not proof that aliases or mapper devices are unmounted.

Unmount mounted eMMC filesystems before the raw read. These are the usual data/cache mounts; an already-unmounted path can report an error. Check for additional mounted system or persist partitions instead of treating these commands as exhaustive:

```bash
adbe shell umount /sdcard
adbe shell umount /data
adbe shell umount /cache
adbe shell cat /proc/mounts
```

With no eMMC filesystem mounted, run the repository's [backup helper](../host/synology/backup_postunlock.py) through the selected host adapter:

```bash
backup_echo
```

It reads `/dev/block/mmcblk0`, `mmcblk0boot0` and `mmcblk0boot1` through binary-safe `adb exec-out`, compresses on the device, and verifies **decompressed byte count plus SHA-256 against a fresh device read**. Completion requires `POST-UNLOCK BACKUP VERIFIED` and three entries in the private `manifest.json`. A `.partial` file or partly populated manifest is not a completed backup. Never reuse an incomplete destination or proceed to wipe before this passes.

The pilot read 3,909,091,328 bytes from the main eMMC and 4,194,304 bytes from each boot area; measure each device independently. Reading and verification took about 20 minutes. RPMB and hardware-bound secrets were not exported. Keep a separate protected copy of the verified backup. Images, raw properties and saved Wi-Fi files can contain credentials and personal data.

TWRP's named partitions and active-slot aliases are in the [device fstab](https://github.com/R0rt1z2/twrp_device_amazon_echo-mt8163/blob/main/ab/recovery/root/etc/recovery.fstab). A TWRP filesystem backup can supplement the raw checkpoint. [TWRP CLI reference](https://twrp.me/faq/openrecoveryscript.html).

## 5. Install the pinned OTA in both slots

This stage **erases data and settings**. `OTA_FILE` is the verified file path as seen by the selected ADB process. Remain in TWRP; do not flash stock firmware through stock fastboot.

```bash
adbe shell twrp wipe cache
adbe shell twrp wipe data
adbe push "$OTA_FILE" /sdcard/update.zip
adbe shell sha256sum /sdcard/update.zip
```

Require the OTA SHA-256 from section 2. Record the active slot and run the first installation:

```bash
adbe shell bcbtool get_active
adbe shell twrp install /sdcard/update.zip > "$HAE_PRIVATE/ota-first.log" 2>&1
adbe shell bcbtool get_active
```

**Inspect the log and slot before continuing.** With the tested TWRP/OTA pair, installation targets the **inactive** slot and automatically selects it afterward. Starting on A, the pilot logged `Flashing A/B zip to inactive slot: B`, completed successfully and selected B. Exit status alone does not prove OTA success.

Reboot recovery into the newly selected slot, wait for the same serial to return as `recovery`, and compare all slot indicators:

```bash
adbe reboot recovery
# Wait for USB re-enumeration and the white TWRP ring.
adbe get-state
adbe shell bcbtool get_active
adbe shell getprop ro.boot.slot_suffix
adbe shell 'ls -l /dev/block/current-boot /dev/block/current-system'
```

From B, the second installation must target inactive A; if starting from B initially, reverse the order. Install the same OTA again:

```bash
adbe shell twrp install /sdcard/update.zip > "$HAE_PRIVATE/ota-second.log" 2>&1
adbe shell bcbtool get_active
```

Inspect the second log: the successful passes must cover **different targets**. **Do not blindly run `bcbtool set_active` after the OTA's automatic switch.** That can make the next pass target the same slot again. A mismatch between the log and selected slot is a stop-and-investigate checkpoint.

Reboot recovery again and repeat the slot checks. Before EchoLocal, `bcbtool get_active`, `ro.boot.slot_suffix`, `current-boot` and `current-system` must agree. EchoLocal chooses the boot/system target from **`ro.boot.slot_suffix`**, not directly from `bcbtool`.

Verify both system images independently. Inspect `/proc/mounts` and unmount any TWRP system mount, such as `/system_root`, first. This reads each named partition with journal replay disabled and unmounts it on exit:

```bash
for slot in a b; do
  adbe shell "set -e
mkdir -p /tmp/verify-system-$slot
mount -t ext4 -o ro,noload /dev/block/platform/bootdevice/by-name/system_$slot /tmp/verify-system-$slot
trap 'umount /tmp/verify-system-$slot' EXIT
grep -E '^ro.build.(id|version.(incremental|sdk|release))=' /tmp/verify-system-$slot/system/build.prop
" > "$HAE_PRIVATE/system-$slot.properties" || break
done
```

Read **both** files. Require `NS6574`, incremental `0013121734532`, SDK `25`, and Android `7.1.2`. If checking the additional build fields, `ro.build.display.id` is `NS6574`; the `7623N` marker is in `ro.build.fingerprint`, not the display ID. An empty file, failed mount or differing build does not pass. Recovery's own properties are not a substitute for checking the installed systems.

## 6. Install EchoLocal and retain credentials privately

Stay in TWRP. No preliminary stock-OS setup or `boot-root.zip` is required. Prepare protected `wifi.json` with the host guide's interactive prompt, then run:

```bash
install_echo_private
```

The Synology adapter runs [install_private.py](../host/synology/install_private.py). It supplies the exact serial/name, secured Wi-Fi credentials, `--yes` and **`--reboot`**, stores full output privately, and extracts the individual ESPHome PSK. This is an explicit write step; finish all previous checkpoints first. The native adapter uses the same private-log approach.

The installer verifies and writes its embedded boot image when needed, applies root ADB/SELinux patches, waits for Android, requires SDK 25, installs `echod`, disables Amazon services, configures Wi-Fi and reboots. On an already rooted, permissive Android boot, boot-flash is skipped. The embedded image is 9,678,848 bytes, SHA-256 `7f12e1522211d2e1adfc0164a5c2381b8819f44099732bf919b12c23e41e7dd1`, tested with `biscuit_puffin` build `13121734532`. Do not bypass image, partition-size or system-patch checks. [Boot checks](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/bootimg/bootimg.go), [flash stage](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/installer/flash.go), [install flow](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/cli/echoctl/install.go).

### Recovering the observed service-stop timeout

The pilot's first attempt failed at step 14/16: `service is "stopping" 10s after ctl.stop, want stopped`. Android remained reachable; init finished stopping the old process shortly afterward.

```bash
adbe shell getprop init.svc.ledcontroller
adbe shell getprop sys.boot_completed
adbe shell getenforce
```

If the service has reached **`stopped`**, Android reports `1`, and SELinux remains `Permissive`, rerun `install_echo_private`. The pilot needed no wipe or reflash. Existing PSK, name, models and `ledcontroller.orig` are retained. Keep **explicit `--reboot`**: a retry may see existing patches and otherwise decide no reboot is necessary, even though this installation has not completed one. If stopping remains stuck, preserve private logs and investigate. [Stop timeout and idempotence](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/installer/installer.go), [reboot decision](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/cli/echoctl/reboot.go).

### Completion checkpoint

Require all of the following; CLI exit zero alone is insufficient:

```bash
adbe shell getprop sys.boot_completed
adbe shell getprop ro.build.version.sdk
adbe shell getprop echolocal.state
adbe shell getprop init.svc.ledcontroller
adbe shell getenforce
adbe shell wpa_cli -p /data/misc/wifi/sockets -i wlan0 status > "$HAE_PRIVATE/wifi-status.txt"
```

Expected: `1`, SDK `25`, `resident`, service `running`, and `Permissive`. Private Wi-Fi status must contain `wpa_state=COMPLETED`, the intended SSID and a valid IP. The supplicant socket can appear after `resident`, and Wi-Fi association can complete before DHCP supplies `ip_address`; wait briefly and retry until all conditions hold. The Synology wrapper checks this readiness separately. A readiness check that ran before DHCP completed does not by itself require reinstalling EchoLocal. Record the IP privately for pairing.

The key lives at `/data/misc/echolocal/psk`. Both host adapters save `$HAE_PRIVATE/esphome.psk` as mode 0600 and validate that Base64 decoding yields 32 bytes. To recover it separately:

```bash
umask 077
adbe exec-out cat /data/misc/echolocal/psk > "$HAE_PRIVATE/esphome.psk"
chmod 0600 "$HAE_PRIVATE/esphome.psk"
```

Do not print `echoctl key show` or full installer logs into shared transcripts. There is no password-file or suppress-key CLI option; the wrapper passes Wi-Fi credentials as subprocess arguments, briefly visible to sufficiently privileged process inspection. `--ssid` without `--password` means an open network, not a password prompt. [Wi-Fi handling](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/cli/echoctl/wifi.go), [key preservation](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/installer/key.go).

## 7. Hand off to Home Assistant

Follow the [HA integration guide](ha-integration.md). Add the device through **ESPHome**, using its reachable IP, **TCP 6053**, and individual PSK. Routed networks may need manual IP entry because mDNS is not guaranteed. Assign the room and an existing Assist pipeline. ESPHome Device Builder and the optional EchoLocal HACS companion are not prerequisites for basic voice. [Native API port](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/layout/layout.go), [optional companion](https://github.com/ygelfand/echolocal-hacs).

Bundled words are **Okay Nabu**, **Hey Jarvis** and **Hey Mycroft**, all English-trained. A Russian pipeline does not make the wake word Russian. Custom models require separate configuration and testing. Local wake detection does not imply that STT, conversation processing or TTS is local. [Bundled manifests](https://github.com/ygelfand/echolocal/tree/0.0.8/internal/host/assets/models).

Verify audible TTS and a harmless spoken command. Then stop the installation container and USB proxy using the host guide. The NAS may keep powering the Dot; the satellite uses its own Wi-Fi and does not need the USB host software running. Complete cold-boot and soak tests before marking full acceptance.

## Recovery boundaries and other branches

- **Already on amonet 1.x:** the author provides a TWRP ZIP upgrade to amonet 2, followed by Fire OS 6 in both slots. Back up first. Updating the boot chain means Fire OS 5 is no longer an ordinary boot option. Do not apply stock fastbrick to an unlocked device.
- **After amonet 2:** Volume Up at power-on enters TWRP (white ring); Volume Down enters hacked fastboot (rainbow); Mute alone at USB power-on enters preloader USBDL (no LED). Confirm against the [author's instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-2nd-gen-2016-biscuit.4761416/) before using a different release.
- **Stock fastboot unavailable:** the alternate Linux route involves opening the case, shorting the documented testpoint to ground, `sudo ./bootrom-step.sh`, removing the short only when instructed, and `sudo ./fastboot-step.sh`. This is a separate repair procedure, not the successful no-disassembly pilot. [Testpoint image 1](https://xdaforums.com/attachments/short1-jpg.6273803/), [image 2](https://xdaforums.com/attachments/short2-jpg.6273804/). The serial-pinned proxy deliberately excludes unidentified boot-ROM devices; this branch needs separate USB-access preparation.
- **Rollback is limited:** `ledcontroller.orig` preserves one executable; `make uninstall-service` does not restore every Amazon service or undo unlocking. EchoLocal OTA rollback restores the preceding `echod`, not the original Fire OS or boot chain. Do not write LK, preloader or TEE/TZ from unrelated instructions. [Service backup](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/installer/installer.go), [Makefile](https://github.com/ygelfand/echolocal/blob/0.0.8/Makefile).

The resale post that prompted this project described setup Wi-Fi, a pairing webpage and unattended batches. Those features were not established as the pinned upstream provisioning path. This guide uses the verified **USB CLI → Wi-Fi → individual PSK → HA** process for one identified device at a time. Upstream reports about Wi-Fi, audio and wake behavior justify per-device acceptance; they do not prove every device is affected. [Wi-Fi issue 92](https://github.com/ygelfand/echolocal/issues/92), [wake issue 71](https://github.com/ygelfand/echolocal/issues/71), [audio issue 84](https://github.com/ygelfand/echolocal/issues/84), [stop issue 85](https://github.com/ygelfand/echolocal/issues/85).
