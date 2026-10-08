# Changelog

## Unreleased

- Update the CI lock resolver to uv 0.12.18, which fixes the Windows wheel
  extraction path traversal in GHSA-2cv4-cqwr-gwf7. The training dependency
  lock and supported runtime versions remain unchanged.

- Run the existing synthetic Python host regressions and Go race tests in CI.
  Model training, TensorFlow-specific dependency checks, acoustic acceptance and
  physical-device conversion remain separate validation steps.
- Document contributions, private vulnerability reporting, trust boundaries and
  partial OpenSSF evidence. Export these files through the public manifest.
- No firmware, model, credential, device setting or license grant is changed.
