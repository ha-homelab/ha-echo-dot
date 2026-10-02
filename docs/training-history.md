# Russian wake-word experiment: stage record

This is the English record of the pilot behind the [reproducible training commands](../training/README.md). It distinguishes completed work from hypotheses and untested behavior. Dates use UTC where a time is stated. Historical artifacts remain private; the public repository contains scripts and documentation, not a pre-trained model download.

## Baseline and target

The converted Echo Dot 2 ran EchoLocal 0.0.8, paired with Home Assistant Core 2026.9.1 through the ESPHome integration. The owner confirmed **Okay Nabu → Russian command → spoken Russian reply**. The experiment added **Привет, Мышка** to the second wake-word slot, keeping the first slot available. Choosing Russian in Assist or renaming Okay Nabu would not create this detector.

## Runtime feasibility before training

The first stage inspected the actual Go dependency pinned by EchoLocal and tested supported streaming operations, tensor shapes, INT8/UINT8 quantization, state initialization and repeated execution. A random-model smoke export exposed an optional fully connected bias issue; the smoke harness supplies a nonzero bias so the converter retains a tensor required by the Go implementation. Trained exports still undergo their own independent runtime checks.

The implemented builder was `kahrendt/microWakeWord` at `a70bd740d4e79ee8a8bb3db843fe862b88d5d6b0`. The `interkelstar/microwakeword-trainer` wrapper at `8fdbadc3b969a8c1993108c0d655910440dfb762` was inspected as a reference, but its entire pipeline was not used. The final path did not patch the deployed Go interpreter or silently fall back to float/nonstreaming output.

## Environment and compute choice

The reference environment used Python 3.11.16, TensorFlow 2.16.2 and Keras 3.15.1 on Apple Silicon. A bounded benchmark measured approximately **0.00655 seconds/update on CPU** and **0.02165 seconds/update with Metal** for the sampled workload. CPU was selected for this small architecture. These numbers describe that benchmark, not universal training throughput. The complete package set is recorded in the [reference lock](../training/requirements-macos-arm64.lock.txt).

## Synthetic data and source partitions

The recipe downloaded four pinned Russian Piper voices: Dmitri, Denis, Irina and Ruslan. It produced 4,000 complete-phrase positives and 2,500 difficult negatives, split by original recording before augmentation. Training received 3,200 positives and 2,000 negatives; validation and test each received 400 positives and 250 negatives.

Positive durations ranged from 0.708 to 2.183 seconds. This ruled out a fixed 1.5-second crop that would remove part of some utterances. The model uses a 250-frame context at a 10 ms hop. Synthetic voice identity is shared across the partitions, so the split does not measure transfer to a new human speaker.

## Frontend comparison and feature preparation

The C and exact Go frontends did not produce identical features despite matching basic frame geometry. The recipe therefore included the deployed Go frontend in feature preparation and used it for all final streaming scores. Synthetic training used one C and two Go variants per recording; validation/test used Go variants. The resulting TTS arrays contain 16,900 windows.

Precomputed background features supplied 42,000/3,000/3,500 train/validation/test windows. Their source used a C frontend and 20 ms hop; `/25.6` scaling and clipping to 0–26 were recorded as an approximation. A later source-separation pass added real LibriSpeech audio with 32 training, eight validation and 40 test speakers, producing 5,099/1,260/3,000 Go-feature windows. The final continuous test used independently prepared full audio, not shuffled feature windows.

## Bounded candidates and export

Candidate 1 was the earlier synthetic/background baseline. Candidate 2 included LibriSpeech negatives. The saved recipe capped training at 5,000 updates, checked validation every 500, selected the lowest weighted validation loss and allowed early stopping. The exact completed update count belongs to each private run receipt, not a claim that every candidate used the full budget.

The exported experimental artifact is **privet_myshka_v1**, **51,344 bytes**, SHA-256 **20b28cd466a8c65aee5ac827b3e6a6d492b73645a510dffb2aacd81e1ae591eb**. It uses a 10 ms feature hop, stride three, a five-score window and internal streaming state. Graph, quantization, explicit Go inference and public-detector consistency checks passed.

