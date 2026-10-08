# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ha-homelab/ha-echo-dot/security/advisories/new).
If the form is unavailable, contact a maintainer through the repository's GitHub
profile to arrange a private channel before sharing sensitive details. Public
issues are for non-sensitive defects and feature requests.

Include the affected commit/release, prerequisites, a minimal synthetic
reproduction, expected and actual results, and impact. Do not include live
credentials, personal data or access to devices you do not own.

## Response and supported versions

Maintainers aim to acknowledge a private report within 14 days, investigate its
scope, and agree on remediation and disclosure with the reporter. If no reply
arrives within 14 days, follow up privately. Confirmed security defects are
prioritized by impact; critical defects take precedence over feature work.

Security fixes target the current default branch and latest published release,
where one exists. Older snapshots are not maintained security branches. Release
notes must identify security fixes, affected versions and upgrade actions without
disclosing credentials. This policy is a commitment for handling reports, not
a claim that no vulnerabilities exist or that past reports met a response SLA.

## Project boundary

This project provides Echo Dot conversion helpers and wake-word training, recording and evaluation tools.

Device backups, voice recordings, model training data, Wi-Fi keys and Home Assistant credentials are private. The explicit public-file manifest limits exports; keep its traversal/symlink rejection and never add private data to it. Flashing and USB helpers operate on physical devices and require attended use of the ordered runbook. A wake word is not authentication for sensitive Home Assistant actions.

See [security design and validation boundaries](docs/security-design.md).
