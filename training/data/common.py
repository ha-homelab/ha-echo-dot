"""Shared output, download, archive and resumable-array helpers (stdlib first)."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile


def digest(path: Path, algorithm="sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as src:
        for block in iter(lambda: src.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def encode_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def inside(root: Path, relative: str | Path) -> Path:
    root = root.resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path escapes the work directory: {relative}")
    return path


def immutable_bytes(path: Path, content: bytes) -> None:
    """Create once, or verify identical bytes. Never replace a conflicting file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Refusing to overwrite different content: {path}")
        return
    temp = path.with_name(path.name + ".pending-" + uuid.uuid4().hex)
    try:
        with temp.open("xb") as dst:
            dst.write(content)
            dst.flush()
            os.fsync(dst.fileno())
        # Hard-link publication is atomic and fails if a concurrent writer won.
        try:
            os.link(temp, path)
        except FileExistsError:
            if path.read_bytes() != content:
                raise ValueError(f"Concurrent conflicting output: {path}")
    finally:
        temp.unlink(missing_ok=True)


def immutable_json(path: Path, value) -> None:
    immutable_bytes(path, encode_json(value))


def immutable_jsonl(path: Path, rows, *, sort_keys=False) -> None:
    immutable_bytes(path, "".join(json.dumps(x, ensure_ascii=False, sort_keys=sort_keys) + "\n" for x in rows).encode())


