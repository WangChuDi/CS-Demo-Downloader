"""Small stdout/stderr logging helpers for CLI and Docker output."""
from __future__ import annotations

import datetime
import sys
from typing import TextIO


def _timestamp() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def log_info(message: str, stream: TextIO | None = None) -> None:
    target = sys.stdout if stream is None else stream
    print(f"[{_timestamp()}] {message}", file=target, flush=True)


def log_error(message: str) -> None:
    log_info(message, stream=sys.stderr)
