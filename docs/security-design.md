# Security design and verification

## Scope and trust boundaries

The project provides Echo Dot conversion helpers and wake-word training, recording and evaluation tools.

Device backups, voice recordings, model training data, Wi-Fi keys and Home Assistant credentials are private. The explicit public-file manifest limits exports; keep its traversal/symlink rejection and never add private data to it. Flashing and USB helpers operate on physical devices and require attended use of the ordered runbook. A wake word is not authentication for sensitive Home Assistant actions.

## Source and operating documentation

- [scripts/prepare_public_release.py](../scripts/prepare_public_release.py)
- [public-files.txt](../public-files.txt)
- [docs/runbook.md](../docs/runbook.md)
- [training/README.md](../training/README.md)
- [training/recorder/README.md](../training/recorder/README.md)

## Regression evidence

- [scripts/test_prepare_public_release.py](../scripts/test_prepare_public_release.py)
- [training/test_delivery.py](../training/test_delivery.py)
- [training/test_warm_start.py](../training/test_warm_start.py)
- [training/validation/test_evaluate.py](../training/validation/test_evaluate.py)

Run the documented commands in [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[CI workflow](../.github/workflows/tests.yml). Preserve negative tests for rejected inputs,
unavailable dependencies, authorization failures and cancellation. A passing
test run describes its fixtures and environment; it does not certify every
upstream service, hardware model or production deployment.

## Remaining security assessment

An explicit license grant for the project-owned source is absent. Resolve ownership and publish the selected license before claiming FLOSS criteria. Full inference/runtime, memory-safety and acoustic qualification remain separate from fast host CI.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.
