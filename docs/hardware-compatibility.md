# Identify and select existing Echo hardware

Start with the Echo devices you already own. For this repository's proven conversion route, select an **Echo Dot, second generation (2016), model RS03QR, codename `biscuit`, USB fastboot product `BISCUIT`**. EchoLocal **0.0.8** explicitly targets that device. One such unit completed conversion and a spoken Home Assistant exchange in this project; that result does not validate every unit, firmware state, or Echo family. [EchoLocal 0.0.8](https://github.com/ygelfand/echolocal/blob/0.0.8/README.md), [amonet's BISCUIT device mapping](https://github.com/R0rt1z2/amonet/blob/0aac01a5daa60b0a4b958dd127c46feb9daaaceb/fastbrick.sh#L33).

The model selection below is a snapshot checked on **October 1, 2026**, using the release pinned by the pilot. “Supported” means documented by the relevant community project; Amazon does not provide this conversion procedure. This is a practical inventory guide, not a catalog of every regional SKU, color, bundle, or later release.

## First separate the families

**Alexa** is the assistant/service name. **Echo** is a product brand containing several hardware families. “Works with Alexa,” an Alexa entry in Home Assistant, or a similar exterior does not establish EchoLocal compatibility.

Use Amazon's illustrated [Which Echo Device Do I Have?](https://digprjsurvey.amazon.com/csad/help/node/GHRYQ6GHE4A5TUD2) page to sort the collection:

- **Echo Dot:** compact speakers. Generations 1–5, clock variants, Kids editions, and Dot Max need their own identification.
- **Echo:** the larger speaker family, including first, second, third, and fourth generations. **Echo Plus** is another named family.
- **Echo Pop:** a compact speaker family with a different design from the Dot.
- **Echo Studio:** larger speakers focused on room audio; record the release as well as the family name.
- **Echo Show:** displays in several size families and generations.
- **Echo Spot:** compact screen devices; the original 2017 model and 2024 release are distinct.
- **Echo Auto:** car-oriented devices that work with the Alexa phone app and vehicle audio.
- **Echo Flex:** a small speaker that plugs directly into a wall outlet.

The same Amazon guide also lists products such as Input, Hub, Link, Sub, wearables, and Tap. Keep those in separate inventory groups. None becomes a Dot 2 because it uses Alexa.

## Echo Dot generations: which one to put on the conversion bench

Appearance is a sorting aid. Confirm the label before acting. Amazon's [Dot identification guide](https://digprjsurvey.amazon.com/csad/help/node/T9vK1qIZkTSG7LX8JT) distinguishes these common units:

- **Dot 1:** a relatively thick, glossy black puck. Set aside from this conversion batch; the pinned EchoLocal route does not document Dot 1 support.
- **Dot 2:** a lower puck with a hard plastic exterior, sold in black and white. This is the candidate to inspect for **RS03QR**, then **BISCUIT** over USB.
- **Dot 3:** a fabric-covered puck. It is a different generation even though it is also round and flat. Do not use the Dot 2 images.
- **Dot 4:** a small sphere. Outside the pinned Dot 2 route.
- **Dot 5:** also a small sphere, visually similar to Dot 4. Outside the pinned Dot 2 route; shape alone is not enough to distinguish these two.

Clock displays, Kids styling, or an old purchase date do not replace a generation check. For Dot 1, 3, 4, 5, Max, and any unidentified variant, this repository makes **no compatibility claim** beyond the explicitly documented Dot 2 target. That means there is no validated procedure here, not that future ports or all other research are impossible.

### Why Dot 2 is the selected route

The complete path has matching pieces: a model-specific unlock, recovery, a compatible Fire OS base, and EchoLocal's device implementation. Release 0.0.8 embeds a boot-image definition for `biscuit_puffin` and advertises the hardware as Echo Dot 2. A microphone array and a speaker alone are insufficient: boot images, audio routing, LEDs, storage layout, and hardware access must match the device. [Boot-image definition](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/host/bootimg/bootimg.go#L65), [device identity](https://github.com/ygelfand/echolocal/blob/0.0.8/internal/layout/layout.go#L93).

The project's successful basic test used **amonet 2.0.0, TWRP, Fire OS 6, and EchoLocal 0.0.8**. Follow the [conversion runbook](../research/conversion.md) for its exact versions, backup checkpoints, and separate branch for an already-unlocked device. Cold power-on recovery and a long soak remain acceptance work; do not promote one successful spoken reply into a batch reliability claim.

## Full-size Echo and other speaker families

- **Full-size Echo 1, 3, and 4:** no supported conversion with this repository's EchoLocal 0.0.8 procedure is established. Keep them out of the Dot batch.
- **Full-size Echo 2:** separate experimental work exists for codename **`radar`**. At the check above, [EchoLocal PR #64](https://github.com/ygelfand/echolocal/pull/64) was a **draft**, describing a different boot image, amplifier handling, and incomplete features. It is not included in this project's proven Dot 2 route and was not tested here. Shared processor ancestry does not make a `biscuit` image suitable.
- **Echo Plus, Pop, Studio, Auto, and Flex:** no working conversion for these families is established by the pinned EchoLocal documentation or this pilot. Preserve their full model/release information for separate investigation. Do not run the Dot unlocker as a compatibility test.

If an existing unit falls outside the proven path, leave its firmware unchanged while checking a project that explicitly names its model. Keeping stock Alexa functionality or using a documented audio-input/Bluetooth feature is a separate reuse choice; neither proves that Home Assistant can use the unit's microphones as a local Assist satellite.

## Echo Spot: distinguish 2017 from 2024

**Spot first generation (2017), `rook` / `AEORK`:** a [model-specific amonet branch](https://github.com/R0rt1z2/amonet/tree/mt8163-rook) exists. The separate [TECHO5 Spot project](https://github.com/HuskerMinion/techo5-spot) targets that generation, identifies model `VN94DQ`, and reports a Linux-based HA voice implementation derived from TECHO5/EchoLocal. This is an alternative research lead with its own unlock, OS, installer, and recovery requirements. It is not the pinned EchoLocal 0.0.8 Dot installer, and this project has not tested it.

**Spot 2024:** neither of those model-specific claims establishes support for the redesigned 2024 device. Keep it in the unresolved group for this project; do not apply `rook` or `biscuit` files to it. “Echo Spot” alone is insufficient identification.

## Echo Show: a separate Android experiment

Echo Show support must be evaluated independently. The pinned [amonet Echo Show branch](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/README.md) explicitly lists these unlock targets:

- **Show 5, first generation (2019):** codename `checkers`, product `AEOCH`.
- **Show 5, second generation (2021):** codename `cronos`, product `AEOCN`.
- **Show 8, first generation (2019):** codename `crown`, product `AEOCW`.

Those are unlock claims for those exact devices, not an EchoLocal compatibility list. Do not extend them to Show 5 third generation, later Show 8 generations, the original full-size Show, or another Show size.

This repository researched **Show 5 Gen 2 / `cronos`** with model-specific amonet and an unofficial [LineageOS 18.1 release](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4). The intended application path would be an Android Home Assistant client after validating the port. No Show was unlocked or tested by this project. Display, microphone, speaker, wake behavior, app compatibility, and recovery need their own acceptance checks. See the [Show source research](../research/show5-android-sources.md) and [experimental plan](show5-plan.md).

## Naming traps that lead to the wrong image

- **“Dot 2” and “Echo 2” are different devices.** Write the complete family name in inventory records. `biscuit` and `radar` are not interchangeable.
- **The “5” in Show 5 identifies its screen-size family, not generation five.** A Show 5 can itself be first, second, or third generation. Amazon describes the 2021 Show 5 as having a 5.5-inch display. [Amazon's 2021 announcement](https://press.aboutamazon.com/uk/2021/5/amazon-introduces-upgraded-echo-show-8-and-echo-show-5).
- **A Home Assistant entity ending in `_2` is not evidence of second-generation hardware.** HA can add numeric suffixes when generating an available entity ID, and names can be edited. [HA entity-ID generation](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/helpers/entity_registry.py#L1319).
- **A model, a serial, a product identifier, and a firmware version are different fields.** A model describes a hardware type; a serial identifies one unit; `BISCUIT` is the bootloader product response; a software build identifies installed software.
- **A USB connector is not proof of a supported USB workflow.** A cable can supply power without carrying data, and another Echo's connector or power arrangement does not imply the same recovery procedure.
- **An “Echo” device in HA is not proof of conversion.** It may come from a stock Alexa integration. Check its integration, actual hardware record, and the software running on the device.

## Find and identify the units already in the house

1. **Collect the physical devices and their matching power supplies.** Check current rooms, storage boxes, spare electronics, and old packaging. Keep a temporary numbered tag with each unit; use generic tags such as `ECHO-01`, not a guessed generation.
2. **Photograph the underside/back label and the top/ports.** Copy the model code exactly. Do not infer a missing character from a similar-looking model in an online post. Store photos and complete serials privately.
3. **Cross-check the box and purchase record.** The original box can identify the generation and serial. Compare it to the unit; boxes and adapters may have been swapped. Amazon's own fleet setup guidance recommends serial-based physical labeling and notes that some devices do not print the serial on the device itself. [Amazon device-labeling guidance](https://developer.amazon.com/en-GB/docs/alexa/alexa-smart-properties/device-setup.html).
4. **Use the existing Alexa/Amazon account as corroboration.** Inspect the registered device list and any device details available for the unit. In the Alexa app, **Devices → the device → Device Settings → About** shows its software version. Record that before any change. An assigned room name is not a model, and an old account entry may refer to a device no longer present. [Amazon's About instructions](https://digprjsurvey.amazon.com/csad/help/node/GGKZ8CZYMD47WG7U).
5. **Cross-check existing Home Assistant entries.** Use the integration's device page, not a dashboard title or entity suffix. Treat generic or missing model data as unresolved. HA, router, or account records help locate a unit but do not override its physical and USB identity.
6. **Assign an inventory status:** `candidate Dot 2`, `separate research`, or `unresolved`. Keep the reason and source with that status. Only the first group proceeds to the Dot-specific read-only USB check.

Identification does not require a factory reset, deregistration, firmware update, or opening the case. Avoid adding those changes merely to discover which device is on the desk.

### Final USB identity check before a write

For a physically identified Dot 2, follow only the **identity-check stage** of the [conversion runbook](../research/conversion.md#3-unlock-the-selected-stock-dot) on the prepared host. Match the selected serial, read `getvar product`, and require **`BISCUIT`**. Also inspect the unlock status: an already-unlocked device belongs to a different branch of the procedure. The correct label plus an unexpected product response is a reason to investigate, not to force the script.

For the stock unlock stage, isolate one target as directed by the [USB host guide](usb-host.md). The author's `fastbrick` script does not take a device serial argument. Keep the inventory tag attached through each USB re-enumeration and verify the serial again after recovery appears. Do not paste real serials into public issues or this repository.

The pinned BISCUIT branch's general README still contains inherited Fire tablet text. Use its [model-aware script](https://github.com/R0rt1z2/amonet/blob/0aac01a5daa60b0a4b958dd127c46feb9daaaceb/fastbrick.sh) and the author's [Dot 2 instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-2nd-gen-2016-biscuit.4761416/); do not combine a generic repository README with instructions for another device.

## What can happen with the wrong generation

These are possible failure modes, not a prediction that every mismatch will brick a device:

- **A clean rejection:** a tool may refuse an unknown product, mismatched image, or unsupported software base. Treat the refusal as a stop condition; do not bypass it to discover what happens.
- **A booting but unusable system:** different audio or peripheral hardware can leave microphones, speakers, Wi-Fi, LEDs, or other functions unavailable. An Android boot does not establish voice-satellite compatibility.
- **A boot loop or recovery-only state:** an incompatible kernel, system image, or partition target can prevent normal startup. Repair then depends on the recovery and valid images still available for that exact unit.
- **Loss of recovery or a hard brick:** a wrong or interrupted write to critical early-boot storage can remove ordinary recovery access. Hardware-assisted repair may be necessary or unavailable. Recovery instructions for another family are not a guarantee.
- **Loss of device data:** wipes and cross-device restores can remove settings or overwrite unit-specific data. One speaker's backup is not a universal image for the next speaker.

This risk assessment follows from the model-specific boot images and unlock payloads; the project's matched-device pilot did not test deliberate cross-flashing. The script's mismatch check is one safeguard, not proof that arbitrary manual writes are safe. Preserve each device's own verified backup at the stage the runbook permits, and do not claim a post-unlock backup represents the untouched factory state.

## Choose the next device

Select **one confirmed RS03QR/BISCUIT Dot 2** with stable USB power and a working data cable. Finish its [conversion](../research/conversion.md), [HA setup](../research/ha-integration.md), and [acceptance checks](acceptance-and-batch.md) before adding more units. Keep Show experiments, full-size Echo 2 development, and unresolved hardware outside that batch. No purchase is needed to complete this inventory and selection process.
