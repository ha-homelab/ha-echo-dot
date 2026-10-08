# Contributing

Use [GitHub issues](https://github.com/ha-homelab/ha-echo-dot/issues) for non-sensitive bug reports, questions and
feature proposals. Include the exact version/commit, environment, expected and
actual behavior, and a minimal sanitized reproduction. Check existing issues
first and keep follow-up evidence in the original thread. For vulnerabilities,
use the [private security process](SECURITY.md).

Submit a focused pull request against `main`. Describe the user-visible problem,
the resulting behavior, compatibility implications and checks performed. Preserve
existing authorship and third-party license/provenance records. Discuss changes
to protocols, storage, device safety or dependency/runtime requirements before
making an incompatible change. English is the common language for code review
and project documentation.

## Development and validation

```sh
python3 scripts/test_prepare_public_release.py
python3 training/test_pipeline.py
python3 training/test_delivery.py
python3 training/test_warm_start.py
python3 training/validation/test_evaluate.py
python3 -m unittest discover -s training/data -v
python3 -m unittest discover -s training/recorder -v
```

Fast tests use synthetic data; NumPy 1.26.4 exercises numerical fixtures and ffmpeg is required for recorder tests. Full model training, TensorFlow dependency tests and acoustic acceptance use the separately documented Python 3.11 environment. These are not implied by passing host tests.

The [CI workflow](.github/workflows/tests.yml) is the authoritative list of required jobs.
Use isolated test data and temporary outputs. Never run a device write, unlock,
deployment or publication command merely to validate a documentation change.

## Test and review policy

Changes to behavior must add or update automated tests that fail for the old
defect and cover the new boundary; regression fixes should include the relevant
failure case. If automation is infeasible, explain why in the PR and document
the reproducible manual procedure and limits. Update user/API documentation and
release notes for user-visible changes. Keep compiler, lint, static-analysis and
test assertions enabled, resolve new warnings, and document any remaining
warning with its reason and scope. Do not suppress a real security finding to
obtain a passing check. Wait for required checks and independent review before
merging; do not use an administrator bypass.
