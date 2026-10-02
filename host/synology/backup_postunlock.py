#!/usr/bin/env python3
"""Read-only raw backup from TWRP; requires unmounted eMMC filesystems."""
import hashlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time

serial, destination = sys.argv[1:]
os.umask(0o077)
root = Path(destination)
root.mkdir(parents=True, exist_ok=True)
adb = ["adb", "-s", serial]


def output(*args, timeout=900):
    return subprocess.check_output(adb + list(args), timeout=timeout).decode().strip()


assert output("get-serialno") == serial
assert output("get-state") == "recovery"
assert "/dev/block/mmcblk0" not in output("shell", "cat", "/proc/mounts"), "Unmount data/cache first"
manifest = {"serial": serial, "stage": "post-amonet2-before-wipe", "images": []}
for name in ["mmcblk0", "mmcblk0boot0", "mmcblk0boot1"]:
    source = "/dev/block/" + name
    size = int(output("shell", "blockdev", "--getsize64", source))
    final = root / (name + ".img.gz")
    temporary = root / (name + ".img.gz.partial")
    assert not final.exists() and not temporary.exists(), "Backup path already used"
    print(f"Backing up {name}: {size} bytes", flush=True)
    count = 0
    last_report = time.monotonic()
    with temporary.open("xb") as target, (root / (name + ".stderr")).open("xb") as errors:
        process = subprocess.Popen(["timeout", "1800"] + adb + ["exec-out", "gzip", "-1", "-c", source], stdout=subprocess.PIPE, stderr=errors)
        while chunk := process.stdout.read(1024 * 1024):
            target.write(chunk)
            count += len(chunk)
            if time.monotonic() - last_report >= 30:
                print(f"{name}: {count} compressed bytes saved", flush=True)
                last_report = time.monotonic()
        assert process.wait() == 0, "ADB backup failed; inspect private stderr"
        target.flush()
        os.fsync(target.fileno())
    print(f"Checking device and saved SHA256: {name}", flush=True)
    device_hash = output("shell", "sha256sum", source).split()[0]
    disk_hash = hashlib.sha256()
    uncompressed_size = 0
    with gzip.open(temporary, "rb") as saved:
        while chunk := saved.read(1024 * 1024):
            disk_hash.update(chunk)
            uncompressed_size += len(chunk)
    assert uncompressed_size == size, "Incomplete backup"
    assert device_hash == disk_hash.hexdigest(), "Checksum mismatch"
    temporary.rename(final)
    manifest["images"].append({"source": source, "path": str(final), "bytes": size, "gzip_bytes": count, "sha256": device_hash})
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified {name}: {size} raw bytes, {count} compressed bytes", flush=True)
print("POST-UNLOCK BACKUP VERIFIED", flush=True)
