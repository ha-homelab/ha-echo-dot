"""Check the installed training environment against the protobuf security regression.

Run with WORK/.venv/bin/python after setup; no datasets, training, or devices.
"""
from importlib import metadata
import unittest

from google.protobuf import any_pb2, json_format
from packaging.requirements import Requirement


class DependencySecurityTests(unittest.TestCase):
    def test_nested_any_obeys_the_requested_recursion_limit(self):
        """CVE-2026-0994 must fail at the protobuf limit, not Python's stack limit."""
        payload = {"@type": "type.googleapis.com/google.protobuf.Any", "value": {}}
        for _ in range(16):
            payload = {"@type": "type.googleapis.com/google.protobuf.Any", "value": payload}
        with self.assertRaisesRegex(json_format.ParseError, "recursion depth"):
            json_format.ParseDict(payload, any_pb2.Any(), max_recursion_depth=4)

    def test_tensorflow_accepts_the_installed_protobuf(self):
        """An isolated protobuf bump must not violate TensorFlow's package metadata."""
        requirements = [Requirement(value) for value in metadata.requires("tensorflow")]
        protobuf = [value for value in requirements if value.name == "protobuf"]
        self.assertEqual(len(protobuf), 1)
        self.assertIn(metadata.version("protobuf"), protobuf[0].specifier)


if __name__ == "__main__":
    unittest.main()
