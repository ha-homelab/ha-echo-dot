# Third-party projects and artifacts

This project is an independent documentation and tooling effort. It is not an official Amazon, EchoLocal, Synology, or Home Assistant product.

The working conversion depends on software maintained elsewhere:

- [EchoLocal](https://github.com/ygelfand/echolocal), including `echoctl`, `echod`, and bundled wake-word models. The demonstrated release is 0.0.8.
- [amonet-biscuit](https://github.com/R0rt1z2/amonet/tree/mt8163-biscuit) and the author's [XDA instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-dot-2nd-gen-2016-biscuit.4761416/), providing the device-specific unlock/recovery route.
- Amazon's device-specific Fire OS OTA, downloaded from its distribution service as described in the conversion guide.
- [Home Assistant](https://www.home-assistant.io/), its [ESPHome integration](https://www.home-assistant.io/integrations/esphome/), and the user's selected speech services.
- Debian and the packages installed by the host Dockerfile, including Android platform tools and Python.

The optional training workflow also depends on pinned external software and data:

- [kahrendt/microWakeWord](https://github.com/kahrendt/microWakeWord/tree/a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0) provides the actual MixedNet builder and streaming export utilities; setup fetches its source into the private work directory. TensorFlow, Keras, NumPy and the remaining Python package versions are recorded under `training/`.
- The exact EchoLocal Go interpreter/frontend, FlatBuffers, TensorFlow comparison tools and optional reference assets are documented in [validation dependency notices](training/validation/THIRD_PARTY.md). Upstream modules are fetched at build time, not vendored into the public export.
- Russian Piper voice assets, precomputed background features and LibriSpeech sources have separate pins and terms in [data provenance](training/data/README.md) and [the source recipe](training/data/recipe.py). Irina's dataset terms are listed as unknown, Ruslan includes a non-commercial/share-alike condition, and the precomputed dataset includes non-commercial terms. A code dependency's license does not resolve generated-audio or derived-model redistribution rights.

Research appendices link additional projects. A link or comparison does not mean their code or binaries are included here, or that those alternatives were tested on the pilot.

Only documentation, helper/training source, configuration, dependency pins and source-based tests are included in the public manifest. Downloaded release binaries, firmware, recovery images, third-party source trees, model files, training audio/features, container images, and device dumps are excluded. Their licenses and redistribution conditions remain those of their respective authors; this guide does not grant permission to redistribute them.

Keep upstream notices when building or distributing anything that includes their material. A published host/container image would need its own review of included components and redistribution obligations; this project currently documents a local build only.

The project owner's grant for original documentation and helper code is the [MIT license](LICENSE). It does not change the separate upstream terms or grant rights to models, recordings, datasets, firmware or other excluded artifacts.

## Vendored release tooling

The shared release, versioning and workflow-contract scripts are vendored from
[victron-venus/venus-os-ci-toolkit](https://github.com/victron-venus/venus-os-ci-toolkit).
Their MIT notice is preserved in [third_party/venus-os-ci-toolkit-LICENSE](third_party/venus-os-ci-toolkit-LICENSE).
That preserved license covers toolkit material; the root MIT license separately covers original project code.

## Verified-chain TLS helpers

The exact certificate-key policy and native macOS metadata helper are adapted
from [google-home-voice-stats](https://github.com/victron-venus/google-home-voice-stats/blob/4cbd3296bd08c515198136cb9480e3a6ba734768/igw_google_voice/tls_policy.py),
Copyright (c) 2026 victron-venus, under the MIT license. The original MIT
permission and disclaimer are retained in the root [LICENSE](LICENSE); keep
this attribution when distributing the helpers.
