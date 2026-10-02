# Echo Show 5 second generation: Android source research

**Research-only experimental appendix.** Target: **Echo Show 5, second generation (2021), `cronos`**. This is separate from the Echo Dot 2 / EchoLocal procedure. No Show 5 unlock, flashing, recovery, audio test, or Home Assistant application test was performed by this project.

The original research cutoff was **2026-10-01 in America/Los_Angeles**. The notes below preserve that historical snapshot and its pinned artifacts. Tagged GitHub release metadata was rechecked for this English edition. XDA findings are retained from the original browser-based review; direct web retrieval returned HTTP 403. Links to branch heads and forum posts may change. Re-read the model-specific instructions before any hardware work.

## Candidate path and identification

Start with the [hardware compatibility and identification guide](../docs/hardware-compatibility.md). A shared Echo name does not establish a shared boot image, partition layout, or audio implementation.

The upstream sources described this candidate path:

**Stock Show 5 Gen 2 → model-specific amonet-cronos unlock → TWRP → per-device backup → unofficial LineageOS 18.1 → Android Home Assistant client.**

The researched pins were **amonet-cronos 2.0.1** and **LineageOS 18.1 `cronos` v0.4 / Android 11**. Published support for a model does not prove that a particular device can be converted successfully. Verify its physical generation, label, product identifier, and actual Fire OS state. A firmware number shown by an existing Home Assistant integration is not necessarily a human-readable Fire OS release number.

The inspected amonet README identified product **AEOCN**. The forum opening post used label **C76N8S**, while other project documentation has used a similar label. Do not resolve such a discrepancy by guessing from one character. Establish the generation and product before selecting files. Images for `biscuit`, `checkers`, and `crown` target different devices.

## Unlock evidence

