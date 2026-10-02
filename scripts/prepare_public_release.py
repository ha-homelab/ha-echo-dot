#!/usr/bin/env python3
"""Validate or export only the explicit public-file manifest; never publish."""
from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "public-files.txt"
PRIVATE_PARTS = {"private", "backups", "logs", "downloads", "vendor", ".git", "__pycache__"}


def public_files() -> list[Path]:
    files = []
    seen = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts or "\\" in name
                or any(part in PRIVATE_PARTS for part in relative.parts)
                or ".local." in relative.name or relative.name.startswith(".env")):
            raise ValueError(f"Disallowed manifest path: {name}")
        if name in seen:
            raise ValueError(f"Duplicate manifest path: {name}")
        path = ROOT.joinpath(*relative.parts)
        current = ROOT
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ValueError(f"Symlinks cannot be exported: {name}")
        if not path.is_file():
            raise ValueError(f"Missing public file: {name}")
        if path.stat().st_size > 1024 * 1024:
            raise ValueError(f"Unexpectedly large documentation/helper file: {name}")
        path.read_text(encoding="utf-8")  # No firmware, images, or other binary payloads.
        files.append(path)
        seen.add(name)
    if not files:
        raise ValueError("Public manifest is empty")
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", type=Path,
                        help="new directory outside the source workspace; must not exist")
    parser.add_argument("--check-only", action="store_true", help="validate without copying")
    args = parser.parse_args()
    try:
        files = public_files()
        if args.check_only:
            if args.destination is not None:
                raise ValueError("Do not supply a destination with --check-only")
            print(f"Validated {len(files)} public files. No files copied; nothing published.")
            return 0
        if args.destination is None:
            raise ValueError("Supply a new destination directory or --check-only")
        if args.destination.is_symlink() or args.destination.exists():
            raise ValueError("Destination must not exist")
        destination = args.destination.expanduser().resolve()
        if destination == ROOT or ROOT in destination.parents:
            raise ValueError("Destination must be outside the source workspace")
        destination.mkdir(parents=True, exist_ok=False)
        for source in files:
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o644)
        print(f"Exported {len(files)} files to {destination}")
        print("No Git repository created and nothing published. Review content and licensing before release.")
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Public export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
