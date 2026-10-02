#!/usr/bin/env python3
"""Bounded, offline regression tests for recording import and model delivery.

Run from any working directory with: python3 /path/to/training/test_delivery.py -v
Only the Python standard library is required. All generated files stay inside
TemporaryDirectory instances. No microphone, network, credentials, or real Home
Assistant configuration is used. Model/report fixtures test packaging policy;
they are deliberately not valid inference models or acoustic acceptance evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import wave


TRAINING = Path(__file__).resolve().parent
RECORDINGS = TRAINING / "recordings.py"
DELIVERY = TRAINING / "delivery.py"
GATES = (
    "runtime", "strict_parity", "positive_recall", "zero_negative_events",
    "negative_duration", "clean_holdout", "human_trials", "room_soak",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TemporaryCLI(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="wakeword-regression-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.work = self.root / "work"

    def cli(self, script: Path, *args: object, error: str | None = None) -> dict | str:
        result = subprocess.run(
            [sys.executable, "-B", str(script), *map(str, args)],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if error is not None:
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn(error, result.stderr)
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)


class RecordingTests(TemporaryCLI):
    def make_wav(self, name: str, variant: int = 0, rate: int = 16000, frames: int = 3200) -> Path:
        path = self.root / name
        pcm = b"".join(struct.pack("<h", (index * (variant + 1)) % 2000 - 1000) for index in range(frames))
        with wave.open(str(path), "wb") as wav:
            wav.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            wav.writeframes(pcm)
        return path

    def import_clip(
        self, wav: Path, *, speaker: str = "speaker-01", session: str = "session-01",
        split: str = "train", transcript: str = "Example phrase",
        extra: tuple = (), error: str | None = None,
    ) -> dict | str:
        return self.cli(
            RECORDINGS, "import", "--work-dir", self.work, "--wav", wav,
            "--speaker", speaker, "--session", session, "--split", split,
            "--label", "positive", "--transcript", transcript, *extra, error=error,
        )

    def records(self) -> list[dict]:
        return [json.loads(line) for line in (self.work / "recordings/manifest.jsonl").read_text().splitlines()]

    def test_import_and_manifest_path_contract(self) -> None:
        summary = self.import_clip(self.make_wav("clip.wav"))
        self.assertEqual(summary["status"], "imported")
        record, = self.records()
        audio = self.work / "recordings" / record["path"]
        self.assertTrue(audio.is_file())
        self.assertEqual(record["sha256"], sha256(audio.read_bytes()))
        with wave.open(str(audio), "rb") as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate()), (1, 2, 16000))
            self.assertEqual(record["pcm_sha256"], sha256(wav.readframes(wav.getnframes())))
        self.assertEqual(record["label"], 1)
        self.assertEqual(record["source_kind"], "real_recording")
        self.assertEqual(record["voice"], record["speaker"])
        self.assertEqual(record["text"], record["transcript"])
        checked = self.cli(RECORDINGS, "check", "--work-dir", self.work)
        self.assertEqual(checked["clips"], 1)

    def test_identical_import_is_idempotent(self) -> None:
        wav = self.make_wav("clip.wav")
        self.import_clip(wav)
        before = (self.work / "recordings/manifest.jsonl").read_bytes()
        summary = self.import_clip(wav)
        self.assertEqual(summary["status"], "already_imported")
        self.assertEqual((self.work / "recordings/manifest.jsonl").read_bytes(), before)

    def test_same_pcm_in_different_wav_container_cannot_cross_splits(self) -> None:
        first = self.make_wav("first.wav")
        # A valid trailing RIFF chunk changes the file hash without changing PCM.
        changed = bytearray(first.read_bytes() + b"JUNK\x04\x00\x00\x00test")
        struct.pack_into("<I", changed, 4, len(changed) - 8)
        second = self.root / "different-container.wav"
        second.write_bytes(changed)
        self.assertNotEqual(sha256(first.read_bytes()), sha256(second.read_bytes()))
        self.import_clip(first)
        self.import_clip(second, session="session-02", split="test", error="already imported with different metadata")
        self.assertEqual(len(self.records()), 1)

    def test_recording_session_cannot_cross_splits_even_for_different_speakers(self) -> None:
        self.import_clip(self.make_wav("first.wav"))
        self.import_clip(
            self.make_wav("second.wav", variant=1), speaker="speaker-02",
            split="val", error="crosses dataset splits",
        )
        self.assertEqual(len(self.records()), 1)

    def test_same_speaker_new_session_is_allowed_and_reported(self) -> None:
        self.import_clip(self.make_wav("first.wav"))
        summary = self.import_clip(self.make_wav("second.wav", variant=1), session="session-02", split="val")
        self.assertEqual(summary["evaluation_scope"], "known_speaker_sessions")
        self.assertEqual(summary["speaker_overlap"], {"speaker-01": ["train", "val"]})
        self.cli(RECORDINGS, "check", "--work-dir", self.work)

    def test_strict_speaker_policy_rejects_new_session_in_another_split(self) -> None:
        self.import_clip(self.make_wav("first.wav"))
        self.import_clip(
            self.make_wav("second.wav", variant=1), session="session-02", split="val",
            extra=("--split-by", "speaker"), error="Speaker overlap is forbidden",
        )
        self.assertEqual(len(self.records()), 1)

    def test_duration_and_sample_rate_are_bounded(self) -> None:
        self.import_clip(self.make_wav("long.wav"), extra=("--max-seconds", "0.01"), error="Clip duration")
        self.import_clip(self.make_wav("empty.wav", frames=0), error="Clip duration")
        self.import_clip(self.make_wav("wrong-rate.wav", rate=8000), error="mono 16 kHz PCM16")
        self.assertFalse((self.work / "recordings/manifest.jsonl").exists())

    def test_positive_requires_a_transcript(self) -> None:
        self.import_clip(self.make_wav("clip.wav"), transcript="", error="Positive recordings require")

    def test_checker_rejects_modified_recording(self) -> None:
        self.import_clip(self.make_wav("clip.wav"))
        record, = self.records()
        audio = self.work / "recordings" / record["path"]
        changed = bytearray(audio.read_bytes())
        changed[-1] ^= 1
        audio.write_bytes(changed)
        self.cli(RECORDINGS, "check", "--work-dir", self.work, error="checksum mismatch")


class DeliveryTests(TemporaryCLI):
    def setUp(self) -> None:
        super().setUp()
        self.model_id = "fixture_word_v1"
        self.candidate = self.work / "models/candidate-1"
        self.candidate.mkdir(parents=True)
        # Header-only fixture: never invoke it in an inference runtime.
        self.model = b"\x18\x00\x00\x00TFL3" + b"packaging-fixture-not-an-inference-model"
        self.model_sha = sha256(self.model)
        self.sidecar = {
            "type": "micro", "version": 2, "model": self.model_id + ".tflite",
            "wake_word": "Example phrase", "trained_languages": ["en"],
            "micro": {"probability_cutoff": 0.85, "sliding_window_size": 5, "feature_step_size": 10},
        }
        self.source_sidecar = json.dumps(self.sidecar).encode()
        (self.candidate / (self.model_id + ".tflite")).write_bytes(self.model)
        (self.candidate / (self.model_id + ".json")).write_bytes(self.source_sidecar)
        self.protocol = {
            "model": {"path": "fixture.tflite", "sha256": self.model_sha},
            "validator": {"path": "fixture-validator", "sha256": "a" * 64},
            "cutoff": 0.90, "window": 5, "strict_parity": "FAIL",
        }
        self.report = {
            "model_sha256": self.model_sha, "cutoff": 0.90,
            "all_gates_passed": False, "gates": {name: {"status": "PASS"} for name in GATES},
        }
        self.report["gates"]["strict_parity"]["status"] = "FAIL"
        self.report["gates"]["human_trials"]["status"] = "NOT_RUN"
        self.protocol_path = self.root / "protocol.json"
        self.report_path = self.root / "test.json"
        self.output = self.work / "delivery" / self.model_id
        self.config = self.root / "temporary-ha-config"
        self.config.mkdir()
        self.write_evidence()

    def write_evidence(self) -> None:
        self.protocol_path.write_text(json.dumps(self.protocol))
        self.report["protocol_sha256"] = sha256(self.protocol_path.read_bytes())
        self.report_path.write_text(json.dumps(self.report))

    def passing_fixture(self) -> None:
        """Set fake policy evidence to PASS; this makes no acoustic-quality claim."""
        self.protocol["strict_parity"] = "PASS"
        self.report["all_gates_passed"] = True
        for gate in self.report["gates"].values():
            gate["status"] = "PASS"
        self.write_evidence()

    def package(self, *, experimental: bool = True, include_protocol: bool = True, error: str | None = None) -> dict | str:
        args = [
            "package", "--work-dir", self.work, "--candidate", "candidate-1",
            "--model-id", self.model_id, "--cutoff", "0.90",
        ]
        if include_protocol:
            args += ["--evaluation", self.protocol_path]
        args += ["--evaluation", self.report_path]
        if experimental:
            args += ["--experimental"]
        return self.cli(DELIVERY, *args, error=error)

    def stage(self, *, experimental: bool = True, error: str | None = None) -> dict | str:
        args = ["stage", "--package", self.output, "--ha-config-dir", self.config]
        if experimental:
            args += ["--experimental"]
        return self.cli(DELIVERY, *args, error=error)

    def test_failed_or_incomplete_gates_reject_accepted_packaging(self) -> None:
        self.package(experimental=False, error="Release gates are failed or incomplete")
        self.assertFalse(self.output.exists())

    def test_experimental_package_preserves_model_and_failure_reports(self) -> None:
        summary = self.package()
        self.assertEqual(summary["release_status"], "experimental")
        self.assertTrue(any("strict_parity=FAIL" in reason for reason in summary["experimental_reasons"]))
        self.assertTrue(any("human_trials=NOT_RUN" in reason for reason in summary["experimental_reasons"]))
        self.assertEqual((self.output / (self.model_id + ".tflite")).read_bytes(), self.model)
        self.assertEqual((self.output / "reports/000-protocol.json").read_bytes(), self.protocol_path.read_bytes())
        self.assertEqual((self.output / "reports/001-test.json").read_bytes(), self.report_path.read_bytes())
        checked = self.cli(DELIVERY, "verify", "--package", self.output)
        self.assertEqual(checked["release_status"], "experimental")

    def test_provisional_cutoff_changes_only_delivered_sidecar(self) -> None:
        self.package()
        self.assertEqual((self.candidate / (self.model_id + ".json")).read_bytes(), self.source_sidecar)
        self.assertEqual((self.output / "source" / (self.model_id + ".json")).read_bytes(), self.source_sidecar)
        delivered = json.loads((self.output / (self.model_id + ".json")).read_bytes())
        self.assertEqual(delivered["micro"]["probability_cutoff"], 0.90)
        delivered["micro"]["probability_cutoff"] = 0.85
        self.assertEqual(delivered, self.sidecar)
        manifest = json.loads((self.output / "manifest.json").read_bytes())
        self.assertEqual(manifest["source_sidecar"]["sha256"], sha256(self.source_sidecar))
        self.assertEqual(manifest["sidecar_adjustment"]["source"], 0.85)
        self.assertEqual(manifest["sidecar_adjustment"]["packaged"], 0.90)

    def test_all_matching_pass_fixture_exercises_accepted_policy(self) -> None:
        self.passing_fixture()
        self.assertEqual(self.package(experimental=False)["release_status"], "accepted")
        self.assertEqual(self.cli(DELIVERY, "verify", "--package", self.output)["release_status"], "accepted")

    def test_explicit_experimental_flag_is_preserved_despite_passing_fixture(self) -> None:
        self.passing_fixture()
        self.assertEqual(self.package()["release_status"], "experimental")

    def test_frozen_protocol_wrong_model_cutoff_or_window_always_rejects(self) -> None:
        original = json.loads(json.dumps(self.protocol))
        for field, value in (("model", {"sha256": "b" * 64}), ("cutoff", 0.70), ("window", 3)):
            with self.subTest(field=field):
                self.protocol = dict(original)
                self.protocol[field] = value
                self.write_evidence()
                self.package(error="Frozen protocol")
                self.assertFalse(self.output.exists())

    def test_gate_report_wrong_model_or_cutoff_always_rejects(self) -> None:
        original = json.loads(json.dumps(self.report))
        for field, value in (("model_sha256", "b" * 64), ("cutoff", 0.70)):
            with self.subTest(field=field):
                self.report = dict(original)
                self.report[field] = value
                self.write_evidence()
                self.package(error="different")
                self.assertFalse(self.output.exists())

    def test_missing_frozen_protocol_bytes_cannot_claim_acceptance(self) -> None:
        self.passing_fixture()
        self.package(experimental=False, include_protocol=False, error="frozen protocol bytes are not included")
        summary = self.package(include_protocol=False)
        self.assertEqual(summary["release_status"], "experimental")
        self.assertTrue(any("frozen protocol bytes" in reason for reason in summary["experimental_reasons"]))

    def test_missing_required_gate_cannot_be_hidden_by_overall_pass(self) -> None:
        self.passing_fixture()
        del self.report["gates"]["human_trials"]
        self.write_evidence()
        self.package(experimental=False, error="human_trials=NOT_RUN")

    def test_existing_package_is_never_overwritten(self) -> None:
        self.package()
        before = (self.output / "manifest.json").read_bytes()
        self.package(error="destination already exists")
        self.assertEqual((self.output / "manifest.json").read_bytes(), before)

    def test_verifier_rejects_changed_model_and_unlisted_files(self) -> None:
        self.package()
        model_path = self.output / (self.model_id + ".tflite")
        model_path.write_bytes(self.model + b"modified")
        self.cli(DELIVERY, "verify", "--package", self.output, error="checksum or size mismatch")
        model_path.write_bytes(self.model)
        (self.output / "unlisted.txt").write_text("unlisted payload")
        self.cli(DELIVERY, "verify", "--package", self.output, error="unlisted files")

    def test_experimental_stage_requires_its_own_explicit_flag(self) -> None:
        self.package()
        self.stage(experimental=False, error="staging requires the explicit --experimental flag")
        self.assertEqual(list(self.config.iterdir()), [])

    def test_staging_copies_only_two_files_and_is_idempotent(self) -> None:
        self.package()
        self.assertEqual(self.stage()["status"], "staged")
        target = self.config / "custom_wake_words"
        self.assertEqual({path.name for path in target.iterdir()}, {self.model_id + ".tflite", self.model_id + ".json"})
        for path in target.iterdir():
            self.assertEqual(path.read_bytes(), (self.output / path.name).read_bytes())
        before = {path.name: path.read_bytes() for path in target.iterdir()}
        self.assertEqual(self.stage()["status"], "already_staged")
        self.assertEqual({path.name: path.read_bytes() for path in target.iterdir()}, before)

    def test_stage_never_clobbers_a_different_existing_model(self) -> None:
        self.package()
        target = self.config / "custom_wake_words"
        target.mkdir()
        existing = target / (self.model_id + ".tflite")
        existing.write_bytes(b"pre-existing model must survive")
        self.stage(error="already exists; use a new model ID")
        self.assertEqual(existing.read_bytes(), b"pre-existing model must survive")
        self.assertFalse((target / (self.model_id + ".json")).exists())

    def test_stage_can_complete_an_identical_partial_pair(self) -> None:
        self.package()
        target = self.config / "custom_wake_words"
        target.mkdir()
        existing = target / (self.model_id + ".tflite")
        existing.write_bytes(self.model)
        self.assertEqual(self.stage()["status"], "staged")
        self.assertEqual(existing.read_bytes(), self.model)
        self.assertEqual((target / (self.model_id + ".json")).read_bytes(), (self.output / (self.model_id + ".json")).read_bytes())


if __name__ == "__main__":
    unittest.main()
