"""Warm-start integrity and selection tests without TensorFlow or training data."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_CONFIG, read_config, sha256
from train import checkpoint_if_better, compile_for_training, initial_weights_provenance


class FakeModel:
    def __init__(self, events, mismatch=False, mutate=None):
        self.events = events
        self.mismatch = mismatch
        self.mutate = mutate
        self.weights = "initial"

    def load_weights(self, path, *, skip_mismatch):
        self.events.append(("load", str(path), skip_mismatch))
        if self.mismatch:
            raise ValueError("fixture: checkpoint tensor shape mismatch")
        if self.mutate:
            self.mutate()

    def compile(self, **kwargs):
        self.events.append(("compile", kwargs))

    def save_weights(self, path):
        Path(path).write_text(self.weights)
        self.events.append(("checkpoint", self.weights))


class WarmStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = read_config(DEFAULT_CONFIG)
        self.weights = self.root / "best.weights.h5"
        self.weights.write_bytes(b"fixture checkpoint; no actual HDF5 loading in mocked tests")
        self.digest = sha256(self.weights)
        self.recipe = self.root / "recipe.json"
        self.recipe.write_text(json.dumps({"config": self.cfg}))

    def provenance(self):
        return initial_weights_provenance(self.weights, self.digest, self.cfg)

    def fake_tf(self, events):
        def adam(rate):
            optimizer = object()
            events.append(("fresh_adam", rate, optimizer))
            return optimizer
        return SimpleNamespace(keras=SimpleNamespace(optimizers=SimpleNamespace(Adam=adam)))

    def test_no_option_keeps_cold_start_and_paired_options_are_required(self):
        self.assertIsNone(initial_weights_provenance(None, None, self.cfg))
        for path, digest in ((self.weights, None), (None, self.digest), (self.weights, "short")):
            with self.assertRaises(ValueError):
                initial_weights_provenance(path, digest, self.cfg)
        events = []
        compile_for_training(FakeModel(events), self.fake_tf(events), self.cfg["training"])
        self.assertEqual([e[0] for e in events], ["fresh_adam", "compile"])

    def test_checkpoint_and_recipe_are_verified_before_loading(self):
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            initial_weights_provenance(self.weights, "0" * 64, self.cfg)
        bad = copy.deepcopy(self.cfg)
        bad["architecture"]["residual_connection"] = "True,True,True,True"
        self.recipe.write_text(json.dumps({"config": bad}))
        with self.assertRaisesRegex(ValueError, "architecture"):
            self.provenance()
        bad = copy.deepcopy(self.cfg)
        bad["feature_step_ms"] = 20
        self.recipe.write_text(json.dumps({"config": bad}))
        with self.assertRaisesRegex(ValueError, "cadence"):
            self.provenance()

    def test_legacy_pilot_recipe_is_supported_without_inventing_cadence(self):
        self.recipe.write_text(json.dumps({"frames": self.cfg["frames"], "flags": self.cfg["architecture"]}))
        info = initial_weights_provenance(self.weights, self.digest.upper(), self.cfg)
        self.assertEqual(info["sha256"], self.digest)
        self.assertEqual(info["recipe_sha256"], sha256(self.recipe))
        self.assertEqual(info["recipe_format"], "legacy_frames_flags")
        self.assertFalse(info["feature_step_ms_recorded"])

    def test_strict_load_precedes_fresh_optimizer(self):
        events = []
        compile_for_training(FakeModel(events), self.fake_tf(events), self.cfg["training"], self.provenance())
        self.assertEqual([e[0] for e in events], ["load", "fresh_adam", "compile"])
        self.assertIs(events[0][2], False)
        self.assertIs(events[2][1]["optimizer"], events[1][2])
        self.assertEqual(events[1][1], self.cfg["training"]["learning_rate"])

    def test_tensor_mismatch_does_not_construct_optimizer(self):
        events = []
        with self.assertRaisesRegex(ValueError, "shape mismatch"):
            compile_for_training(FakeModel(events, mismatch=True), self.fake_tf(events),
                                 self.cfg["training"], self.provenance())
        self.assertEqual([e[0] for e in events], ["load"])

    def test_source_changes_before_or_during_load_are_rejected(self):
        info = self.provenance()
        self.weights.write_bytes(b"changed checkpoint")
        events = []
        with self.assertRaisesRegex(ValueError, "changed"):
            compile_for_training(FakeModel(events), self.fake_tf(events), self.cfg["training"], info)
        self.assertEqual(events, [])
        info = initial_weights_provenance(self.weights, sha256(self.weights), self.cfg)
        mutate = lambda: self.recipe.write_text("{}")
        with self.assertRaisesRegex(ValueError, "recipe changed"):
            compile_for_training(FakeModel(events, mutate=mutate), self.fake_tf(events), self.cfg["training"], info)
        self.assertEqual([e[0] for e in events], ["load"])

    def test_step_zero_checkpoint_survives_worse_or_equal_finetuning(self):
        events = []
        model = FakeModel(events)
        best, improved = checkpoint_if_better(model, self.root, {"weighted_loss": .2}, float("inf"))
        self.assertTrue(improved)
        checkpoint = self.root / "best.weights.h5"
        self.assertEqual(checkpoint.read_text(), "initial")
        model.weights = "regressed update"
        for loss in (.5, .2):
            best, improved = checkpoint_if_better(model, self.root, {"weighted_loss": loss}, best)
            self.assertFalse(improved)
            self.assertEqual(checkpoint.read_text(), "initial")
            self.assertEqual(best, .2)
        with self.assertRaisesRegex(ValueError, "not finite"):
            checkpoint_if_better(model, self.root, {"weighted_loss": float("nan")}, best)
        self.assertEqual(checkpoint.read_text(), "initial")
        model.weights = "improved update"
        best, improved = checkpoint_if_better(model, self.root, {"weighted_loss": .1}, best)
        self.assertTrue(improved)
        self.assertEqual(best, .1)
        self.assertEqual(checkpoint.read_text(), "improved update")

    def test_failed_save_preserves_prior_checkpoint_and_removes_partial_file(self):
        for existing in (True, False):
            with self.subTest(existing_checkpoint=existing):
                if not existing:
                    self.weights.unlink()
                expected = self.weights.read_bytes() if existing else None
                files_before = set(self.root.iterdir())

                def partial_save(path):
                    self.assertTrue(str(path).endswith(".weights.h5"))
                    Path(path).write_bytes(b"partial HDF5 checkpoint")
                    raise OSError("fixture: disk full during checkpoint save")

                with self.assertRaisesRegex(OSError, "disk full"):
                    checkpoint_if_better(SimpleNamespace(save_weights=partial_save),
                                         self.root, {"weighted_loss": .1}, .2)
                if existing:
                    self.assertEqual(self.weights.read_bytes(), expected)
                else:
                    self.assertFalse(self.weights.exists())
                self.assertEqual(set(self.root.iterdir()), files_before)

    def test_failed_replace_keeps_prior_checkpoint_and_cleans_completed_temp_file(self):
        expected = self.weights.read_bytes()
        files_before = set(self.root.iterdir())
        with patch.object(Path, "replace", side_effect=OSError("fixture: replace denied")):
            with self.assertRaisesRegex(OSError, "replace denied"):
                checkpoint_if_better(FakeModel([]), self.root, {"weighted_loss": .1}, .2)
        self.assertEqual(self.weights.read_bytes(), expected)
        self.assertEqual(set(self.root.iterdir()), files_before)

    def test_existing_candidate_is_immutable_without_importing_ml_packages(self):
        (self.root / "models/existing").mkdir(parents=True)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("train.py")),
                                 "--work-dir", str(self.root), "--candidate", "existing"],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Candidate exists", result.stderr)
        self.assertEqual(list((self.root / "models/existing").iterdir()), [])

    def test_help_remains_available_without_tensorflow(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("train.py")), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--initial-weights-sha256", result.stdout)


if __name__ == "__main__":
    unittest.main()
