#!/usr/bin/env python3
"""Resolve the complete macOS reference lock without installing native packages."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile


SOURCE = Path(__file__).resolve().parent


def pins(path):
    result = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9_.+!-]+)", line)
        if not match:
            raise ValueError(f"{path}:{number}: expected one exact package pin")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in result:
            raise ValueError(f"{path}:{number}: duplicate package {name}")
        result[name] = match[2]
    if not result:
        raise ValueError(f"{path}: expected a nonempty package lock")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=SOURCE / "requirements.txt")
    parser.add_argument("--lock", type=Path, default=SOURCE / "requirements-macos-arm64.lock.txt")
    args = parser.parse_args()
    locked = pins(args.lock)
    for name, version in pins(args.requirements).items():
        if locked.get(name) != version:
            raise ValueError(f"Reference lock must include direct dependency {name}=={version}")
    with tempfile.TemporaryDirectory(prefix="echo-reference-lock-") as directory:
        resolved = Path(directory) / "resolved.txt"
        # ONNX Runtime's pinned wheel requires macOS 14; uv otherwise targets 13.
        environment = {**os.environ, "MACOSX_DEPLOYMENT_TARGET": "14.0"}
        subprocess.run([
            "uv", "pip", "compile", "--python-version", "3.11",
            "--python-platform", "aarch64-apple-darwin", "--only-binary", ":all:",
            "--no-header", "--no-annotate", str(args.requirements), str(args.lock),
            "--output-file", str(resolved),
        ], env=environment, check=True, stdout=subprocess.DEVNULL)
        actual = pins(resolved)
        if actual != locked:
            changed = sorted(name for name in actual.keys() | locked.keys()
                             if actual.get(name) != locked.get(name))
            raise ValueError(f"Reference lock is not a complete resolved environment: {', '.join(changed)}")
    print(f"Reference lock verified: {len(locked)} exact pins, Python 3.11 / macOS 14 ARM64")


if __name__ == "__main__":
    main()
