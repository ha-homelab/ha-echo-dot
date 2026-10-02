# Prepare a public repository

The documentation describes a real pilot but uses generic asset names, placeholders, and public upstream sources. The original operational workspace also holds private records; publishing that entire directory is not the release procedure.

## Public content

[public-files.txt](../public-files.txt) is the explicit source of truth for the public export. It includes the English guides, synthetic inventory template, host helpers, training/evaluation source, pinned recipes/dependency lists, and small generated-fixture tests. It excludes local device inventories, host snapshots, credentials, tokens, keys, installer logs, downloaded firmware, third-party source trees, device backups, recordings, voice weights, trained models, feature arrays, compiled tools and private evaluation reports.

The old site-specific HA pairing helper has been preserved in ignored private storage. It depended on a particular Kubernetes deployment and credential location. The public HA guide instead uses the supported UI configuration flow.

## Create and inspect a clean copy

Run from the source project's root:

```bash
python3 scripts/prepare_public_release.py --check-only
python3 scripts/prepare_public_release.py /path/to/new/ha-echo-dot-public
```

The destination must be new and outside the source workspace. The exporter rejects manifest traversal, private paths, local-record filenames, symlinks, missing files, oversized files, and non-UTF-8 content. It only copies files. It does not initialize Git, select a license, push a repository, or upload anything.

The allowlist limits which files are copied; it is not a general secret scanner. Inspect the exported content, especially after future documentation changes. Confirm that examples contain no real Wi-Fi password, Noise PSK, token, full serial, MAC, personal HA hostname, account name, or identifying screenshot. Hashes of publicly downloaded release artifacts are intentional.

Review code and Markdown links in the exported directory. Keep placeholder names consistent. Check that any newly added file is both intended for public use and explicitly listed in the manifest; otherwise it will not appear in the export.

## Release checklist

- The main runbook and detailed device commands agree on the tested versions and stage order.
- The distinction between one successful basic voice test and untested recovery, cold boot, soak, and batch behavior is preserved.
- Wake-word documentation preserves the failed numerical-parity/hard-negative checks and unconfirmed human activation. Preparing reproducible scripts is not a claim that a new full training run or successful human test occurred.
- Training source exports contain no work directory. Voice/dataset terms and per-source attribution remain documented; publishing code does not grant permission to publish trained weights or source audio.
- The Echo Show material remains a research appendix, not an implied tested device route.
- All public files are English, apart from explicitly labelled example utterances if added later.
- Local files and secrets are absent, not merely hidden in a diff or listed in `.gitignore` after being committed.
- Third-party assets are linked to their upstream sources rather than redistributed.
- The original documentation and helper code currently have no selected license. Do not infer a license from public visibility. If the owner later chooses one, add its full text as `LICENSE` and include it in `public-files.txt`.
- Add the chosen repository URL and maintainer contact only when those values are decided. Do not invent author identity or imply upstream endorsement.

The public destination is [ha-homelab/ha-echo-dot](https://github.com/ha-homelab/ha-echo-dot). Repository creation, visibility, default branch, security settings and main-branch protection are managed by [terraform-github-ha-homelab](https://github.com/4alvit/terraform-github-ha-homelab) in its canonical HCP Terraform workspace. Review the staged file list against `public-files.txt` before every publication. The exporter itself never creates a repository or uploads files.

## Preserve local operations separately

The source workspace retains an ignored `private/operations.md`, per-device local inventory, protected keys, and historical documentation. Keep those available for maintaining the real installation. Historical originals may retain their original language and household-specific details; they are not part of the current English public documentation.

Never use `git add -f` to bypass the private-file exclusions. `.gitignore` is a second line of protection, not a substitute for the public manifest and clean export.
