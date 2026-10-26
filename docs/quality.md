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

## Linux amd64 host image qualification

The required `check-3 / Linux amd64 host image build` job runs on a GitHub-hosted
Ubuntu runner through the single quality gate. It builds the unchanged
`host/synology/Dockerfile` for `linux/amd64` from a temporary context containing
only that Dockerfile and the official EchoLocal 0.0.8 binary, verified against
the same SHA-256 required by the Dockerfile. No credentials, firmware images or
device files enter the build context.

The job inspects the resulting image configuration and retains a
`host-image-build-receipt` artifact with the source commit, Dockerfile and binary
hashes, base image, target architecture and resulting image ID. It does not start
the completed image, execute EchoLocal, access USB, perform a conversion, train a
model, record audio, deploy anything or publish the image.

A green result establishes host-image buildability for those inputs. APT package
versions remain unpinned, so it does not establish bit-for-bit reproducibility,
upstream binary rebuilds, runtime USB behavior or compatibility with a physical
Echo. The receipt records those limits.
