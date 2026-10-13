#!/usr/bin/env python3
"""Package only the reviewed public text-file inventory; never build firmware."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

import prepare_public_release as public_export

PREFIX = "ha-echo-dot-public-tools"


def package(output: Path, source_sha: str) -> Path:
    """Create a new deterministic source archive and explicit version metadata."""
    if re.fullmatch(r"[a-f0-9]{40}", source_sha) is None:
        raise ValueError("Expected an exact source commit")
    version = (public_export.ROOT / "VERSION").read_text().strip()
    if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version) is None:
        raise ValueError("Invalid prepared host-tools version")
    files = public_export.public_files()
    if public_export.ROOT / "VERSION" not in files:
        raise ValueError("Public archive must contain its version")
    # Validate the complete allowlist before creating any output. Excluding a
    # private path is not enough: no unlisted file is considered at all.
    payload = {p.relative_to(public_export.ROOT).as_posix(): p.read_bytes() for p in files}
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f"{PREFIX}.tar.gz"
    with archive.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for name, data in sorted(payload.items()):
                    member = tarfile.TarInfo(f"{PREFIX}/{name}")
                    member.size = len(data)
                    member.mode = 0o644
                    member.mtime = member.uid = member.gid = 0
                    tar.addfile(member, io.BytesIO(data))
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        expected = {f"{PREFIX}/{name}" for name in payload}
        if len(members) != len(expected) or {m.name for m in members} != expected:
            raise ValueError("Public archive inventory mismatch")
        for member in members:
            if not member.isfile():
                raise ValueError("Archive contains a non-regular file")
            with tar.extractfile(member) as stream:
                if stream.read() != payload[member.name[len(PREFIX) + 1:]]:
                    raise ValueError("Public archive content mismatch")
    metadata = {
        "schema": 1,
        "version": version,
        "source_sha": source_sha,
        "scope": "public host tools and documentation source; no firmware or model weights",
        "archive": archive.name,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "files": len(payload),
    }
    (output / f"{PREFIX}.version.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return archive


if __name__ == "__main__":
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=public_export.ROOT, text=True
    ).strip()
    print(package(public_export.ROOT / "release-dist", sha))
