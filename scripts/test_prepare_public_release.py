#!/usr/bin/env python3
"""Validate public-manifest path rejection without publishing or reading WIP."""

from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "prepare_public_release", ROOT / "scripts" / "prepare_public_release.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PreparePublicReleaseTests(unittest.TestCase):
    def _synthetic_workspace(self):
        """Return an isolated fake repository root and its manifest path."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "repo"
        root.mkdir()
        (root / "README.md").write_text("synthetic public file\n", encoding="utf-8")
        manifest = root / "public-files.txt"
        manifest.write_text("README.md\n", encoding="utf-8")
        return root, manifest

    def _bind(self, root: Path, manifest: Path):
        return mock.patch.multiple(MODULE, ROOT=root.resolve(), MANIFEST=manifest)

    def test_public_files_accepts_allowed_synthetic_manifest(self):
        root, manifest = self._synthetic_workspace()
        with self._bind(root, manifest):
            files = MODULE.public_files()
        self.assertEqual([path.name for path in files], ["README.md"])
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in files))

    def test_rejects_disallowed_private_vendor_env_and_local_paths(self):
        cases = (
            "host/private/secret.md",
            "docs/.env.example",
            "research/notes.local.md",
            "vendor/pkg/readme.md",
        )
        for name in cases:
            with self.subTest(name=name):
                root, manifest = self._synthetic_workspace()
                target = root.joinpath(*Path(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("disallowed fixture\n", encoding="utf-8")
                manifest.write_text(name + "\n", encoding="utf-8")
                with self._bind(root, manifest):
                    with self.assertRaisesRegex(ValueError, r"Disallowed manifest path"):
                        MODULE.public_files()

    def test_rejects_absolute_and_traversal_paths_with_outside_root_fixture(self):
        with tempfile.TemporaryDirectory() as outside_tmp:
            outside_root = Path(outside_tmp)
            escape = outside_root / "escape.md"
            escape.write_text("outside fixture\n", encoding="utf-8")

            root, manifest = self._synthetic_workspace()
            # Place the synthetic repo beside a sibling file for a ../ traversal case.
            sibling = root.parent / "sibling.md"
            sibling.write_text("sibling fixture\n", encoding="utf-8")

            for name in (str(escape), "../sibling.md"):
                with self.subTest(name=name):
                    manifest.write_text(name + "\n", encoding="utf-8")
                    with self._bind(root, manifest):
                        with self.assertRaisesRegex(ValueError, r"Disallowed manifest path"):
                            MODULE.public_files()

    def test_check_only_rejects_nonexistent_destination_without_creating_it(self):
        root, manifest = self._synthetic_workspace()
        destination = root.parent / "export-target-does-not-exist"
        self.assertFalse(destination.exists())
        stderr = io.StringIO()
        with self._bind(root, manifest):
            with mock.patch("sys.argv", ["prepare_public_release.py", "--check-only", str(destination)]):
                with redirect_stderr(stderr):
                    code = MODULE.main()
        self.assertEqual(code, 1)
        self.assertIn("Do not supply a destination with --check-only", stderr.getvalue())
        self.assertFalse(destination.exists())


    def test_rejects_symlink_public_file(self):
        """Reachable export failure: a public-named symlink must not be copied."""
        root, manifest = self._synthetic_workspace()
        target = root / "docs" / "guide.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("real guide\n", encoding="utf-8")
        link = root / "README-link.md"
        link.symlink_to(target)
        manifest.write_text("README-link.md\n", encoding="utf-8")
        with self._bind(root, manifest):
            with self.assertRaisesRegex(ValueError, r"Symlinks cannot be exported"):
                MODULE.public_files()

    def test_rejects_empty_manifest_and_destination_inside_workspace(self):
        """Empty manifest and in-tree destinations fail without creating an export."""
        root, manifest = self._synthetic_workspace()
        manifest.write_text("# comments only\n\n", encoding="utf-8")
        with self._bind(root, manifest):
            with self.assertRaisesRegex(ValueError, r"Public manifest is empty"):
                MODULE.public_files()

        root, manifest = self._synthetic_workspace()
        inside = root / "out-export"
        self.assertFalse(inside.exists())
        stderr = io.StringIO()
        with self._bind(root, manifest):
            with mock.patch("sys.argv", ["prepare_public_release.py", str(inside)]):
                with redirect_stderr(stderr):
                    code = MODULE.main()
        self.assertEqual(code, 1)
        self.assertIn("Destination must be outside the source workspace", stderr.getvalue())
        self.assertFalse(inside.exists())


if __name__ == "__main__":
    unittest.main()
