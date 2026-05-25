#!/usr/bin/env python3
"""Compatibility wrapper for the packaged CLI."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from cs_demo_downloader.cli import main


if __name__ == "__main__":
    sys.exit(main())