def checkpoint(path: Path, value) -> None:
    """Replace only an explicitly named, recoverable progress record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending-" + uuid.uuid4().hex)
    try:
        with temporary.open("xb") as dst:
            dst.write(encode_json(value))
            dst.flush()
            os.fsync(dst.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextlib.contextmanager
def stage_lock(root: Path, name: str):
    """OS releases this advisory lock after interruption; no stale PID override."""
    import fcntl  # CLI help remains portable; execution targets macOS/Linux.
    root.mkdir(parents=True, exist_ok=True)
    path = inside(root, f".{name}.lock")
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"Another {name} process is using {root}") from None
        yield


def verify_file(path: Path, record: dict) -> None:
    if path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
        raise ValueError(f"Pinned size/SHA-256 mismatch: {path}")
    if record.get("md5") and digest(path, "md5") != record["md5"]:
        raise ValueError(f"Published MD5 mismatch: {path}")


def download(record: dict, destination: Path) -> None:
    """Resume a verified source into .part; final files are immutable."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        verify_file(destination, record)
        return
    partial = destination.with_name(destination.name + ".part")
    marker = partial.with_name(partial.name + ".json")
    if partial.is_symlink() or marker.is_symlink():
        raise ValueError("Download partial/progress files must not be symlinks")
    identity = {k: record[k] for k in ("url", "bytes", "sha256")}
    if partial.exists() and not marker.exists():
        raise ValueError(f"Unclaimed partial file; inspect it before retrying: {partial}")
    immutable_json(marker, identity)
    for attempt in range(4):
        current = partial.stat().st_size if partial.exists() else 0
        if current > record["bytes"]:
            raise ValueError(f"Partial exceeds pinned size: {partial}")
        if current == record["bytes"]:
            break
        try:
            headers = {"User-Agent": "ha-echo-dot-training-data/1", "Accept-Encoding": "identity"}
            if current:
                headers["Range"] = f"bytes={current}-"
            request = urllib.request.Request(record["url"], headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                status = getattr(response, "status", None)
                if current and status == 206:
                    expected_prefix = f"bytes {current}-"
                    if not response.headers.get("Content-Range", "").startswith(expected_prefix):
                        raise ValueError("Incorrect HTTP Content-Range; refusing to append")
                    mode = "ab"
                elif current:
                    print(f"Server did not resume {destination.name}; restarting its known partial", flush=True)
                    mode = "wb"
                else:
                    mode = "wb"
                with partial.open(mode) as dst:
                    while block := response.read(1024 * 1024):
                        dst.write(block)
                        if dst.tell() > record["bytes"]:
                            raise ValueError("Download exceeds pinned size")
                    dst.flush()
                    os.fsync(dst.fileno())
        except (OSError, urllib.error.URLError):
            if attempt == 3:
                raise
            time.sleep(attempt + 1)
            continue
        if partial.stat().st_size == record["bytes"]:
            break
    verify_file(partial, record)
    try:
        os.link(partial, destination)
    except FileExistsError:
        verify_file(destination, record)
    partial.unlink()
    marker.unlink()


def archive_member(root: Path, name: str) -> Path:
    pure = PurePosixPath(name)
    if not pure.parts or pure.is_absolute() or ".." in pure.parts or "\\" in name or ":" in pure.parts[0]:
        raise ValueError(f"Unsafe archive member: {name}")
    return inside(root, name)


def _copy_member(source, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".extracting-" + uuid.uuid4().hex)
    h = hashlib.sha256()
    # This is a restartable extraction scratch file, never a final output.
    with temporary.open("wb") as dst:
        while block := source.read(1024 * 1024):
            h.update(block)
            dst.write(block)
    expected = h.hexdigest()
    if target.exists():
        if digest(target) != expected:
            raise ValueError(f"Conflicting extracted file: {target}")
        temporary.unlink()
    else:
        os.link(temporary, target)
        temporary.unlink()
    return expected


def extract_archive(archive: Path, destination: Path, marker: Path, archive_sha: str) -> None:
    """Reject links/traversal; resume by verifying already extracted files."""
    if marker.exists():
        saved = json.loads(marker.read_text())
        if saved["archive_sha256"] != archive_sha:
            raise ValueError("Extraction marker belongs to another archive")
        for item in saved["files"]:
            path = archive_member(destination, item["path"])
            verify_file(path, item)
        return
    destination.mkdir(parents=True, exist_ok=True)
    records, seen = [], set()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as src:
            for info in src.infolist():
                target = archive_member(destination, info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise ValueError("Archive symlink rejected")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if info.filename in seen:
                    raise ValueError("Duplicate archive member")
                seen.add(info.filename)
                with src.open(info) as member:
                    sha = _copy_member(member, target)
                records.append({"path": info.filename, "bytes": info.file_size, "sha256": sha})
    else:
        with tarfile.open(archive, "r:gz") as src:
            for info in src:
                target = archive_member(destination, info.name)
                if not (info.isfile() or info.isdir()):
                    raise ValueError("Archive special file/link rejected")
                if info.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if info.name in seen:
                    raise ValueError("Duplicate archive member")
                seen.add(info.name)
                with src.extractfile(info) as member:
                    sha = _copy_member(member, target)
                records.append({"path": info.name, "bytes": info.size, "sha256": sha})
    immutable_json(marker, {"archive_sha256": archive_sha, "files": records})


class FeatureWriter:
    """A float16 NPY with a durable completed-row prefix and recipe identity."""
    def __init__(self, path: Path, shape: tuple[int, ...], identity: dict):
        import numpy as np
        self.path, self.shape = path, shape
        self.partial = path.with_name(path.name + ".partial")
        self.progress = path.with_name(path.name + ".progress.json")
        self.receipt = path.with_name(path.name + ".json")
        if any(p.is_symlink() for p in (self.partial, self.progress, self.receipt)):
            raise ValueError("Feature partial/progress/receipt files must not be symlinks")
        self.identity = {"shape": list(shape), "dtype": "float16", "recipe_sha256": fingerprint(identity)}
        self.array = None
        self.record = None
        self.done = 0
        path.parent.mkdir(parents=True, exist_ok=True)
        saved = json.loads(self.progress.read_text()) if self.progress.exists() else None
        if path.exists():
            record = json.loads(self.receipt.read_text()) if self.receipt.exists() else saved
            if not record or any(record.get(k) != v for k, v in self.identity.items()) or not record.get("sha256"):
                raise ValueError(f"Unclaimed/conflicting completed feature file: {path}")
            verify_file(path, record)
            immutable_json(self.receipt, record)
            self.record, self.done = record, shape[0]
            return
        if self.receipt.exists():
            raise ValueError(f"Feature receipt exists but final array is missing: {path}")
        if saved:
            if any(saved.get(k) != v for k, v in self.identity.items()):
                raise ValueError(f"Conflicting partial feature recipe: {path}")
            self.done = int(saved["completed_rows"])
            if not 0 <= self.done <= shape[0]:
                raise ValueError("Invalid completed-row count")
            if not self.partial.exists():
                if self.done:
                    raise ValueError("Nonempty checkpoint has no partial array")
                self.array = np.lib.format.open_memmap(self.partial, mode="w+", dtype=np.float16, shape=shape)
            else:
                self.array = np.lib.format.open_memmap(self.partial, mode="r+")
        else:
            if self.partial.exists():
                raise ValueError(f"Unclaimed partial feature file: {self.partial}")
            checkpoint(self.progress, {**self.identity, "completed_rows": 0})
            self.array = np.lib.format.open_memmap(self.partial, mode="w+", dtype=np.float16, shape=shape)
        if self.array.shape != shape or self.array.dtype != np.float16:
            raise ValueError("Partial feature shape/dtype mismatch")

    def append(self, index: int, value) -> None:
        if index < self.done:
            return
        if index != self.done or self.array is None:
            raise ValueError("Feature rows must arrive in deterministic contiguous order")
        self.array[index] = value
        self.done += 1
        if self.done % 128 == 0:
            self.flush()

    def flush(self):
        if self.array is not None:
            self.array.flush()
            checkpoint(self.progress, {**self.identity, "completed_rows": self.done})

    def finish(self) -> dict:
        if self.record:
            return self.record
        if self.done != self.shape[0]:
            raise ValueError("Incomplete feature array")
        self.flush()
        record = {**self.identity, "completed_rows": self.done,
                  "bytes": self.partial.stat().st_size, "sha256": digest(self.partial)}
        checkpoint(self.progress, record)
        del self.array
        self.array = None
        os.link(self.partial, self.path)
        self.partial.unlink()
        immutable_json(self.receipt, record)
        self.record = record
        return record
