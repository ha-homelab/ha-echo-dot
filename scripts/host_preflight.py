#!/usr/bin/env python3
"""Read-only host inventory. Does not contact, unlock, or flash any device."""

import json
import platform
import shutil
import sys
from datetime import datetime, timezone


def main():
    system = platform.system()
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Host tools only; device and Home Assistant readiness are NOT checked",
        "host": {"system": system, "release": platform.release(), "machine": platform.machine()},
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "tools": {name: shutil.which(name) for name in ("adb", "fastboot", "lsusb", "uv", "echoctl")},
        "notes": [
            "Tool presence does not prove a suitable amonet USB/bootrom environment.",
            "Model, Fire OS / Android SDK, recovery and per-device backup must be verified separately.",
            "The echoctl 0.0.8 INSTALLER requires Fire OS 6 / SDK 25; Fire OS 5 uses a separate legacy installation path.",
            "amonet 2 Option 1 documents Linux or Windows; choose a reviewed procedure for the exact device."
        ],
    }
    if system == "Darwin":
        result["notes"].append("macOS can manage EchoLocal, but this does not validate bootrom unlocking on macOS or a VM.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
