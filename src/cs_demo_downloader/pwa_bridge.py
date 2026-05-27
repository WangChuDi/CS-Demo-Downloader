"""Windows-only bridge helpers for calling PvpAlive.dll swapData."""
from __future__ import annotations

import os
import platform
import subprocess
from importlib import resources
from pathlib import Path
from typing import Sequence


class PvpAliveBridgeError(RuntimeError):
    """Raised when the PvpAlive bridge cannot run or swapData fails."""


def get_pvp_alive_bridge_path() -> str:
    """Return the packaged Windows bridge executable path."""
    bridge = resources.files('cs_demo_downloader').joinpath('bin', 'pvp_alive_bridge.exe')
    return str(bridge)


def _is_windows() -> bool:
    return platform.system().lower() == 'windows'


def call_pvp_alive_swap_data(
    dll_path: str,
    inner_json: str,
    bridge_path: str | None = None,
    timeout: int = 10,
) -> str:
    """Call PvpAlive.dll swapData through the bundled 32-bit Windows bridge.

    This helper intentionally supports Windows only. Linux/macOS callers should
    use the pure Python signer directly; Wine is not invoked by this project.
    """
    if not _is_windows():
        raise PvpAliveBridgeError('PvpAlive DLL fallback is only supported on Windows')

    dll = Path(dll_path)
    if not dll.is_file():
        raise PvpAliveBridgeError(f'PvpAlive.dll not found: {dll_path}')

    bridge = Path(bridge_path or get_pvp_alive_bridge_path())
    if not bridge.is_file():
        raise PvpAliveBridgeError(f'pvp_alive_bridge.exe not found: {bridge}')

    command: Sequence[str] = (str(bridge), str(dll), inner_json)
    env = os.environ.copy()
    env['PATH'] = f"{dll.parent}{os.pathsep}{env.get('PATH', '')}"

    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PvpAliveBridgeError(f'PvpAlive bridge execution failed: {exc}') from exc

    if completed.returncode != 0:
        stderr = completed.stderr.strip() or 'no stderr'
        raise PvpAliveBridgeError(f'PvpAlive bridge failed with exit code {completed.returncode}: {stderr}')

    result = completed.stdout.strip()
    if not result:
        raise PvpAliveBridgeError('PvpAlive bridge returned empty output')
    return result
