# Quality evidence and limitations

Host CI runs Ruff F diagnostics across the complete Git-tracked Python inventory,
with isolated configuration and inline suppressions ignored. It also exercises packaging, public export boundaries, synthetic training/data
pipeline helpers, recording interfaces and evaluation tools. The reference
training lock is checked separately from the lighter host environment. Neither
host-only tests nor lock resolution demonstrate all training-runtime dependencies
are safe. Assess conversion, training, recording, evaluation and release paths as
a whole; keep private data and device acceptance outside synthetic-test claims.

The complete dependency, transport and native-code analysis remains work in
progress. No whole-project coverage percentage or clean full-runtime advisory
inventory is claimed. See [security design](security-design.md) and the
[security policy](../SECURITY.md).

The primary maintainer personally confirms knowledge of secure design and common
Python/network application vulnerabilities, and no bug, feature or vulnerability
reports outside GitHub in the preceding twelve months as of 2026-10-16. These are
human attestations, not automated findings. Public issue history and current
diagnostics must also be reviewed for each assessment update.

## Source build system

The two produced native helpers are built by
`python3 training/pipeline.py --work-dir /path/to/new/work build`. The command
uses the standard Go build system, locked Go modules and `-trimpath`, and saves
source and binary SHA-256 values in `bin/build.json`. The required Go CI job
runs this public command, executes the validator and feeds synthetic silence
through the compiled frontend. Python and browser helpers are interpreted;
source package/export commands have separate host tests.

The reference training environment and synthetic TensorFlow-to-Go export were
also exercised as documented in [the training guide](../training/README.md).
That evidence concerns executable model format, not acoustic accuracy. A
working project build does not imply independently rebuilding unchanged external
ROMs, EchoLocal, TensorFlow, Python or the operating system. The conversion host
image has its own [Dockerfile](../host/synology/Dockerfile). Dependency security
and physical-device acceptance remain separate checks.
