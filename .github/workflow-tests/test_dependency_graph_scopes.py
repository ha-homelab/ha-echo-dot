"""Keep managed dependency snapshots complete without overlapping training."""
import fnmatch
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class DependencyGraphScopesTests(unittest.TestCase):
    def setUp(self):
        config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text())
        self.pip = [row for row in config["updates"] if row["package-ecosystem"] == "pip"]

    def test_each_python_manifest_has_one_graph_owner(self):
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
            for row in self.pip:
                prefix = row["directory"].strip("/")
                if prefix and not path.startswith(prefix + "/"):
                    continue
                relative = path[len(prefix) + 1:] if prefix else path
                if any(fnmatch.fnmatchcase(relative, pattern) for pattern in row.get("exclude-paths", [])):
                    continue
                owners.append(row["directory"])
            with self.subTest(path=path):
                self.assertEqual(owners, ["/training" if path.startswith("training/") else "/"])

    def test_root_disables_version_prs_without_suppressing_security_updates(self):
        roots = [row for row in self.pip if row["directory"] == "/"]
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual(root["open-pull-requests-limit"], 0)
        self.assertNotIn("ignore", root)
        self.assertNotIn("target-branch", root)
        training = [row for row in self.pip if row["directory"] == "/training"]
        self.assertEqual(len(training), 1)
        self.assertGreater(training[0].get("open-pull-requests-limit", 5), 0)


if __name__ == "__main__":
    unittest.main()
