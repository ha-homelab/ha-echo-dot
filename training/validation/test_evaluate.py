"""Small orchestration fixtures; no TensorFlow, audio downloads, or hardware needed."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parents[1] / "evaluate.py")
E = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E)

# This deliberately fake executable tests process orchestration and evidence handling,
# not inference correctness. Real Go inference has a separate bounded smoke check.
FAKE = '''#!/usr/bin/env python3
import sys,json,hashlib
from pathlib import Path
a=dict(zip(sys.argv[1::2],sys.argv[2::2]))
rows=[json.loads(s) for s in Path(a['-manifest']).read_text().splitlines()]
pos=sum(r['label']=='positive' for r in rows); neg=len(rows)-pos
seconds=sum((Path(a['-manifest']).parent/r['pcm']).stat().st_size/32000 for r in rows if r['label']=='negative')
fp=sum('false-positive' in r['id'] for r in rows)
grid=[dict(threshold=float(t),positive_clips_detected=pos,negative_clips_detected=fp,negative_echo_timing_events=fp) for t in a['-thresholds'].split(',')]
Path(a['-batch-out']).write_text('')
print(json.dumps(dict(runtime='github.com/zserge/microwakeword@v0.0.0-20260330234603-bfaf3840114e',model_sha256=hashlib.sha256(Path(a['-model']).read_bytes()).hexdigest(),sliding_window=int(a['-window']),clips=len(rows),positive_clips=pos,negative_clips=neg,negative_source_seconds=seconds,thresholds=grid)))
'''


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        (self.work / "bin").mkdir()
        self.binary = self.work / "bin/validate"
        self.binary.write_text(FAKE)
        self.binary.chmod(0o700)
        self.model = self.work / "model.tflite"
        self.model.write_bytes(b"not a real model: orchestration fixture")
        self.parity = self.work / "parity.json"
        self.parity.write_text(json.dumps({"model_sha256": E.sha(self.model), "passed": True,
            "allowed_max_raw_error": 1, "max_absolute_raw_error": 0,
            "tensorflow_kernel_resolver": "BUILTIN_REF", "invocations": 3}))
        self.val = self.manifest("val", 1)
        self.test = self.manifest("test", 3)

    def manifest(self, name, byte, fp=False):
        path = self.work / (name + ".jsonl")
        rows = []
        for i, label in enumerate(("positive", "negative")):
            audio = self.work / f"{name}-{i}.pcm"
            audio.write_bytes(bytes([byte+i, 0]) * 16000)
            rows.append({"id": "false-positive" if fp and i else f"{name}-{i}", "label": label,
                         "pcm": audio.name, "leading_ms": 3000, "trailing_ms": 1000})
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
        return path

    def calibration(self, run="first"):
        return E.calibrate(argparse.Namespace(work_dir=self.work, run_id=run, thresholds="0.85,0.9",
            min_recall=.98, min_cutoff=.85, window=5, model=self.model, validator=None,
            manifest=[self.val], parity_report=[self.parity]))

    def freeze(self, run="first", cutoff=.9, evaluation_only=False):
        return E.freeze(argparse.Namespace(work_dir=self.work, run_id=run, cutoff=cutoff,
            evaluation_only=evaluation_only, test_manifest=[self.test], min_test_negative_seconds=1))

    def run_test(self, run="first", reuse=None):
        return E.final_test(argparse.Namespace(work_dir=self.work, run_id=run, allow_reused_test=reuse))

    def test_freeze_blocks_unvalidated_cutoff_and_model_changes(self):
        self.calibration()
        with self.assertRaisesRegex(ValueError, "cutoff"):
            self.freeze(cutoff=.7)
        self.freeze()
        self.model.write_bytes(b"changed after freeze")
        with self.assertRaisesRegex(ValueError, "frozen file changed"):
            self.run_test()
        self.assertFalse((self.work / "evaluation/holdout-history").exists())

    def test_failed_parity_is_not_hidden_by_good_detection(self):
        r = json.loads(self.parity.read_text()); r["passed"] = False; r["max_absolute_raw_error"] = 16
        self.parity.write_text(json.dumps(r))
        self.assertFalse(self.calibration()["passed"])
        with self.assertRaisesRegex(ValueError, "strict parity FAILED"):
            self.freeze()
        self.freeze(evaluation_only=True)
        report = self.run_test()
        self.assertEqual(report["gates"]["strict_parity"]["status"], "FAIL")
        self.assertEqual(report["gates"]["positive_recall"]["status"], "PASS")
        self.assertFalse(report["offline_gates_passed"])

    def test_false_activation_fails_and_test_is_consumed(self):
        self.test = self.manifest("false-test", 6, fp=True)
        self.calibration(); self.freeze()
        report = self.run_test()
        self.assertEqual(report["gates"]["zero_negative_events"]["status"], "FAIL")
        self.assertFalse(report["all_gates_passed"])
        self.calibration("second"); self.freeze("second")
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.run_test("second")
        reused = self.run_test("second", "fixture analysis after a known failure")
        self.assertEqual(reused["gates"]["clean_holdout"]["status"], "FAIL")
        self.assertEqual(reused["heldout_status"], "reused_not_clean")

    def test_good_offline_result_still_requires_human_and_room_evidence(self):
        self.calibration(); self.freeze()
        report = self.run_test()
        self.assertTrue(report["offline_gates_passed"])
        self.assertFalse(report["all_gates_passed"])
        self.assertEqual(report["gates"]["human_trials"]["status"], "NOT_RUN")
        self.assertEqual(report["gates"]["room_soak"]["status"], "NOT_RUN")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_test()

    def test_overlap_and_protocol_tampering_are_rejected(self):
        self.calibration()
        self.test = self.val
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.freeze()
        self.test = self.work / "test.jsonl"
        self.freeze()
        p = self.work / "evaluation/first/protocol.json"
        p.write_text(p.read_text().replace('"cutoff": 0.9', '"cutoff": 0.7'))
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.run_test()


if __name__ == "__main__":
    unittest.main()
