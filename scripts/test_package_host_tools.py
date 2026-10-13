"""Source releases never infer their file inventory from the checkout."""

import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import package_host_tools as packaging


class PublicSourcePackages(unittest.TestCase):
    def test_allowlist_and_repeatability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "VERSION").write_text("0.1.0\n")
            (root / "README.md").write_text("Synthetic public text.\n")
            manifest = root / "public-files.txt"
            manifest.write_text("VERSION\nREADME.md\n")
            (root / "private").mkdir()
            (root / "private" / "credentials.json").write_text("PRIVATE_SENTINEL")
            (root / "unlisted.txt").write_text("UNLISTED_SENTINEL")
            with patch.object(packaging.public_export, "ROOT", root), patch.object(
                packaging.public_export, "MANIFEST", manifest
            ):
                one = packaging.package(root / "one", "a" * 40)
                two = packaging.package(root / "two", "a" * 40)
                self.assertEqual(one.read_bytes(), two.read_bytes())
                with tarfile.open(one) as tar:
                    self.assertEqual(sorted(tar.getnames()), [
                        "ha-echo-dot-public-tools/README.md", "ha-echo-dot-public-tools/VERSION"
                    ])
                metadata = json.loads((one.parent / "ha-echo-dot-public-tools.version.json").read_text())
                self.assertEqual(metadata["archive_sha256"], hashlib.sha256(one.read_bytes()).hexdigest())
                self.assertEqual(metadata["version"], "0.1.0")
                self.assertEqual(metadata["source_sha"], "a" * 40)
                with self.assertRaises(FileExistsError):
                    packaging.package(root / "one", "a" * 40)

    def test_private_inventory_entry_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "VERSION").write_text("0.1.0\n")
            manifest = root / "public-files.txt"
            manifest.write_text("VERSION\nprivate/credentials.json\n")
            with patch.object(packaging.public_export, "ROOT", root), patch.object(
                packaging.public_export, "MANIFEST", manifest
            ):
                with self.assertRaises(ValueError):
                    packaging.package(root / "output", "a" * 40)
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
