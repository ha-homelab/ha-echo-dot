"""Small local fixtures; no model/data downloads or synthesis."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import common
import generate
import librispeech

try:
    import numpy as np
except ImportError:
    np = None


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix=".fixture-", dir=Path(__file__).parent)
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_immutable_conflict_preserves_original(self):
        target = self.root / "result.json"
        common.immutable_json(target, {"a": 1})
        common.immutable_json(target, {"a": 1})
        with self.assertRaises(ValueError):
            common.immutable_json(target, {"a": 2})
        self.assertEqual(json.loads(target.read_text()), {"a": 1})

    def test_archive_replay_and_corruption(self):
        archive = self.root / "example.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("corpus/data.txt", b"source content")
        target, marker = self.root / "out", self.root / "extracted.json"
        common.extract_archive(archive, target, marker, common.digest(archive))
        common.extract_archive(archive, target, marker, common.digest(archive))
        (target / "corpus/data.txt").write_bytes(b"corrupted")
        with self.assertRaises(ValueError):
            common.extract_archive(archive, target, marker, common.digest(archive))
        self.assertEqual((target / "corpus/data.txt").read_bytes(), b"corrupted")

    def test_archive_traversal_and_links_rejected(self):
        bad_zip = self.root / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as z:
            z.writestr("../escape", b"invalid")
        with self.assertRaises(ValueError):
            common.extract_archive(bad_zip, self.root / "out", self.root / "zip.json", common.digest(bad_zip))
        bad_tar = self.root / "bad.tar.gz"
        with tarfile.open(bad_tar, "w:gz") as t:
            entry = tarfile.TarInfo("link")
            entry.type, entry.linkname = tarfile.SYMTYPE, "../outside"
            t.addfile(entry)
        with self.assertRaises(ValueError):
            common.extract_archive(bad_tar, self.root / "out", self.root / "tar.json", common.digest(bad_tar))

    def test_verified_http_range_resume(self):
        body = b"local-fixture-content" * 128
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                header = self.headers.get("Range")
                observed.append(header)
                start = int(header.split("=")[1].split("-")[0]) if header else 0
                self.send_response(206 if header else 200)
                if header:
                    self.send_header("Content-Range", f"bytes {start}-{len(body)-1}/{len(body)}")
                self.send_header("Content-Length", str(len(body) - start))
                self.end_headers()
                self.wfile.write(body[start:])

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(("localhost", 0), Handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                pin = {"url": f"http://localhost:{server.server_port}/fixture", "bytes": len(body),
                       "sha256": hashlib.sha256(body).hexdigest()}
                target = self.root / "source.bin"
                target.with_name(target.name + ".part").write_bytes(body[:100])
                common.immutable_json(target.with_name(target.name + ".part.json"), pin)
                common.download(pin, target)
                self.assertEqual(target.read_bytes(), body)
                self.assertEqual(observed, ["bytes=100-"])
                common.download(pin, target)
                self.assertEqual(len(observed), 1)
                target.write_bytes(b"do not overwrite")
                with self.assertRaises(ValueError):
                    common.download(pin, target)
                self.assertEqual(target.read_bytes(), b"do not overwrite")
            finally:
                server.shutdown()
                thread.join()

    @unittest.skipIf(np is None, "numpy is required for feature fixtures")
    def test_feature_resume_uses_durable_row_prefix(self):
        target = self.root / "features.npy"
        first = common.FeatureWriter(target, (260, 2, 3), {"seed": 123})
        for i in range(130):
            first.append(i, np.full((2, 3), i, np.float16))
        # Last two rows may be present on disk, but only 128 were checkpointed.
        resumed = common.FeatureWriter(target, (260, 2, 3), {"seed": 123})
        self.assertEqual(resumed.done, 128)
        for i in range(resumed.done, 260):
            resumed.append(i, np.full((2, 3), i, np.float16))
        record = resumed.finish()
        self.assertEqual(record["completed_rows"], 260)
        np.testing.assert_array_equal(np.load(target)[:, 0, 0], np.arange(260))
        complete = common.FeatureWriter(target, (260, 2, 3), {"seed": 123})
        self.assertEqual(complete.finish(), record)
        with self.assertRaises(ValueError):
            common.FeatureWriter(target, (260, 2, 3), {"seed": 456})


class RecipeTests(unittest.TestCase):
    def test_synthesis_source_split_counts(self):
        jobs = generate.make_jobs()
        rows = [r for group in jobs.values() for r in group]
        self.assertEqual([len(x) for x in jobs.values()], [1625] * 4)
        self.assertEqual(len({r["source_id"] for r in rows}), 6500)
        expected = {("train", 1): 3200, ("val", 1): 400, ("test", 1): 400,
                    ("train", 0): 2000, ("val", 0): 250, ("test", 0): 250}
        for (split, label), count in expected.items():
            self.assertEqual(sum(r["split"] == split and r["label"] == label for r in rows), count)
        self.assertEqual(jobs, generate.make_jobs())
        self.assertTrue(all(r["text"].lower().replace(",", "").startswith("привет мышка") for r in rows if r["label"]))

    @unittest.skipIf(np is None, "numpy is required for speaker split fixtures")
    def test_librispeech_groups_and_windows_stay_disjoint(self):
        def row(speaker, subset, seconds):
            return {"path": f"raw/LibriSpeech/{subset}/{speaker}/1/{speaker}-1-0001.flac",
                    "subset": subset, "utterance_id": f"{speaker}-1-0001", "speaker_id": str(speaker),
                    "chapter_id": "1", "samples": seconds * 16000, "sample_rate": 16000,
                    "duration_seconds": float(seconds)}
        subsets = {"dev-clean": [row(i, "dev-clean", 500) for i in (1, 2, 3, 4)],
                   "test-clean": [row(i, "test-clean", 1801) for i in (5, 6)]}
        jobs, metadata, hour = librispeech.plan_index(subsets)
        self.assertEqual((jobs[0]["utterance_id"], jobs[0]["start_sample"], jobs[0]["end_sample"]),
                         ("2-1-0001", 1983768, 2024088))
        self.assertFalse(set(metadata["train_speakers"]) & set(metadata["val_speakers"]))
        self.assertFalse((set(metadata["train_speakers"]) | set(metadata["val_speakers"])) & set(metadata["test_speakers"]))
        by_source = {}
        for job in jobs:
            by_source.setdefault(job["utterance_id"], []).append(job)
        for group in by_source.values():
            self.assertEqual(len({r["split"] for r in group}), 1)
            ordered = sorted(group, key=lambda r: r["start_sample"])
            self.assertTrue(all(a["end_sample"] <= b["start_sample"] for a, b in zip(ordered, ordered[1:])))
        self.assertGreaterEqual(sum(r["duration_seconds"] for r in hour), 3600)
        subsets["test-clean"][0]["speaker_id"] = "1"
        with self.assertRaises(ValueError):
            librispeech.plan_index(subsets)


if __name__ == "__main__":
    unittest.main()
