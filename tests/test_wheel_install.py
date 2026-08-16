import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
import venv
from json import JSONDecodeError
from pathlib import Path
from typing import cast


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_NAME = 'cs-demo-downloader'
IMPORT_NAME = 'cs_demo_downloader'


def _supports_bundled_signer() -> bool:
    machine = platform.machine().lower().replace('-', '_')
    return sys.implementation.name == 'cpython' and sys.version_info[:2] == (3, 12) and sys.platform.startswith('linux') and machine in {'x86_64', 'amd64'}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        _ = path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _venv_python(venv_dir: Path) -> Path:
    if os.name == 'nt':
        return venv_dir / 'Scripts' / 'python.exe'
    return venv_dir / 'bin' / 'python'


def _venv_console_script(venv_dir: Path) -> Path:
    if os.name == 'nt':
        return venv_dir / 'Scripts' / 'cs-demo-downloader.exe'
    return venv_dir / 'bin' / 'cs-demo-downloader'


def _subprocess_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in (
        'COMSPEC',
        'HOME',
        'PATH',
        'PATHEXT',
        'SystemRoot',
        'TEMP',
        'TMP',
        'TMPDIR',
        'USERPROFILE',
        'WINDIR',
    ):
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['PIP_NO_INDEX'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    return env


class PipInstallTests(unittest.TestCase):
    def run_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int = 240,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if completed.returncode != 0:
            command_text = repr(command)
            message = '\n'.join(
                [
                    f'Command failed with exit code {completed.returncode}: {command_text}',
                    f'stdout:\n{completed.stdout}',
                    f'stderr:\n{completed.stderr}',
                ]
            )
            self.fail(message)
        return completed

    def test_pip_install_dot_installs_and_runs_from_site_packages(self):
        env = _subprocess_env()

        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            install_venv = temp_dir / 'install-venv'
            run_dir = temp_dir / 'run-from-outside-repo'
            source_dir = temp_dir / 'source'
            run_dir.mkdir()
            _ = shutil.copytree(
                REPO_ROOT,
                source_dir,
                ignore=shutil.ignore_patterns(
                    '.git',
                    '.sisyphus',
                    '.venv',
                    '__pycache__',
                    '.pytest_cache',
                    '.ruff_cache',
                    'build',
                    'cache',
                    'config.json',
                    'config.jsonc',
                    'demos',
                    'dist',
                    'env',
                    'private',
                    'vendor',
                    'venv',
                    'wheelhouse',
                    '*.egg-info',
                    '*.whl',
                ),
            )

            # Install from the source copy with the same user-facing path as
            # `pip install .`, while keeping package index access disabled.
            venv.EnvBuilder(with_pip=True, system_site_packages=True).create(install_venv)
            install_python = _venv_python(install_venv)

            _ = self.run_command(
                [
                    str(install_python),
                    '-m',
                    'pip',
                    '--isolated',
                    'install',
                    '--no-index',
                    '--no-build-isolation',
                    '--no-deps',
                    str(source_dir),
                ],
                cwd=run_dir,
                env=env,
            )

            probe_code = textwrap.dedent(
                f'''
                import importlib.metadata
                import importlib.resources
                import hashlib
                import json
                from pathlib import Path

                import {IMPORT_NAME}

                package_root = importlib.resources.files('{IMPORT_NAME}')
                bridge = package_root.joinpath('bin', 'pvp_alive_bridge.exe')
                excluded_cpp = package_root.joinpath('bin', 'pvp_alive_bridge.cpp')
                vendored_signer_dir = package_root.joinpath('_vendor', 'cs_demo_pwa_signer')
                manifest = json.loads(vendored_signer_dir.joinpath('manifest.json').read_text(encoding='utf-8'))
                entries = manifest.get('entries', [])
                materialized_entries = []
                for entry in entries:
                    path = vendored_signer_dir.joinpath(entry['directory'], entry['extension'])
                    materialized_entries.append({{
                        'directory': entry['directory'],
                        'exists': path.is_file(),
                        'extension': entry['extension'],
                        'platform_tag': entry['platform_tag'],
                        'python_tag': entry['python_tag'],
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
                    }})

                print(json.dumps({{
                    'bridge_exists': bridge.is_file(),
                    'cpp_exists': excluded_cpp.is_file(),
                    'manifest_entry_count': len(entries),
                    'materialized_entries': materialized_entries,
                    'package_file': str(Path({IMPORT_NAME}.__file__).resolve()),
                    'requirements': importlib.metadata.requires('{DIST_NAME}') or [],
                    'version': importlib.metadata.version('{DIST_NAME}'),
                }}))
                '''
            )
            probe = self.run_command(
                [str(install_python), '-c', probe_code],
                cwd=run_dir,
                env=env,
            )
            try:
                metadata = cast(dict[str, object], json.loads(probe.stdout))
            except JSONDecodeError:
                self.fail(f'installed package probe did not return JSON: {probe.stdout!r}')
            package_file_value = metadata['package_file']
            self.assertIsInstance(package_file_value, str)
            package_file = Path(cast(str, package_file_value))

            self.assertEqual('1.3.0', metadata['version'])
            self.assertTrue(metadata['bridge_exists'])
            self.assertFalse(metadata['cpp_exists'])
            manifest_entry_count_value = metadata['manifest_entry_count']
            self.assertIsInstance(manifest_entry_count_value, int)
            manifest_entry_count = cast(int, manifest_entry_count_value)
            self.assertGreaterEqual(manifest_entry_count, 1)
            materialized_entries_value = metadata['materialized_entries']
            self.assertIsInstance(materialized_entries_value, list)
            materialized_entries = cast(list[object], materialized_entries_value)
            self.assertTrue(materialized_entries)
            matching_entries: list[dict[str, object]] = []
            for entry_value in materialized_entries:
                if not isinstance(entry_value, dict):
                    continue
                entry = cast(dict[str, object], entry_value)
                if (
                    entry['python_tag'] == 'cp312'
                    and entry['platform_tag'] in {'linux_x86_64', 'manylinux_2_28_x86_64'}
                    and entry['extension'] == 'cs_demo_pwa_signer.cpython-312-x86_64-linux-gnu.so'
                ):
                    matching_entries.append(entry)
            self.assertTrue(matching_entries)
            first_entry = matching_entries[0]
            self.assertTrue(first_entry['exists'])
            sha256_value_obj = first_entry['sha256']
            self.assertIsInstance(sha256_value_obj, str)
            sha256_value = cast(str, sha256_value_obj)
            self.assertEqual(64, len(sha256_value))
            requirements_value = metadata['requirements']
            self.assertIsInstance(requirements_value, list)
            requirements = cast(list[object], requirements_value)
            self.assertTrue(any(str(requirement).startswith('requests') for requirement in requirements))
            self.assertTrue(_is_relative_to(package_file, install_venv))
            self.assertFalse(_is_relative_to(package_file, REPO_ROOT))
            self.assertFalse(_is_relative_to(package_file, REPO_ROOT / 'src'))

            module_help = self.run_command(
                [str(install_python), '-m', IMPORT_NAME, '--help'],
                cwd=run_dir,
                env=env,
            )
            self.assertIn('usage:', module_help.stdout)

            console_script = _venv_console_script(install_venv)
            self.assertTrue(console_script.is_file(), f'missing console script: {console_script}')
            script_help = self.run_command(
                [str(console_script), '--help'],
                cwd=run_dir,
                env=env,
            )
            self.assertIn('usage:', script_help.stdout)

            if _supports_bundled_signer():
                signer_probe_code = textwrap.dedent(
                    f'''
                    import importlib.resources
                    import json
                    from pathlib import Path

                    from {IMPORT_NAME}.core.downloader_pwa import _load_compiled_signer

                    package_root = importlib.resources.files('{IMPORT_NAME}')
                    signer = _load_compiled_signer()
                    signer_path = Path(signer.__file__).resolve()
                    print(json.dumps({{
                        'has_build_x_pwa_signature': hasattr(signer, 'build_x_pwa_signature'),
                        'has_sign_demo_request': hasattr(signer, 'sign_demo_request'),
                        'package_root': str(Path(str(package_root)).resolve()),
                        'signer_path': str(signer_path),
                    }}))
                    '''
                )
                signer_probe = self.run_command(
                    [str(install_python), '-c', signer_probe_code],
                    cwd=run_dir,
                    env=env,
                )
                signer_metadata = cast(dict[str, object], json.loads(signer_probe.stdout))
                signer_path_value = signer_metadata['signer_path']
                package_root_value = signer_metadata['package_root']
                self.assertIsInstance(signer_path_value, str)
                self.assertIsInstance(package_root_value, str)
                signer_path = Path(cast(str, signer_path_value))
                installed_package_root = Path(cast(str, package_root_value))
                self.assertTrue(signer_metadata['has_build_x_pwa_signature'])
                self.assertTrue(signer_metadata['has_sign_demo_request'])
                self.assertIn('site-packages', signer_path.parts)
                self.assertTrue(_is_relative_to(signer_path, install_venv))
                self.assertTrue(_is_relative_to(signer_path, installed_package_root))
                self.assertFalse(_is_relative_to(signer_path, REPO_ROOT))
                self.assertFalse(_is_relative_to(signer_path, REPO_ROOT / 'src'))
                self.assertTrue({'cp312-cp312-linux_x86_64', 'cp312-cp312-manylinux_2_28_x86_64'} & set(signer_path.parts))


if __name__ == '__main__':
    _ = unittest.main()
