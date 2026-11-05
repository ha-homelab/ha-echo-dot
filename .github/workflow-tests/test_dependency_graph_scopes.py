"""Keep dependency update paths complete without competing lock writers."""
import fnmatch
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def matches(path, pattern):
    if pattern.startswith("/") and pattern.endswith("/"):
        return re.search(pattern[1:-1], path) is not None
    return fnmatch.fnmatchcase(path, pattern)


class DependencyGraphScopesTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "renovate.json").read_text())

    def test_each_python_manifest_has_one_update_path(self):
        paths = [
            "requirements-host-tests.txt",
            "requirements-lint.txt",
            "requirements-strict-tls.txt",
            "requirements-tls-test.txt",
            ".github/requirements-workflow-contracts.txt",
            ".github/requirements-host-tools.txt",
            "training/requirements.txt",
            "training/requirements-macos-arm64.lock.txt",
        ]
        for path in paths:
            owners = []
            if any(matches(path, pattern) for pattern in self.config["ignorePaths"]):
                owners.append("source-workflow")
            else:
                for manager in ("pip_requirements", "pip-compile"):
                    config = self.config.get(manager, {})
                    if any(matches(path, pattern) for pattern in config.get("ignorePaths", [])):
                        continue
                    if any(matches(path, pattern) for pattern in config.get("managerFilePatterns", [])):
                        owners.append(manager)
            expected = "pip_requirements"
            if path == "requirements-host-tests.txt":
                expected = "pip-compile"
            elif path == ".github/requirements-host-tools.txt":
                expected = "source-workflow"
            with self.subTest(path=path):
                self.assertEqual(owners, [expected])

    def test_root_requires_approval_without_suppressing_training_or_security(self):
        roots = [row for row in self.config["packageRules"] if row.get("dependencyDashboardApproval")]
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertTrue(self.config["dependencyDashboard"])
        self.assertIn("**", root["matchFileNames"])
        self.assertIn("!training/**", root["matchFileNames"])
        self.assertIn("pip_requirements", root["matchManagers"])
        self.assertIn("pip-compile", root["matchManagers"])
        self.assertNotEqual(self.config.get("vulnerabilityAlerts", {}).get("enabled"), False)
        self.assertIn("local>victron-venus/venus-os-ci-toolkit:renovate-fleet", self.config["extends"])


if __name__ == "__main__":
    unittest.main()
