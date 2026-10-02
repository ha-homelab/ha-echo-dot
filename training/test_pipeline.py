"""Fast contract checks; no network, installed ML runtime, or device is required."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DEFAULT_CONFIG, candidate_dir, read_config, work_dir
from features import load_rows


class WorkflowContracts(unittest.TestCase):
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