## Numerical parity and validation calibration

Strict TensorFlow Lite/Go parity failed on two Russian traces, with maximum differences of **2 and 16 raw UINT8 score units**, exceeding the one-unit budget. At the selected **0.90** cutoff, both runtimes made the same threshold decision at every compared step. This agreement did not convert the numerical failure into a pass.

Calibration used the deployed Go implementation. At 0.90, validation detected 400/400 synthetic positives, produced zero events on 250 difficult negatives and zero events over 3,872.485 seconds of concatenated clean speech. The cutoff and averaging window were fixed before the final independent test.

## Frozen final test

At the frozen 0.90 cutoff, the model detected **400/400 synthetic positives** and falsely activated on **2/250 difficult negatives**: Ruslan renderings of **«Компьютер не видит мышку»** and **«Привет, мышь»**. The zero-negative criterion therefore failed. A separate **3,601.99-second** concatenated held-out LibriSpeech stream produced zero events.

These long streams preserved frontend/model state through utterance joins. They were not recordings of the household, television or music. The final-test errors were retained, and the reported test threshold was not adjusted to remove them. Perfect synthetic recall does not establish human wake-word reliability.

## HA delivery and first human trial

The matching model/sidecar were staged and downloaded to the Echo through a controlled native-API route, then the target ESPHome entry was reloaded and slot 2 selected in HA. A global HA restart was not used for that historical route. The public scripts now provide verified packaging and standard catalog staging; the site-specific native-API helper remains private.

The first slot retained Okay Nabu, its tested Russian assistant, and threshold **0.85**. The second slot initially used the custom phrase with threshold **0.90**. The owner then reported **“does not understand.”** HA later transcribed the phrase correctly inside an Okay Nabu conversation and answered it as a greeting; this did not demonstrate independent custom activation.

For diagnosis, only the second slot's threshold was temporarily lowered to **0.70**, confirmed at **2026-10-02 04:19:33 UTC**. A subsequent 60-second observation showed no new wake/HA events. There was no new explicit user outcome confirming a fresh custom-phrase attempt after that change. Thus 0.70 is a diagnostic trial, not a newly calibrated or accepted model setting.

Device diagnostics showed the custom model loaded, approximately 50 processed frames per second, and roughly 10 ms processing per 20 ms frame, without a relevant model/runtime error in the inspected tail. Missing detection or near-miss lines are not a zero-score measurement and do not prove a particular utterance was attempted during the observation.

## Personalization acquisition

The owner subsequently reported intermittent activation: a higher-pitched delivery worked more often than an ordinary speaking voice. This is qualitative feedback, not a measured pitch boundary. Deliberately bounded microphone recordings have begun in private storage. Collection exposed a synchronization problem: the participant did not hear the short start chime, and a chat prompt could arrive too late for a complete utterance. The attempted capture turns restore recording retention and the original slot settings afterward. Captured files are not automatically accepted as labelled examples.

A compatible-checkpoint warm-start path now preserves the initial weights as the step-0 validation baseline. Preparing that path and collecting WAVs do not establish that a personalized model has been trained or deployed. Complete-phrase verification, separate acquisition sessions and streaming evaluation remain necessary before replacement.

## New target: Привет, котик

On 2026-10-02 the owner selected **Привет, котик** as the new target. This started a separate private workspace using `synthesis_profile: pk-v1`, seed `2026100204`, and model ID `privet_kotik_v1`. It did not rename or reuse Myshka positives. The four Russian TTS voices generated 4,000 new positives and 2,500 new negatives, including confusable greetings, кот/котики/котята, кофе and the previous Myshka phrase. Source partitions remained 3,200/400/400 positive and 2,000/250/250 negative; feature preparation produced 16,900 windows. Cached background and LibriSpeech **training/validation** arrays were hash-verified and reused. No old TTS or test feature arrays were linked into the new run.

A local cached Whisper model transcribed one training sample per synthetic voice as the complete target without a target-text prompt. Pronunciation metadata placed stress on приВЕТ and КОтик. This was automatic QA; no human audition of those four samples was recorded, so the listening checkpoint remains open.

