#!/usr/bin/env python3
"""Verify that a private PWA signer wheel does not ship source files."""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path
from typing import cast


SOURCE_SUFFIXES = {'.py', '.pyx', '.c', '.cc', '.cpp', '.cxx', '.h', '.hpp', '.rs'}
COMPILED_SUFFIXES = {'.so', '.pyd', '.dll', '.dylib'}


def is_metadata_path(path: str) -> bool:
    parts = path.split('/')
    return any(part.endswith('.dist-info') for part in parts) or any(part.endswith('.data') for part in parts)


def verify_wheel(path: Path) -> list[str]:
    errors: list[str] = []
    with zipfile.ZipFile(path) as wheel:
        names = [name for name in wheel.namelist() if not name.endswith('/')]

    if not any(Path(name).suffix in COMPILED_SUFFIXES for name in names):
        errors.append('wheel does not contain a compiled extension artifact')

    for name in names:
        suffix = Path(name).suffix
        if suffix in SOURCE_SUFFIXES:
            errors.append(f'source-like file included: {name}')
            continue
        if is_metadata_path(name):
            continue
        if suffix in COMPILED_SUFFIXES:
            continue
        errors.append(f'unexpected non-compiled payload: {name}')

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument('wheels', nargs='+', type=Path, help='Path(s) to cs_demo_pwa_signer wheel files')
    args = parser.parse_args()
    wheels = cast(list[Path], args.wheels)
    failed = False

    for wheel in wheels:
        errors = verify_wheel(wheel)
        if errors:
            failed = True
            for error in errors:
                print(f'{wheel}: {error}', file=sys.stderr)
            continue
        print(f'{wheel}: OK')

    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
