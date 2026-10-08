"""Optional real-Piper API fixture, without model downloads, training or devices."""
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import generate


@unittest.skipUnless(importlib.util.find_spec("piper"), "install synthesis requirements")
class PiperContractTests(unittest.TestCase):
    def test_real_phonemizer_and_audio_api_match_generator(self):
        # Native libraries may terminate with exit(0); a successful exit alone
        # does not prove that phonemization or the test reached completion.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--fixture"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PIPER_FIXTURE_COMPLETED', result.stdout, result.stderr)

    def _exercise_real_phonemizer_and_audio_api(self):
        import numpy as np
        from piper import PiperVoice
        from piper.config import PiperConfig

        voice, jobs = next(iter(generate.make_jobs().items()))
        job = jobs[0]
        config = {"num_symbols": 128, "num_speakers": 1,
                  "audio": {"sample_rate": 22050}, "espeak": {"voice": "ru"},
                  "phoneme_id_map": {"_": [0], "^": [1], "$": [2]}}
        probe = PiperVoice(session=None, config=PiperConfig.from_dict(config))
        phonemes = probe.phonemize(job["text"])
        self.assertTrue(phonemes)
        for phoneme in sorted({p for sentence in phonemes for p in sentence}):
            config["phoneme_id_map"].setdefault(phoneme, [len(config["phoneme_id_map"])])

        class SyntheticSession:
            def __init__(self):
                self.calls = []

            def run(self, names, inputs):
                self.calls.append(inputs)
                wave = np.sin(np.arange(8000, dtype=np.float32) * .1) * .2
                return [wave.reshape(1, 1, -1)]

        session = SyntheticSession()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            folder = root / "voices" / voice
            folder.mkdir(parents=True)
            (folder / f"ru_RU-{voice}-medium.onnx.json").write_text(json.dumps(config))
            with patch("onnxruntime.InferenceSession", return_value=session):
                result = generate.run_voice(str(root), voice, [job], "smoke")
                # Identical replay exercises the immutable waveform contract.
                generate.run_voice(str(root), voice, [job], "smoke")
            rows = [json.loads(line) for line in (root / result["manifest"]).read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["sample_rate"], 16000)
            self.assertEqual(rows[0]["phonemes"], ["".join(sentence) for sentence in phonemes])
            self.assertGreater(rows[0]["duration_seconds"], .12)
            self.assertGreater(len(session.calls), 0)
            for inputs in session.calls:
                self.assertEqual(inputs["input"].dtype, np.int64)
                self.assertEqual(inputs["input"].shape[0], 1)
                np.testing.assert_allclose(inputs["scales"],
                    [job["noise_scale"], job["length_scale"], job["noise_w_scale"]])


if __name__ == "__main__":
    if sys.argv[1:] == ["--fixture"]:
        suite = unittest.TestSuite([PiperContractTests("_exercise_real_phonemizer_and_audio_api")])
        result = unittest.TextTestRunner().run(suite)
        if result.wasSuccessful() and not result.skipped:
            print("PIPER_FIXTURE_COMPLETED")
        sys.exit(0 if result.wasSuccessful() else 1)
    unittest.main()
