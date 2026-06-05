import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Protocol, cast


class _SyncPrivateSignerArtifacts(Protocol):
    def __call__(self, repo: Path, source_wheelhouse: Path, expected_count: int | None = None) -> None:
        ...


def _load_sync_private_signer_artifacts() -> _SyncPrivateSignerArtifacts:
    module_path = Path(__file__).resolve().parents[1] / 'scripts' / 'sync_private_signer_artifacts.py'
    spec = importlib.util.spec_from_file_location('sync_private_signer_artifacts_module', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load sync module from {module_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_SyncPrivateSignerArtifacts, getattr(module, 'sync_private_signer_artifacts'))


sync_private_signer_artifacts = _load_sync_private_signer_artifacts()


def _write_wheel(path: Path, extension_name: str, extension_bytes: bytes, extra_name: str | None = None, extra_bytes: bytes = b''):
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(extension_name, extension_bytes)
        archive.writestr('cs_demo_pwa_signer-0.1.0.dist-info/METADATA', 'Metadata-Version: 2.1\nName: cs_demo_pwa_signer\nVersion: 0.1.0\n')
        archive.writestr('cs_demo_pwa_signer-0.1.0.dist-info/WHEEL', 'Wheel-Version: 1.0\nTag: cp312-cp312-linux_x86_64\n')
        archive.writestr('cs_demo_pwa_signer-0.1.0.dist-info/RECORD', '')
        if extra_name is not None:
            archive.writestr(extra_name, extra_bytes)


class PrivateSignerSyncTests(unittest.TestCase):
    def test_sync_private_signer_artifacts_extracts_manifest_entry(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            repo = temp_dir / 'repo'
            wheelhouse = temp_dir / 'wheelhouse'
            vendor_dir = repo / 'src' / 'cs_demo_downloader' / '_vendor' / 'cs_demo_pwa_signer'
            wheelhouse.mkdir(parents=True)
            vendor_dir.mkdir(parents=True)

            wheel_path = wheelhouse / 'cs_demo_pwa_signer-0.1.0-cp312-cp312-linux_x86_64.whl'
            _write_wheel(wheel_path, 'cs_demo_pwa_signer.cpython-312-x86_64-linux-gnu.so', b'binary-extension')

            sync_private_signer_artifacts(repo, wheelhouse, expected_count=1)

            manifest_path = vendor_dir / 'manifest.json'
            self.assertTrue(manifest_path.is_file())
            manifest_text = manifest_path.read_text(encoding='utf-8')
            self.assertIn('cp312', manifest_text)
            self.assertTrue((vendor_dir / 'cp312-cp312-linux_x86_64' / 'cs_demo_pwa_signer.cpython-312-x86_64-linux-gnu.so').is_file())

    def test_sync_private_signer_artifacts_rejects_source_like_files(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            repo = temp_dir / 'repo'
            wheelhouse = temp_dir / 'wheelhouse'
            wheelhouse.mkdir(parents=True)
            (repo / 'src' / 'cs_demo_downloader' / '_vendor' / 'cs_demo_pwa_signer').mkdir(parents=True)

            wheel_path = wheelhouse / 'cs_demo_pwa_signer-0.1.0-cp312-cp312-linux_x86_64.whl'
            _write_wheel(wheel_path, 'cs_demo_pwa_signer.cpython-312-x86_64-linux-gnu.so', b'binary-extension', extra_name='cs_demo_pwa_signer.py', extra_bytes=b'print(1)')

            with self.assertRaises(RuntimeError) as ctx:
                sync_private_signer_artifacts(repo, wheelhouse, expected_count=1)

            self.assertIn('source-like file included', str(ctx.exception))


if __name__ == '__main__':
    _ = unittest.main()
