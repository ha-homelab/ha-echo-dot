# Documentation map — EchoLocal on Echo Dot 2

[English overview](../README.md) · [Русский](../README.ru.md) · [Deutsch](../README.de.md) · [Español](../README.es.md) · [Français](../README.fr.md)

This repository preserves the **EchoLocal / Fire OS** conversion and training path for **Echo Dot 2 / RS03QR / BISCUIT**. For a Dot already running **EchoMuse / emOS**, use the [EchoMuse repository](https://github.com/ha-homelab/ha-echomuse). A shared enclosure does not make the two software stacks, access methods or recovery procedures interchangeable.

![Conversion and runtime responsibilities](assets/architecture.svg)

## First conversion

1. [Identify hardware](hardware-compatibility.md) and [find existing devices](known-devices.md).
2. Read the complete [ordered runbook](runbook.md) and prepare the [USB host](usb-host.md).
3. Follow the pinned [conversion procedure](../research/conversion.md), including the verified backup checkpoint.
4. Configure [Home Assistant, ESPHome and Assist](../research/ha-integration.md).
5. Complete [acceptance before repeated conversion](acceptance-and-batch.md). A successful basic reply is not a recovery or endurance test.

## Operate and diagnose

- [Controls, readable values and limits](device-controls.md): supported entities and options in the documented EchoLocal version.
- [Device access and ADB](device-access.md): access paths, prerequisites and boundaries.
- [Companion integration and dashboard](echolocal-companion.md): optional EchoLocal-specific UI. Do not carry its old entities over to an EchoMuse migration.
- [Music latency](music-latency.md): isolate request processing from playback transport.
- [Operational findings](operations-findings.md): dated evidence, not a live status page.

## Train and evaluate a wake phrase

1. Read [custom wake-word limits](custom-wake-word.md), then the [training pipeline](../training/README.md).
2. Collect private samples with the [local recorder](../training/recorder/README.md); never commit voices, transcripts or model weights.
3. Use [validation and parity checks](../training/validation/README.md) before the [delivery stages](../training/DELIVERY.md).
4. Compare against the [training history](training-history.md), including negative results. Evaluate false activations and natural speech separately; changing the README language does not train a model.

## Research and maintenance

- [Other ecosystem routes](../research/ecosystem.md), [Show 5 research](show5-plan.md) and the separate [Show 5 repository](https://github.com/ha-homelab/ha-echo-show-5).
- [Contributing](../CONTRIBUTING.md), [translation policy](i18n.md), [security reporting](../SECURITY.md) and [security design](security-design.md).
- [Publication allowlist](publication.md), [release strategy](../RELEASING.md), [versioning](VERSIONING.md), [release workflow](release-workflow.md) and [RC fuzzing](fuzzing.md).
- [Third-party notices](../THIRD_PARTY_NOTICES.md) and [OpenSSF evidence](openssf-evidence.md).

The SVG is an architecture illustration, not a measurement. Benchmark and validation numbers belong to the dated experiment that produced them. Device availability, keys and household inventories remain private.