Cold training stopped after 4,500 updates and retained the step-2,500 checkpoint with weighted validation loss approximately 0.0031955. The streaming export passed the pinned Go structural and repeated-inference checks. The candidate is **51,344 bytes**, SHA-256 **bb971774263e41ab95c0d35e5268cf0e273a7854bdcc32750b45887a722b124a**. It uses the same 10 ms hop, stride three and five-score window as the historical recipe.

All five validation parity traces failed the one-unit raw UINT8 budget. Maximum differences were **17, 17, 7 and 11** for the Denis, Dmitri, Irina and Ruslan positive traces, and **7** for the negative trace. At 0.90, clip decisions agreed on all five; one Dmitri invocation crossed opposite sides of the threshold. An identical seven-unit difference occurred during leading digital silence before speech on every trace. Numerical failure remains recorded; agreeing clip decisions do not make it pass. The cold-start Go score also briefly reached about **0.856** during that zero padding. It stayed below 0.90, but the provisional 0.85 sidecar value should not be mistaken for the evaluated operating point.

Exact-Go validation at **0.90** detected **398/400** synthetic positives, with zero events on 250 difficult negatives and a **3,872.485-second** concatenated LibriSpeech stream. The cutoff was then frozen, explicitly as an evaluation-only protocol because strict parity failed. The independent test detected **398/400** positives and falsely activated on **2/250** negatives: Denis saying **«Привет, кот.»** and Ruslan saying **«Привет, кофе.»**. A separate **3,602.095-second** LibriSpeech stream produced zero events. The test result did not change the threshold.

The new continuous test excluded utterances used by the historical continuous test and used speakers separate from training/validation. Its source came from the cached test-clean corpus; some source utterances had previously been converted into unused test feature windows. This is a new continuous evaluation selection, not a claim that every source file had never been processed. Neither stream measures household background noise. The four synthetic voice identities remain shared across partitions.

The immutable private package is labelled **experimental**, retaining the failed parity and zero-negative gates and the unrun human/room gates. **It has not been staged, downloaded or activated on the Echo.** Connectivity subsequently recovered and participant-controlled capture produced one verified ordinary-voice example. The existing slot selections remained unchanged; the capture controller and its independent watchdog both verified restoration, including recording retention off.

The first accepted source was 3.5 seconds long. The participant confirmed the attempt, and both HA transcription and offline cached Whisper identified the complete target. Local transcription used no target-text prompt; no manual audition was recorded. A complete-phrase crop covers 0.60–2.90 seconds and retains its source checksum and sample bounds. It was imported as one training positive; real validation and test sets remain empty, and feature generation is deferred until collection is complete. The frozen candidate's exact-Go streaming diagnostic reached only **0.33647**, below its **0.90** cutoff, and produced no activation. This is a training example and diagnostic, not an independent acceptance test. No personalized candidate has been trained yet.

Collection also exposed a delivery problem: short chat cues arrived after recording ended. Two attempts explicitly confirmed by the participant to contain no prompted phrase are excluded from positive training. A final chat response followed by a participant-held Action button successfully synchronized one attempt. The next one-minute arming window expired without audio, so the private helper now allows five minutes to start one attempt while keeping actual listening capped at 12 seconds. Failed or expired attempts do not become labelled examples.

## Remaining work and next experiment

Human spoken acceptance, a room-noise soak, and reliable custom activation remain unconfirmed. The current target is **Привет, котик**. The next steps are to collect more deliberately bounded ordinary-voice recordings, keep acquisition sessions separated, import accepted clips with [recordings.py](../training/recordings.py), and evaluate adaptation using real voice examples. Acoustic mismatch is a hypothesis to test, not an established diagnosis. Preserve consumed holdouts and use a fresh final selection for decisions informed by their errors; repeated diagnostic use must be labelled as reused.

Keep the historical model and failed results. Use separate-session validation and a fresh independent final holdout for decisions influenced by the old test. Preserve Okay Nabu as the fallback while evaluating another revision. The Echo may already run from ordinary USB power; further wake-word training and network configuration do not require it to remain connected by USB data to Synology.
