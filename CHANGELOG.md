# Changelog

## [0.1.1] - Development line

### Changed

- Qualify this release with a bounded RC fuzz campaign, offline target execution, and deterministic seed replay checks.
- Bind release evidence to the exact source and toolkit revision, validate seed corpora, and retain engine execution counts and diagnostic artifacts.
- Document the fuzzing scope, resource limits, and the distinction between synthetic checks and target acceptance.

### Upgrade

Use the existing installation or update procedure. This release changes validation
and release tooling; existing user configuration and data formats are preserved.
Keep the previous immutable release for rollback. Test the exact RC package on the
intended target before accepting a stable promotion.

### Security

Fuzz targets and deterministic preflight commands run offline on synthetic
inputs. Setup and dependency installation may use the runner network. The
campaign rejects missing or invalid seed corpora and incomplete execution
evidence. These checks do not establish untested hardware, integrations,
credentials, or deployment behavior.

## [0.1.0] - Host tools preview

- Add local synthetic model-metadata and WAV fuzz tests. Invalid model tensor
  references now return validation errors instead of panicking. Public RCs run
  bounded isolated campaigns through the shared release tooling.
- Start the separate 0.1.0 host-tools/documentation preview line with deterministic
  allowlisted source archives. No firmware, models or private audio is packaged.

- Update the CI lock resolver to uv 0.12.18, which fixes the Windows wheel
  extraction path traversal in GHSA-2cv4-cqwr-gwf7. The training dependency
  lock and supported runtime versions remain unchanged.

- Run the existing synthetic Python host regressions and Go race tests in CI.
  Model training, TensorFlow-specific dependency checks, acoustic acceptance and
  physical-device conversion remain separate validation steps.
- Document contributions, private vulnerability reporting, trust boundaries and
  partial OpenSSF evidence. Export these files through the public manifest.
- No firmware, model, credential, device setting or license grant is changed.

### Upgrade

This first 0.1.0 host-tools preview is source-only. Unpack it into a new directory
and follow the existing host-tool instructions. It does not install firmware,
replace a model, alter an Echo or migrate private training data. Review device
and model compatibility separately before using any tool on hardware.

### Security

Malformed model metadata now returns validation errors instead of panicking.
RC fuzzing exercises only synthetic metadata and WAV inputs in an isolated
runner. The archive contains the public allowlist only; never place credentials,
recordings, trained model weights or device inventories in public reports.
