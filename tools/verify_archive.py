#!/usr/bin/env python3
"""Verify this archive against MANIFEST.sha256.

Standard library only, so it runs in any Python 3 environment without NumPy, Torch
or CUDA. Exits 0 when every recorded file is present and unchanged and no unexpected
file was added; exits 1 otherwise.

Usage:
    python tools/verify_archive.py [--root ROOT] [--quiet]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

MANIFEST = "MANIFEST.sha256"
# Paths that are expected to exist but are not part of the recorded manifest.
IGNORED_PREFIXES = (".git/", "__pycache__/")
IGNORED_SUFFIXES = (".pyc",)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(root: Path) -> dict[str, str]:
    manifest = root / MANIFEST
    if not manifest.is_file():
        raise SystemExit(f"manifest not found: {manifest}")
    entries: dict[str, str] = {}
    for number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            raise SystemExit(f"{MANIFEST}:{number}: expected '<sha256>  <path>'")
        digest, relative = parts[0].strip().lower(), parts[1].strip()
        if len(digest) != 64:
            raise SystemExit(f"{MANIFEST}:{number}: malformed digest")
        entries[relative] = digest
    return entries


def walk(root: Path) -> set[str]:
    found: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST:
            continue
        if any(relative.startswith(prefix) for prefix in IGNORED_PREFIXES):
            continue
        if any(relative.endswith(suffix) for suffix in IGNORED_SUFFIXES):
            continue
        found.add(relative)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="archive root (default: the parent of tools/)")
    parser.add_argument("--quiet", action="store_true", help="print only failures and the summary")
    arguments = parser.parse_args(argv)

    root = arguments.root.resolve()
    expected = load_manifest(root)
    present = walk(root)

    missing = sorted(set(expected) - present)
    extra = sorted(present - set(expected))

    altered: list[str] = []
    verified = 0
    for relative in sorted(expected):
        if relative in missing:
            continue
        path = root / relative
        if sha256(path) != expected[relative]:
            altered.append(relative)
        else:
            verified += 1
            if not arguments.quiet and verified % 500 == 0:
                print(f"  verified {verified}/{len(expected)} ...", file=sys.stderr)

    print(f"manifest entries : {len(expected)}")
    print(f"verified         : {verified}")
    print(f"missing          : {len(missing)}")
    print(f"altered          : {len(altered)}")
    print(f"unexpected       : {len(extra)}")

    for label, items in (("MISSING", missing), ("ALTERED", altered), ("UNEXPECTED", extra)):
        for item in items[:50]:
            print(f"{label}: {item}")
        if len(items) > 50:
            print(f"{label}: ... and {len(items) - 50} more")

    if missing or altered or extra:
        print("RESULT: FAILED")
        return 1
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
