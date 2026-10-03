# Portable training data stages

These helpers reproduce the original **«Привет, Мышка»** profile (`pm-v1`, the unchanged default) and the separate **«Привет, котик»** profile (`pk-v1`). They prepare data only: they do not train a detector, change Home Assistant, upload a model, or establish acoustic acceptance. Each vocabulary, seed, source revision, download size, hash, and synthesis package version is reviewable in `recipe.py`.

Run from the repository root using the Python environment prepared for training. Every command requires `--work-dir`; downloaded voices, archives, extraction files, manifests, partial arrays, checkpoints, and generated WAVs remain beneath that directory. Use a fresh private work directory outside the public source export. No datasets, voice weights, or generated audio are included in this source tree. Execution targets macOS/Linux; stage locks use `fcntl`. All four entry points support `--help` before optional numerical/audio packages are installed.

The examples assume an activated training environment:

```sh
WORK=/absolute/path/to/private-training-run

python training/data/generate.py --work-dir "$WORK" --stage download
python training/data/generate.py --work-dir "$WORK" --stage smoke
python training/data/verify.py --work-dir "$WORK" --stage smoke
# Listen to WORK/data-generation/preview-smoke.wav and inspect the manifest.
python training/data/generate.py --work-dir "$WORK" --stage full
python training/data/verify.py --work-dir "$WORK" --stage full

python training/data/background.py download --work-dir "$WORK"
python training/data/background.py features --work-dir "$WORK"

python training/data/librispeech.py download --work-dir "$WORK"
python training/data/librispeech.py index --work-dir "$WORK"
python training/data/librispeech.py features --work-dir "$WORK"
```

`background.py all` combines its two phases. `librispeech.py all` downloads, extracts, indexes, and creates features. LibriSpeech's `index` verifies/extracts already-downloaded archives without starting a download. Feature extraction expects the parent workflow's Go executable at `WORK/bin/gofeatures`; `--binary PATH` selects another explicitly built executable. The executable hash is recorded. Its stdin contract is raw signed PCM16LE at 16 kHz, and stdout is row-major 40-bin float32LE features.

## Synthesis and audition

`generate.py` preserves recipe **pm-v1**, seed **20261001**, the original source IDs, vocabulary order, parameter draws, and inference order. It uses the pinned Russian Dmitri, Denis, Irina, and Ruslan Piper voices. Four processes each cache one voice; each ONNX session uses two intra-operation threads, one inter-operation thread, sequential execution, and disabled thread spinning. The synthesis environment is checked against the recorded versions: Piper 1.3.0, ONNX Runtime 1.30.0, NumPy 1.26.4, and SciPy 1.17.1.

The original parameter ranges are retained: length scale 0.82–1.16, noise scale 0.50–0.80, noise width 0.60–0.95, and normalized output amplitude 0.72–0.92. Full native utterances are resampled from 22,050 Hz to 16 kHz mono PCM16. Speech is not cropped or silence-padded. These are original synthetic recordings with recorded synthesis/amplitude settings; room/noise augmentation and feature windows belong to later stages.

`smoke` creates 128 sources, 16 positives and 16 negatives per voice. Its four-voice audition WAV contains complete examples and one-second separators, is stored outside `wav/`, and is excluded from training manifests. Listen for pronunciation, stresses, pauses, and missing words; phoneme strings and waveform integrity cannot substitute for listening. `full` creates 6,500 sources **including** those smoke sources: 4,000 positives and 2,500 negatives. All positives contain the complete phrase; negatives include similar greetings, partial words, ordinary commands, and conversation.

The manifest path is `WORK/data-generation/manifest-full.jsonl`. Each row has a `path` relative to `WORK/data-generation`, `source_id`, `split`, integer `label` (1 positive / 0 negative), `voice`, `text`, `duration`, WAV hash, synthesis settings, and RNG provenance. Original-source splits are fixed:

- Train: 3,200 positive and 2,000 negative sources.
- Validation: 400 positive and 250 negative sources.
- Test: 400 positive and 250 negative sources.

Every later window/augmentation must retain its source's partition. The splits share synthetic voices and vocabulary; they are not an unseen-real-speaker evaluation. `_SUCCESS.json` identifies the completed full manifest. `verify.py` is read-only and prints JSON: it checks the fixed source recipe, partitions, every WAV hash and header, duration, unique source/audio IDs, and nonzero audio. It does not silently repair files or approve a model.

