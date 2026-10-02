# Identify speakers you already own

An existing Home Assistant Alexa integration may already contain models and device serials. Use those records to narrow the search before powering every speaker. Installing an Alexa integration is not required for conversion; a physical label and USB identification can supply the evidence.

Start with [hardware families and compatibility](hardware-compatibility.md) for the difference between Echo, Echo Dot, Show, and other families, the supported routes, and the risks of using a mismatched image.

## Find candidates in Home Assistant

1. Open **Settings → Devices & services → Devices**, search for Echo/Amazon, or open the devices under the existing Alexa integration.
2. Inspect model and identifiers. Save a private inventory entry for an explicit **Echo Dot (Gen2)** candidate. An entity suffix such as `_2` can distinguish duplicate names; it does not establish generation.
3. Deduplicate records that refer to the same serial. Renames and old integrations can leave several records for one physical speaker.
4. Note availability, then power one candidate. Inspect entity state/history for the transition from unavailable to available.
5. Associate that record with the physical speaker and confirm its label/serial. A saved room name may describe an old location.

The pilot inventory contained five explicitly labelled Gen2 records. Powering one speaker produced one availability transition; its serial later matched BISCUIT over USB. Only that speaker was converted and voice-tested. The other records are candidates, not proof of five working physical units.

## Limits of saved records

Model, name, and serial can remain in HA while a speaker is unplugged. Conversely, `unavailable` can mean a network or account problem rather than no power. An enabled integration entry does not prove the speaker is powered on.

Stored firmware versions may be stale. Choose the installer from current USB/recovery inspection, not cached software-version fields. A lit ring proves power, not a working USB data cable.

Confirm physical model and **BISCUIT** before the [Dot 2 procedure](../research/conversion.md). Full-size Echo devices, later Dots, and Echo Shows require separate compatibility research. [Show 5 is a separate appendix](show5-plan.md).

## Keep identities private

Copy [the template](../inventory/devices.example.json) to `inventory/devices.local.json`. Assign an asset ID such as `echo-001`, then record the real serial, MAC, room, backup location, HA IDs, and test results there. Store passwords and encryption keys in protected files; inventory contains their references only.

After conversion, HA creates an ESPHome device with new entities. The old Alexa entity is no longer the converted satellite's status indicator. Record both identities if useful, and use the new ESPHome device for tests. Before removing old records, check for automations that still refer to them.

The public documentation omits household device names, serials, HA URLs, and device IDs. Those remain in ignored local inventory and private operations notes.
