"""Fast contract checks; no network, installed ML runtime, or device is required."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_CONFIG, candidate_dir, read_config, require_profile_identity, work_dir
from data.recipe import synthesis_profile
from features import load_rows


class WorkflowContracts(unittest.TestCase):
    @staticmethod
    def source_recipe(profile_name):
        profile = synthesis_profile(profile_name)
        return {"version": profile_name, "master_seed": profile["master_seed"],
                "voices": list(profile["voices"]), "positives": list(profile["positives"]),
                "negatives": list(profile["negatives"])}

    def test_profile_guard_allows_old_same_phrase_personalization_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            original = read_config(DEFAULT_CONFIG)
            self.assertNotIn("synthesis_profile", original)
            (work/"recipe.json").write_text(json.dumps(original))
            (work/"data-generation").mkdir()
            # The original synthesis receipt has no wake_word field.
            (work/"data-generation/recipe.json").write_text(json.dumps(self.source_recipe("pm-v1")))
            before = {p: p.read_bytes() for p in work.rglob("*.json")}
            adapted = copy.deepcopy(original)
            adapted["model_id"] = "privet_myshka_personal_v2"
            adapted["wake_word"] = "привет мышка!"
            adapted["training"].update(learning_rate=.0001, max_updates=500)
            self.assertEqual(require_profile_identity(work, adapted)["synthesis_profile"], "pm-v1")
            self.assertEqual(before, {p: p.read_bytes() for p in work.rglob("*.json")})

    def test_display_phrase_cannot_relabel_a_pinned_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            config = read_config(DEFAULT_CONFIG)
            config["wake_word"] = "Привет, котик"
            with self.assertRaisesRegex(ValueError, "Model wake phrase"):
                require_profile_identity(work, config)
            self.assertEqual(list(work.iterdir()), [])

    def test_guard_checks_source_identity_without_a_saved_model_recipe(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            source = work/"data-generation/recipe.json"
            source.parent.mkdir()
            config = read_config(Path(__file__).parent/"configs/privet-kotik.json")
            source.write_text(json.dumps(self.source_recipe("pm-v1")))
            with self.assertRaisesRegex(ValueError, "another synthesis profile"):
                require_profile_identity(work, config)
            saved = self.source_recipe("pk-v1")
            saved["wake_word"] = "Привет, Мышка"
            source.write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "synthesis source wake phrase"):
                require_profile_identity(work, config)
            saved["wake_word"] = config["wake_word"]
            saved["positives"][0] = "Привет, Мышка."
            source.write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "vocabulary"):
                require_profile_identity(work, config)

    def test_guard_checks_saved_model_phrase_not_just_profile_name(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            config = read_config(Path(__file__).parent/"configs/privet-kotik.json")
            saved = {**config, "wake_word": "Привет, Мышка"}
            (work/"recipe.json").write_text(json.dumps(saved))
            with self.assertRaisesRegex(ValueError, "work model wake phrase"):
                require_profile_identity(work, config)

    def test_direct_consumers_reject_profile_mismatch_before_ml_or_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/"recipe.json").write_text(DEFAULT_CONFIG.read_text())
            config = Path(__file__).parent/"configs/privet-kotik.json"
            commands = (("features.py",), ("train.py", "--candidate", "new"),
                        ("model.py", "smoke"))
            for script, *args in commands:
                with self.subTest(script=script):
                    # -S excludes installed numerical/ML packages: the identity
                    # rejection must occur before those packages are touched.
                    result = subprocess.run([sys.executable, "-S", str(Path(__file__).with_name(script)),
                        *args, "--work-dir", str(work), "--config", str(config)],
                        capture_output=True, text=True)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("another synthesis profile", result.stderr)
                    self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertEqual([p.name for p in work.iterdir()], ["recipe.json"])

    def test_dry_run_consumers_reject_saved_profile_mismatch_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work/"recipe.json").write_text(DEFAULT_CONFIG.read_text())
            config = Path(__file__).parent/"configs/privet-kotik.json"
            before = (work/"recipe.json").read_bytes()
            for stage in ("features", "features-real", "train", "export"):
                with self.subTest(stage=stage):
                    result = subprocess.run([sys.executable, "-S", str(Path(__file__).with_name("pipeline.py")),
                        "--work-dir", str(work), "--config", str(config), "--dry-run", stage],
                        capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("another synthesis profile", result.stderr)
            self.assertEqual((work/"recipe.json").read_bytes(), before)
            self.assertEqual([p.name for p in work.iterdir()], ["recipe.json"])

    def test_export_candidate_recipe_is_checked_before_ml(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            config = Path(__file__).parent/"configs/privet-kotik.json"
            (work/"recipe.json").write_text(config.read_text())
            candidate = work/"models/old"
            candidate.mkdir(parents=True)
            (candidate/"recipe.json").write_text(json.dumps({"config": read_config(DEFAULT_CONFIG)}))
            result = subprocess.run([sys.executable, "-S", str(Path(__file__).with_name("model.py")),
                "export", "--work-dir", str(work), "--config", str(config), "--candidate", "old"],
                capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Export recipe differs", result.stderr)
            self.assertNotIn("ModuleNotFoundError", result.stderr)
            self.assertEqual([p.name for p in candidate.iterdir()], ["recipe.json"])

    def test_legacy_smoke_without_source_data_reaches_initialization(self):
        import model
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)/"absent"
            with patch.object(sys, "argv", ["model.py", "smoke", "--work-dir", str(work)]), \
                    patch.object(model, "initialize", side_effect=RuntimeError("fixture reached ML boundary")) as initialize:
                with self.assertRaisesRegex(RuntimeError, "reached ML boundary"):
                    model.main()
                initialize.assert_called_once()
            self.assertFalse(work.exists())

    def test_dry_run_does_not_create_private_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/"absent"
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("pipeline.py")),
                "--work-dir", str(destination), "--dry-run", "train", "--candidate", "tiny"],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--candidate tiny", result.stdout)
            self.assertFalse(destination.exists())

    def test_workspace_and_candidate_names_cannot_target_source(self):
        for path in (Path.home(), Path('/'), Path(__file__).resolve().parent):
            with self.assertRaises(ValueError): work_dir(path)
        for name in ("../outside", "a/b", ".", ""):
            with self.assertRaises(ValueError): candidate_dir(Path('/tmp'), name)

    def test_new_phrase_uses_its_vocabulary_for_generation_and_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = read_config(DEFAULT_CONFIG)
            config.update(model_id='privet_kotik_v1', wake_word='Привет, котик',
                          synthesis_profile='pk-v1')
            path = root/'recipe.json'
            path.write_text(json.dumps(config))
            destination = root/'absent'
            for stage in ('voices', 'synth-smoke', 'synth-full', 'verify-data'):
                with self.subTest(stage=stage):
                    result = subprocess.run([
                        sys.executable, str(Path(__file__).with_name('pipeline.py')),
                        '--work-dir', str(destination), '--config', str(path),
                        '--dry-run', stage,
                    ], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('--profile pk-v1', result.stdout)
                    self.assertNotIn('--profile pm-v1', result.stdout)
            self.assertFalse(destination.exists())

    def test_build_help_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/"absent"
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("pipeline.py")),
                "--work-dir", str(destination), "build", "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(destination.exists())

    def test_recipe_rejects_incompatible_frontend(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = read_config(DEFAULT_CONFIG)
            cfg['feature_step_ms'] = 20
            path = Path(directory)/'recipe.json'
            path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError): read_config(path)

    def test_source_manifest_rejects_leakage_and_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'audio'; root.mkdir()
            (root/'one.wav').write_bytes(b'fixture-one')
            (root/'two.wav').write_bytes(b'fixture-two')
            (Path(directory)/'outside.wav').write_bytes(b'outside')
            manifest = root/'manifest.jsonl'
            def check(rows):
                manifest.write_text('\n'.join(json.dumps(r) for r in rows))
                return load_rows(manifest, root)
            a = dict(id='one', path='one.wav', split='train', label=1, session='s1')
            b = dict(id='two', path='two.wav', split='val', label=1, session='s2')
            self.assertEqual(len(check([a,b])), 2)
            for bad in ({**b,'path':'one.wav'}, {**b,'session':'s1'},
                        {**b,'path':'../outside.wav'}, {**b,'id':'one'},
                        {**b,'sha256':'wrong'}):
                with self.assertRaises(ValueError): check([a,bad])


if __name__ == '__main__':
    unittest.main()
