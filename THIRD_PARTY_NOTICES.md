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

A license for this project's original documentation and helpers has not been selected. Public visibility is not a grant of an open-source license; do not infer licensing terms from an upstream dependency. A future licensing decision must be recorded explicitly.
