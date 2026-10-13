# Offline input fuzzing

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
