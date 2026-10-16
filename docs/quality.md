# Quality evidence and limitations

Host CI exercises packaging, public export boundaries, synthetic training/data
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