## Separate Kotik profile

Use [privet-kotik.json](../configs/privet-kotik.json) for the model configuration and pass `--profile pk-v1` to synthesis and verification. The model ID is `privet_kotik_v1`; the positive phrase is **«Привет, котик»**, pronounced *pri-VET, KO-tik*. The second word has first-syllable stress. The profile uses ordinary Russian spelling, several punctuation/case variants, and records Piper's actual phonemes in every manifest row. Check those phonemes and audition the four-voice smoke preview; a recorded pronunciation target is not evidence of human-approved sound quality.

```sh
KOTIK_WORK=/absolute/path/to/private-kotik-run
python training/data/generate.py --work-dir "$KOTIK_WORK" --profile pk-v1 --stage download
python training/data/generate.py --work-dir "$KOTIK_WORK" --profile pk-v1 --stage smoke
python training/data/verify.py --work-dir "$KOTIK_WORK" --profile pk-v1 --stage smoke
# Review KOTIK_WORK/data-generation/preview-smoke.wav and its segment metadata.
python training/data/generate.py --work-dir "$KOTIK_WORK" --profile pk-v1 --stage full
python training/data/verify.py --work-dir "$KOTIK_WORK" --profile pk-v1 --stage full
```

For an existing verified voice cache copied beneath the new work directory, add `--offline` to `generate.py`; every pinned file is checked and a missing or changed file fails without downloading. The four voices and package pins are shared between profiles, but the generated recordings are separate. Source IDs start with `pk-v1-`, and seed **2026100204** controls the source split, per-source synthesis parameters and per-voice inference sequence. Counts remain 4,000 positive / 2,500 negative sources with the same 80/10/10 source allocation: train 3,200/2,000, validation 400/250, test 400/250. Omitting `--profile` always selects the original `pm-v1`; a different existing dataset profile is rejected.

Kotik hard negatives include the previous **«Привет, мышка»** phrase, near neighbours (*кот*, *котики*, *котёнок*, *Костя*, *кофе*), either wake word alone, greetings, pet conversation and ordinary household/music commands. The old Myshka phrase must never be relabelled as a Kotik positive. Reusing source voices or existing background/LibriSpeech **negative train/validation** arrays is possible with a receipt recording exact paths, SHA-256 values, shapes, roles and splits. Do not import old TTS positives or old held-out tests into the new positive set. New human recordings require their own session-based train/validation/test separation; synthetic integrity does not establish human wake accuracy.

## Precomputed background features

