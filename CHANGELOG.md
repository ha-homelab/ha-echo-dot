# Changelog

## [0.1.4] - 2026-10-20

### Changed

- Update Markdown to 3.11.1, wrapt to 2.5.1 and filelock to 4.2.0 in the locked macOS ARM64 training environment. Keep the Python 3.11 reference platform and the existing TensorFlow, NumPy and model compatibility constraints.
- Refresh CodeQL analysis to 4.39.0 in CI.
- Include the shared CI/fuzzing toolkit update and configurable runner routing introduced since 0.1.3.

### Upgrade

Unpack the verified public host-tools archive into a new directory and recreate the documented locked environment. Preserve operator configuration, local models and audio separately, and retain the previous immutable release for rollback. Firmware conversion, training and device deployment remain explicit operations.

### Validation

The complete 61-package reference lock resolves for Python 3.11 on macOS 14 ARM64. Synthetic host regressions, public-export checks and Go race tests qualify the source package. Native TensorFlow training, model parity, hardware and acoustic acceptance remain separate.

### Security

Verify the published archive checksum and use the documented locked environment setup. Artifact-download TLS and hostname verification remain required. The beta contains only the public source allowlist, with no firmware, model weights, datasets, recordings or credentials.

## [0.1.3] - 2026-10-18

### Changed

- Replace the obsolete Scorecard CI container with the reviewed, checksum-pinned scanner. Keep the upstream SARIF reporting policy, GitHub Security upload and retained report artifacts.
- Update the truststore dependency from 0.10.4 to 0.10.5 in the locked macOS ARM64 training environment. Existing artifact-download TLS verification remains unchanged.
- Synchronize the public host-tools version for this dependency maintenance release.

### Upgrade

Unpack the verified host-tools archive into a new directory and use the documented locked environment setup. Preserve operator configuration, local models and audio separately, and retain the previous immutable release for rollback. Firmware conversion, model training and device deployment remain explicit operations.

### Security

The replaced CI image contained 25 high-severity dependency findings in the recorded scan. The scanner replacement changes CI tooling, not the distributed application runtime. OpenSSF REST publication remains disabled as before.

Native trust-store integration and certificate/hostname verification remain required for artifact downloads. Release checks use synthetic host inputs and exclude private audio, credentials, trained models and device firmware. Hardware and acoustic acceptance remain separate from publication.

## [0.1.2] - 2026-10-17

### Changed

- Use Go 1.27.2 for host validation and release fuzzing, fixing the upstream fuzz-coordinator deadline race while retaining the Go 1.26 language baseline.

- License original host tools and documentation under MIT while preserving third-party notices.
- Verify the strict TLS profile used for training-artifact downloads and exercise native wake-word helpers in CI.
- Document maintenance, vulnerability reporting, release fuzzing and the limits of project security evidence.

### Upgrade

Use the existing host-tools installation procedure and preserve operator configuration, local models and audio separately. Retain the previous immutable release for rollback. Firmware conversion, training and device deployment remain explicit operations.

### Security

Artifact downloads use verified transport checks. Release checks use synthetic host inputs and do not distribute private audio, credentials, trained models or device firmware. Hardware and acoustic acceptance remain separate from publication.

## [0.1.1] - Development line

### Changed

- Qualify this release with a bounded RC fuzz campaign, offline target execution, and deterministic seed replay checks.
- Bind release evidence to the exact source and toolkit revision, validate seed corpora, and retain engine execution counts and diagnostic artifacts.
- Document the fuzzing scope, resource limits, and the distinction between synthetic checks and target acceptance.

### Documentation

- Add Russian, German, Spanish and French README entry points with a shared topic
  index, translation policy and accessible SVG architecture diagram.
- Distinguish the EchoLocal, EchoMuse and Android Show routes and label recorded
  validation as historical evidence rather than current device state.
- Include the new documentation in the public source distribution.

### Upgrade

Use the existing installation or update procedure. This host-tools release updates
validation, release tooling and documentation; existing user configuration and data
formats are preserved.
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
