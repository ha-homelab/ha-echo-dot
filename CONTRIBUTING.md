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
and the canonical operational guides. Translated entry-point READMEs are welcome; follow the
[translation policy](docs/i18n.md) and update all affected languages together.

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

CI installs TLS fixture tools and the linter from
[the complete host-tools lock](.github/requirements-host-tools.txt), including
transitive dependencies and artifact hashes. The existing `requirements-tls-test.txt`
and `requirements-lint.txt` remain the editable inputs. After changing an input,
regenerate the lock with the same uv version as CI (currently 0.13.4):

```sh
uv pip compile requirements-tls-test.txt requirements-lint.txt .github/requirements-wheels-only.in --python-version=3.11 --universal --generate-hashes --output-file=.github/requirements-host-tools.txt
```

The host workflow checks regeneration with the locked versions before installing
with `--require-hashes --only-binary=:all:`. This tools environment is separate from
the Python 3.11 model-training environment.

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

## Reproducible Python dependencies

The `.in` files declare direct dependencies. The corresponding `.txt` files pin
all resolved dependencies and approved archive SHA-256 hashes across supported
platforms. Install with `--require-hashes`; do not remove this check to work around
a missing archive. Review dependency updates and regenerate the locks with:

```sh
uv pip compile requirements-host-tests.in --generate-hashes --universal --python-version=3.11 --output-file=requirements-host-tests.txt
```

Run the documented tests in a fresh virtual environment after updating a lock.
The host-test environment uses Python 3.11 and `python -m pip install --require-hashes --only-binary=:all: -r requirements-host-tests.txt`.

### Dependency graph ownership

Renovate owns root Python inputs and `training/` through separate rules in
`renovate.json`. Routine root updates require Dependency Dashboard approval;
security fixes bypass that approval gate. Training updates retain their existing
compatibility bounds and schedule. The native pip-compile manager updates each
compiled lock together with its editable inputs.

Keep GitHub's dependency graph and vulnerability alerts enabled. When changing
scanner directories, inspect the successful managed graph payloads and their
`detector.name`/`job.correlator`: an old root snapshot can retain stale training
versions. Verify both the exported SBOM and open dependency alerts after the
updated snapshot arrives. Do not dismiss an alert solely because a newer lock
was merged. Follow the [dependency-update activation procedure](docs/ci-dependency-updates.md)
before declaring the old Dependabot PR producer disabled.

Contributions to original project code and documentation are made under the [MIT license](LICENSE). Preserve upstream copyright, license and NOTICE files for third-party material.


All major functionality changes must include automated regression coverage and
relevant negative cases, with test instructions documented in the PR. Resolve
substantive compiler, linter and security-analysis findings before merge. Do not
replace actual device acceptance with synthetic test success.

See [governance](GOVERNANCE.md), [conduct](CODE_OF_CONDUCT.md),
[security reporting](SECURITY.md) and the [roadmap](ROADMAP.md).
