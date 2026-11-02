"""Prevent unhashed CI tool installs or drift from the editable inputs."""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class HostToolsLockTests(unittest.TestCase):
    def test_host_installs_require_hashes_and_binary_distributions(self):
        workflow = yaml.safe_load((ROOT / ".github/workflows/tests.yml").read_text())
        commands = [line.strip() for step in workflow["jobs"]["python"]["steps"]
                    for line in step.get("run", "").splitlines()
                    if "python -m pip install " in line]
        self.assertEqual(len(commands), 2)
        for command in commands:
            with self.subTest(command=command):
                self.assertIn("--require-hashes", command)
                self.assertIn("--only-binary=:all:", command)
        self.assertIn("-r .github/requirements-host-tools.txt", commands[1])

    def test_lock_retains_editable_direct_requirements_and_hashes(self):
        lock = (ROOT / ".github/requirements-host-tools.txt").read_text()
        entries = {}
        for line in lock.replace("\\\n", " ").splitlines():
            if not line or line.lstrip().startswith("#"):
                continue
            match = re.match(r"([A-Za-z0-9_-]+)==([^ ;]+)", line)
            self.assertIsNotNone(match, line)
            self.assertRegex(line, r"--hash=sha256:[0-9a-f]{64}")
            entries[match[1].lower()] = match[2]
        for filename in ("requirements-tls-test.txt", "requirements-lint.txt"):
            for line in (ROOT / filename).read_text().splitlines():
                if not line or line.startswith("#"):
                    continue
                name, version = line.split("==")
                self.assertEqual(entries[name.lower()], version)


if __name__ == "__main__":
    unittest.main()
