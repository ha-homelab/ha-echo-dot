# Strict training artifact transport

The optional `ECHO_DOT_STRICT_TLS=1` profile applies to the owned training-data
downloader shared by synthesis, background and LibriSpeech preparation. Use
CPython3.11+ with OpenSSL3 and install `requirements-strict-tls.txt`.

```sh
python3 -m pip install -r requirements-strict-tls.txt
ECHO_DOT_STRICT_TLS=1 python3 training/data/generate.py --help
```

Keep the environment setting on the documented download commands. Every URL
and redirect must remain HTTPS. Ordinary trust/hostname verification is retained,
and every verified-chain certificate, including the root, is checked before
HTTP bytes: RSA2048, EC224 or DSA2048/224 minimum; Ed25519/448 are supported.
Unknown keys or inaccessible verified chains fail closed. Stronger platform
policy is preserved. Original pinned size/SHA256, range-resume and immutable
final-file checks remain required. Optional published MD5 comparisons are
redundant metadata checks and never replace SHA256.

Linux and Apple silicon use cryptography. Intel macOS runtime metadata uses
Security.framework and the runtime requirements marker excludes cryptography.
Synthetic fixtures separately use `requirements-tls-test.txt` on Linux/Apple
silicon; they do not establish Intel hardware qualification. The native helper
only reads key metadata and does not replace OpenSSL trust verification.

This profile does not claim all training dependencies, downloaded models or
third-party release/conversion tools are secure. Those remain separately
reviewed boundaries. It does not grant new dataset, audio or model rights.

Validation on 2026-10-16 exercised real TLS1.2/1.3 handshakes through both the
context and actual download adapter: exact RSA2048 chains pass; RSA2047 root,
intermediate and leaf chains fail before HTTP bytes. Trust and hostname checks
remain active. Bounded one-byte requests succeeded for all18 pinned voice,
background and LibriSpeech artifacts in `training/data/recipe.py`, including
redirected hosts. These probes demonstrate transport interoperability; they
do not validate complete remote payloads or claim training accuracy. The
ordinary downloader still requires the pinned size and SHA256 for a full file.
