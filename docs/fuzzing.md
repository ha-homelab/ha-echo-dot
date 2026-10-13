# Offline input fuzzing

This repository has local native Go fuzz targets for the offline wake-word
validation tools. The prepared `.github/fuzz.json` manifest is **not connected to
an RC release workflow yet**: this project currently has no versioned GitHub
release lifecycle. There is no claim that hosted RC campaigns are running, and no
fuzzing status badge is displayed until that lifecycle is adopted.

The intended shared policy is public repositories and explicit release candidates
only; no mutation campaigns on pushes, PRs, betas or scheduled nightlies. Ordinary
Go tests continue to replay the small deterministic seed corpus. This is native
Go fuzzing, not membership in Google's hosted OSS-Fuzz service.

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

When a reviewed release adapter is available, the prepared manifest requests two
60-second targets with two workers and isolated networking after dependency setup.
The eventual badge must describe the actual policy, while source-bound Actions
reports provide the pass/fail evidence for each RC.
