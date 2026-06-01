"""Bridge helpers for explicitly calling PvpAlive.dll swapData."""
from __future__ import annotations

import os
import platform
import shutil
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


def _is_linux() -> bool:
    return platform.system().lower() == 'linux'


def _find_wine_binary(wine_binary: str | None = None) -> str:
    candidate = wine_binary or os.environ.get('CS_DEMO_DOWNLOADER_WINE_BINARY') or 'wine'
    if os.path.isabs(candidate) or os.sep in candidate:
        if os.path.isfile(candidate):
            return candidate
        raise PvpAliveBridgeError(f'Wine binary not found: {candidate}')

    resolved = shutil.which(candidate)
    if resolved:
        return resolved
    raise PvpAliveBridgeError(
        f'Wine binary not found: {candidate}. Install Wine or use the default compiled PWA signer.'
    )


def call_pvp_alive_swap_data(
    dll_path: str,
    inner_json: str,
    bridge_path: str | None = None,
    timeout: int = 10,
    allow_wine: bool = False,
    wine_binary: str | None = None,
) -> str:
    """Call PvpAlive.dll swapData through the bundled 32-bit Windows bridge.

    Windows runs the bridge executable directly. Linux can run it through Wine
    only when allow_wine is explicitly true. The normal downloader does not call
    this helper and keeps using the compiled signer by default.
    """
    use_wine = False
    if _is_windows():
        pass
    elif _is_linux() and allow_wine:
        use_wine = True
    else:
        message = 'PvpAlive DLL fallback is supported directly on Windows only; Linux callers must pass allow_wine=True explicitly or use the compiled signer'
        raise PvpAliveBridgeError(message)

    dll = Path(dll_path)
    if not dll.is_file():
        raise PvpAliveBridgeError(f'PvpAlive.dll not found: {dll_path}')

    bridge = Path(bridge_path or get_pvp_alive_bridge_path())
    if not bridge.is_file():
        raise PvpAliveBridgeError(f'pvp_alive_bridge.exe not found: {bridge}')

    if use_wine:
        command: Sequence[str] = (_find_wine_binary(wine_binary), str(bridge), str(dll), inner_json)
    else:
        command = (str(bridge), str(dll), inner_json)
    env = os.environ.copy()
    env['PATH'] = f"{dll.parent}{os.pathsep}{env.get('PATH', '')}"
    if use_wine:
        env.setdefault('WINEDEBUG', '-all')

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


def call_pvp_alive_swap_data_wine(
    dll_path: str,
    inner_json: str,
    bridge_path: str | None = None,
    timeout: int = 10,
    wine_binary: str | None = None,
) -> str:
    """Call PvpAlive.dll swapData through Wine on Linux.

    This is an explicit opt-in helper. The normal Linux downloader path does not
    auto-detect or invoke Wine.
    """
    return call_pvp_alive_swap_data(
        dll_path=dll_path,
        inner_json=inner_json,
        bridge_path=bridge_path,
        timeout=timeout,
        allow_wine=True,
        wine_binary=wine_binary,
    )
