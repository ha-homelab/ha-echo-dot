#!/usr/bin/env python3
"""Expose only one verified USB serial/physical port in a private directory.

Run as root on Synology. This creates/removes proxy nodes, never real /dev nodes.
Mount the directory read-only at /dev/bus/usb with cgroup rule c 189:* rw.
"""
import os
from pathlib import Path
import signal
import stat
import sys
import time

port, serial, destination = sys.argv[1:]
source = Path('/sys/bus/usb/devices') / port
root = Path(destination).resolve()
# Retain the historical host directory for already installed USB adapters.
assert root.name == 'usb-proxy' and any(
    prefix in str(root) for prefix in ('/ha-echo-dot/private/', '/ha-echo/private/')
)
os.umask(0o077)
root.mkdir(mode=0o700, parents=True, exist_ok=True)
running = True


def stop(*_):
    global running
    running = False


def identity():
    try:
        if (source / 'serial').read_text().strip() != serial:
            return None
        device_id = (source / 'dev').read_text().strip()
        major, minor = map(int, device_id.split(':'))
        bus = int((source / 'busnum').read_text())
        device = int((source / 'devnum').read_text())
        assert major == 189 and minor == (bus - 1) * 128 + device - 1
        actual = Path(f'/dev/bus/usb/{bus:03d}/{device:03d}').stat()
        assert stat.S_ISCHR(actual.st_mode) and actual.st_rdev == os.makedev(major, minor)
        # Re-read identity after all attributes to reject an in-progress replacement.
        if ((source / 'serial').read_text().strip() != serial
                or (source / 'dev').read_text().strip() != device_id
                or int((source / 'busnum').read_text()) != bus
                or int((source / 'devnum').read_text()) != device):
            return None
        return bus, device, major, minor
    except (FileNotFoundError, OSError, ValueError):
        return None


def clean():
    for node in root.glob('*/*'):
        assert not node.is_symlink() and stat.S_ISCHR(node.lstat().st_mode), 'Unexpected proxy contents'
        node.unlink()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGHUP, stop)
clean()
previous = None
try:
    while running:
        current = identity()
        if current != previous:
            clean()
            if current:
                bus, device, major, minor = current
                directory = root / f'{bus:03d}'
                directory.mkdir(mode=0o700, exist_ok=True)
                node = directory / f'{device:03d}'
                os.mknod(node, stat.S_IFCHR | 0o600, os.makedev(major, minor))
                if identity() != current:
                    node.unlink()
                    continue
                print(f'Exposed verified Echo at {bus:03d}/{device:03d}', flush=True)
            else:
                print('Echo disconnected; no USB node exposed', flush=True)
            previous = current
        time.sleep(0.5)
finally:
    clean()
