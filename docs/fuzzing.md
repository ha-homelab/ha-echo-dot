# Offline input fuzzing

See the [illustrated RC fuzzing process and verified rollout results](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/rc-fuzzing-results.md)
for the shared release flow, evidence requirements and a dated cross-project
snapshot. The project-specific scope and reproduction guidance below still apply.

> **Local packaging:** `python3 scripts/release.py package` is unsupported in this repository because no shell packaging adapter is installed. Use the [project commands below](#local-release-packaging); the generic example in `release-workflow.md` does not apply here.

This public repository runs native Go fuzz targets for the offline wake-word
validation tools as part of an explicit release candidate. The manifest
[`.github/fuzz.json`](../.github/fuzz.json) uses the shared
`venus-os-ci-toolkit` runner. It accepts only public default-branch RC requests,
fetches dependencies during setup, then runs two isolated 60-second campaigns
with two workers and no network access. A failed campaign blocks publication.

There are no mutation campaigns on pushes, PRs, betas or scheduled nightlies.
Ordinary Go tests continue to replay the small deterministic seed corpus. Stable
promotion uses the accepted RC's evidence without repeating mutation or rebuilding.
The README badge describes this policy; the exact RC Actions run and report show
actual results. This is native Go fuzzing, not membership in Google's hosted
OSS-Fuzz service.

## Target scope

- `FuzzModelStructure` constructs model metadata from bounded synthetic JSON and
  calls the production `checkModel` validator. The input represents metadata
  after TFLite parsing; the target does not fuzz the third-party FlatBuffer parser
  or prove neural-network correctness. Accepted metadata cannot reference absent
  tensors. Invalid interface indices previously caused an indexing panic; the
  validator now rejects them, as well as out-of-range operator outputs, before
  indexing. The negative examples remain regression seeds.
- `FuzzWAVInput` sends arbitrary bytes to the same PCM16/mono/16 kHz RIFF parser
  used by file input. It also synthesizes WAV containers from fuzzed PCM bytes and
  checks exact signed sample preservation. The small `parseWAV` helper is shared
  with `readWAV`, so there is no parallel test-only parser.

Both inputs are capped at 64 KiB. Tests use synthetic memory buffers, do not open
microphones, contact an Echo/Home Assistant, train a model, flash firmware or
change a deployed wake word. Passing does not establish acoustic acceptance,
TensorFlow parity, an acceptable false-positive rate or physical-device safety.

## Run locally

Use the Go version in `training/validation/go.mod`:

```sh
go -C training/validation mod download
go -C training/validation test -race ./...
go -C training/validation test . -run='^$' -fuzz='^FuzzModelStructure$' -fuzztime=60s -parallel=2
go -C training/validation test . -run='^$' -fuzz='^FuzzWAVInput$' -fuzztime=60s -parallel=2
```

Go prints a minimized failing input path under `testdata/fuzz/<FuzzName>/` and a
replay command. Keep the synthetic input with its fix and run the regular suite
plus a fresh campaign. Do not commit private voices, trained weights, device
identifiers or personal recordings. Security-sensitive findings follow
[SECURITY.md](../SECURITY.md). See [Go's fuzzing guide](https://go.dev/doc/security/fuzz/)
for corpus format, minimization and troubleshooting.

Keep the target manifest and this guide aligned when changing the campaign
scope. Source-only release contents and the separate hardware/model acceptance
boundaries are documented in [publication](publication.md).

## Local release packaging

Use Python 3.12+ from the repository root:

```sh
python3 scripts/test_package_host_tools.py
python3 scripts/prepare_public_release.py --check-only
python3 scripts/package_host_tools.py
```

This writes the reviewed host-tools source archive and version metadata to a new `release-dist/` directory. It packages the public allowlist without building firmware or model weights. Use a clean disposable checkout and a new output directory.

To reproduce an already allocated beta or RC, first check out the exact source
commit from its published `release-manifest.json`, restore that manifest's
`version_plan` object as `.release-plan.json`, and apply its version overlay:

```sh
python3 scripts/version_plan.py sync --root . --plan .release-plan.json
```

Then run the project commands above. Keep the source, plan and channel together;
do not invent a release sequence or edit version fields by hand. Local packaging
does not create a qualified release: the hosted pipeline still verifies the full
build inventory, provenance and, for an RC, its own isolated fuzz report.

## Release workflow retries

Fresh release inputs are selected by the exact GitHub workflow run ID and run
attempt.

Before publication starts, use **Re-run all jobs** only if the allocator and
release policy permit reuse of that run's reservation. Recreate every required
input in the same attempt; failed-only or individual retries can leave inputs
missing, and older artifacts must not fill those gaps.

For a fresh candidate or final build, once publication has started
(`begin_publication`), or its external publication result is partial or uncertain,
inspect the existing release, tags and assets before retrying. A consumed build
number requires a new workflow run and reservation authorized by the release
policy; an existing immutable tag may also require a new base version. Never
reset the release ledger, overwrite assets or retag to force a retry. Historical
byte promotion of an accepted RC keeps its reserved number and follows the
existing promotion policy.

Artifacts from older attempts may remain available for diagnostics; they are not
inputs to the new attempt and do not need to be deleted. Filtering artifact names
alone does not prove package completeness or receipt identity. Complete package
inventory and receipt identity checks remain separate release requirements.

See the shared [package identity and retry contract](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/VERSIONING.md#package-identity-across-reruns).

### Complete package producer inventory

`versioning.required_build_receipts` declares the exact package and signature
receipt filenames required by this project's final publisher. Each authenticated
receipt must match the repository, source commit, workflow run and attempt. A
missing producer or an unexpected receipt stops fresh publication, even when the
remaining packages are valid. RC fuzz evidence is checked separately; pre-signing
checks do not require a signature receipt that has not been created yet.

Before publication begins, rerun all required producers only when the allocator
and release policy permit reusing that reservation. After publication begins or
its outcome is uncertain, inspect existing tags, releases and assets before a
policy-authorized new run; never reset the ledger or mix earlier-attempt packages.
Historical RC promotion keeps its accepted source policy. Keep this explicit
inventory aligned with producer changes; it does not replace package-format,
signature or device acceptance checks.