The [model-specific unlock thread](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-show-5-2nd-gen-2021-cronos.4772596/) was recorded as edited on **2026-09-11**, linking [amonet-cronos-v2.0.1.zip](https://xdaforums.com/attachments/amonet-cronos-v2-0-1-zip.6373838/). Earlier articles about 1.x or the older `mt8163-cronos` branch should not be treated as instructions for this package.

In a [2026-09-11 maintainer reply](https://xdaforums.com/posts/90734589/) concerning Fire OS **6.5.6.4 and 6.5.7.4**, the new exploit was described as no longer requiring a particular Fire OS version. That is a dated upstream claim about the releases discussed, not a guarantee against future firmware changes.

The recorded opening post specified **Windows or Linux**, a normal **micro-USB data cable**, and the Show's **separate AC power adapter**. The main method did not call for disassembly, shorting contacts, or a special cable. It described entering factory FASTBOOT with the three physical buttons, then using the package's `fastbrick` entry point and following its prompts. The source warned against interrupting the destructive stage. Consult that source for its exact timing and button sequence; this appendix does not replace it.

The source pin for the newer common branch was [commit `d6179b8`](https://github.com/R0rt1z2/amonet/tree/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d), dated **2026-08-15 at 23:35:34 UTC**, on the then-inspected [`mt8163-echo-show` branch](https://github.com/R0rt1z2/amonet/tree/mt8163-echo-show).

**macOS initial unlocking was not established.** The inspected [fastbrick.sh](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/fastbrick.sh) uses a bundled fastboot, associative Bash arrays, and `timeout`. Substituting a Homebrew binary is not a validated port. Later file transfer through ordinary ADB is a different step: [Google Platform-Tools](https://developer.android.com/tools/releases/platform-tools) provides a macOS package, and the ROM instructions describe ADB/MTP transfer after recovery is available.

## Pinned Android artifact

The [LineageOS thread](https://xdaforums.com/t/rom-unofficial-11-cronos-lineageos-18-1-for-the-amazon-echo-show-5-2021.4772598/) linked the following release at the research cutoff:

- [Tag `lineage-18.1-cronos-v0.4`](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4).
- Published **2026-09-05 at 00:53:11 UTC**.
- Asset: `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`.
- Published size: **484,847,340 bytes**.
- Published SHA-256: `4c355998061a454792128d4b730932b47ed05a3d2a6d2628599218f44cc84678`.

The hash and size are upstream metadata. This project did not download and hash the ROM archive or install it. Before use, verify the actual downloaded file against the selected release. The repository contains releases for different Amazon devices, so its generic “latest” link is not a sufficient model selector.

The recorded [Build 4 announcement](https://xdaforums.com/posts/90726610/) reported camera photo/video support, a fix for audio stopping after several days, microphone improvements, lower minimum brightness, Bluetooth LE, and Ethernet adapter support. Its displayed build-date text conflicted with the asset filename and GitHub publication metadata. The tag, filename, and checksum identify the artifact more reliably than that conflicting date text.

The [device-tree A2DP sink change](https://github.com/amazon-oss/android_device_amazon_cronos/commit/81ed9d303a51), dated **2026-04-17**, is additional Bluetooth implementation evidence. It does not establish every headset profile, codec, or concurrent microphone/playback combination on a physical device.

## Hardware claims and remaining limits

At the cutoff, the ROM opening post still listed Wi-Fi fast-roaming problems, potentially quiet microphones, **SELinux Permissive**, disabled deep sleep, a synthetic 100% battery value, and **Mute also acting as Power**. This is an unofficial Android 11 port, not an officially supported general-purpose tablet. Display and touch operation described in installation instructions also need testing on the actual hardware.

A [2026-09-06 maintainer explanation](https://xdaforums.com/posts/90728899/) described a camera startup interaction: booting with the red Mute state enabled can leave the camera disabled until rebooting with Mute off. The reply recommended double-tap-to-wake for waking the screen. Treat this as a specific diagnostic clue, not a reason to conclude from one failed camera test that the entire port lacks camera support.

The historical claim that the camera never works is inconsistent with the selected v0.4 changelog. Conversely, a changelog entry is not this project's camera test. The separate [camera patch project](https://github.com/jxlarrea/lineageos-echo-show-camera) is useful implementation history, but applying its patches on top of v0.4 was not validated here and is not required by this proposed first trial.

Android application compatibility, microphone capture, wake-word quality, camera behavior, and Bluetooth audio require independent acceptance checks. Google apps are not a prerequisite for the underlying Android port; choose applications only after the base hardware has been evaluated.

## Backup, installation, and recovery boundaries

The following records the shape of the upstream process. It is **not an executed or proven recovery runbook**.

1. Record the physical model and current software state privately. Select the model-specific unlock package and ROM, verify their available provenance/checksums, and provide stable AC power plus a working USB data link.
2. The recorded procedure obtains TWRP through the unlock first. A full factory-state backup before any unlock write was not established. Once recovery is available, preserve a per-device backup **before wiping the OS**, copy it off the device, and check the files. The older [backup discussion](https://xdaforums.com/posts/90418102/) mentions boot/system/data and empty-backup problems; verify the actual partition list in the selected recovery instead of copying an old script blindly.
3. The ROM instructions included data formatting and wiping Data/System/Cache, transferring the correct `cronos` ZIP, installing through TWRP, and another data format before reboot. These are destructive stages that remove prior settings. Follow the exact instructions for the chosen release rather than combining steps from different generations.
4. The recorded unlock 2.x instructions described returning through TWRP using the appropriate stock update image, with [FTVDB](https://ftvdb.com/) as a firmware index, or restoring a suitable per-device backup. An index is not a substitute for verifying the image's device identity and provenance. No full return-to-Alexa procedure was tested by this project.
5. The source describes distinct recovery, modified fastboot, and USBDL entry modes. Their existence is not an unconditional unbrick guarantee. It specifically cautions against manually altering critical early-boot partitions such as Preloader, LK, and TEE.

Backups can contain Wi-Fi configuration, account data, keys, and device-specific calibration. Store them privately outside this repository. A backup made after unlocking does not undo the risk or writes of the unlock itself, and one device's dump is not a generic image for another.

## Historical activity and next evidence

The inspected [device-tree commit `0abbd82`](https://github.com/amazon-oss/android_device_amazon_cronos/commit/0abbd824bb1ca71d44b578ad99a546784962b19b), dated **2026-09-27 at 13:23:40 UTC**, added stock thermal configurations. It postdates the v0.4 artifact. Do not attribute a later source-tree change to an older published ZIP without build evidence.

This research establishes that a model-specific unofficial Android option was published at the cutoff. It does not establish successful conversion of any device in this project. The next evidence would be physical identification, a reviewed version-specific procedure, verified backup and recovery checkpoints, a working Android boot, and separate Home Assistant application tests. See [client options](show5-ha-options.md) and the [experimental plan](../docs/show5-plan.md).