`background.py download` retrieves `speech.zip`, `no_speech.zip`, `dinner_party.zip`, and `dinner_party_eval.zip` from `kahrendt/microwakeword` revision **`0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1`**. The compressed download is about **5.71 GB**, plus extraction and feature-array space. Downloads and extracted-file inventories are verified; no global Hugging Face cache is used. [Pinned dataset card](https://huggingface.co/datasets/kahrendt/microwakeword/blob/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/README.md).

The feature phase preserves the original seed **20261001**, sorted corpus order, random choices, default **250 × 40** shape, and float16 storage. It takes at most 6,000 items from each speech/no-speech training mmap for training, 1,500 items per dinner-party mmap for validation, and 2,000 items per dinner-party-evaluation mmap for test. The last group includes both of that archive's ambient validation/testing partitions; they are both held out as test here. Test items can contribute several spaced windows, so item caps are not window counts. UINT16 values are divided by **25.6** and clipped to `[0,26]`; float arrays retain their source scale before clipping.

Outputs are `WORK/features/background_train.npy`, `background_val.npy`, `background_test.npy`, plus `background_provenance.jsonl`, the recipe, completion metadata, and per-array receipts. Default settings reproduce the initial 48,500 selected windows. `--frames` and `--seed` are explicit experiment changes and require a new work directory once incompatible outputs exist.

These are upstream TensorFlow microfrontend features. The source card documents a 20 ms hop, while the deployed Go experiment uses a 10 ms hop and a numerically different frontend. Scaling does not eliminate that difference. The helper preserves the historical auxiliary-negative recipe; it does not claim the archives have become exact Go features or that window-level metrics establish real-world false-activation rates.

## Real speech with disjoint speakers

`librispeech.py` downloads the **dev-clean** and **test-clean** archives from the recorded OpenSLR mirror, checking pinned SHA-256, byte sizes, and published MD5 values. The two downloads total about 685 MB. It retains the LibriSpeech attribution and CC BY 4.0 reference in `WORK/librispeech/sources.json`. [Original source and terms](https://www.openslr.org/12).

Seed **2026100203** assigns whole dev-clean speakers 80/20 to training/validation; all test-clean speakers remain held out. Speaker intersections are rejected. Source IDs are LibriSpeech utterance IDs. Within each utterance, a deterministic offset places non-overlapping 40,320-sample windows for the default 250-frame context. Even their 30 ms analysis windows remain disjoint. Selection caps are 12,000/1,500/3,000 training/validation/test windows. The original archives yield **5,099/1,260/3,000** selected windows.

Outputs include `WORK/librispeech/windows.jsonl`, `split_manifest.json`, `test_clean_raw.jsonl`, and `test_clean_continuous_at_least_1h.jsonl`. Raw audio paths in these manifests are relative to `WORK/librispeech`. The last filename is retained for compatibility: it is a deterministic **playlist of complete held-out utterances** totaling at least one hour, not a recording of uninterrupted household audio. Final room testing is still separate.

Features are written to `WORK/features/librispeech_{train,val,test}.npy`. Each source window uses a fresh instance of the pinned EchoLocal Go frontend, with a 30 ms window and 10 ms hop. Its quantized features are converted using `(q + 128) * float32(26/255)` and stored as float16; no `/25.6` conversion is applied. The default executable must come from the parent workflow's pinned Go build. `--workers` accepts 1–6; the default is four. A different `--frames`, `--seed`, or executable hash creates a different recorded recipe.

## Resume and immutable outputs

Rerun the same command with the same work directory and dependencies after an interruption. HTTP downloads resume known `.part` files with Range requests; if a server ignores Range, the helper reports that it is restarting that partial. Completed downloads must match the pins. Extraction rejects traversal, links, conflicting existing files, and mismatched receipts. Archive extraction can repeat decompression to verify members after interruption.

Interrupted synthesis replays each voice's earlier inference sequence, verifies existing WAV hashes, and then continues, preserving the ONNX session RNG order. A completed stage is verified and returned without generating it again. Exact byte reproduction is checked in the same environment; it is not promised across runtime versions or hardware platforms.

Background/LibriSpeech arrays use memory-mapped partial NPY files and checkpoint a completed-row prefix every 128 rows. Resume verifies the recipe and rewrites only uncommitted partial rows. Final files have SHA-256 receipts and are never silently replaced. Stage locks prevent two processes from writing the same dataset concurrently. A conflicting recipe, unclaimed old partial, missing receipt for an existing final array, or checksum failure stops the command for inspection. The helpers do not adopt an unrelated legacy output directory automatically; use a new work directory for another experiment.

## Licenses and publication

Source pins do not grant redistribution permission. The voice cards at revision **`c10ece1aade47bb51c153c893d14e5bf8e5b7117`** list Dmitri/Denis training datasets as CC0, Irina as **Unknown**, and Ruslan as **CC BY-NC-SA 4.0**; individual card URLs and hashes are in `recipe.py` and generated provenance. The background dataset card declares **CC BY-NC 4.0** and names constituents including FMA, FSD50K, WHAM, VOiCES, CHiME6, and DiPCo. FMA audio retains artist-selected licenses; a trainer's software license does not resolve those source terms. LibriSpeech attribution and license references are retained separately.

Keep generated audio, downloaded corpora, features, checkpoints, recordings, and models outside the public code export until their intended release and source permissions are assessed. These helpers do not label a derived model as redistributable. The fixed Russian phrase is an example configuration; a new phrase, voice set, source corpus, or public release requires a reviewed new recipe and work directory.

## Lightweight verification of the helpers

```sh
python -m unittest discover -s training/data -p test_data.py -v
```

Fixtures cover immutable outputs, local HTTP resume, archive replay/rejection, interrupted-array recovery, deterministic synthesis partitions, and source/speaker-disjoint LibriSpeech windows. They download no external data and synthesize no speech. With NumPy absent, numerical fixtures are explicitly skipped. During the portability refactor, read-only checks verified all 6,500 existing WAVs and reproduced every existing background selection and LibriSpeech window/speaker partition. That confirms recipe preservation, not acoustic acceptance of the trained detector.
