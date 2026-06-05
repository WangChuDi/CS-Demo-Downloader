# Private PWA signer wheel

`cs-demo-downloader` does not contain the PWA signing algorithm. PWA URL and header signing are delegated to the proprietary `cs-demo-pwa-signer` wheel, which must be built and distributed outside this public repository.

## Required public API

The wheel must install an importable module named `cs_demo_pwa_signer` with these functions:

```python
def sign_demo_request(randnum: str, timestamp: str, data: str) -> str: ...
def build_x_pwa_signature(steamid: str, timestamp: int, ip_addr: str) -> str: ...
```

## Build and release rules

- Keep the signer source in a private repository or another private location outside this repository.
- Publish wheels only. Do not publish an sdist.
- Inspect every wheel before release. It may contain compiled artifacts such as `.so`, `.pyd`, or `.dylib` and normal `.dist-info` metadata only.
- The wheel must not contain `.py`, `.pyx`, `.c`, `.cpp`, `.h`, `.rs`, or generated Cython/Nuitka source files that reveal the algorithm.
- Build one wheel per Python ABI, operating system, and CPU architecture that you want to support.

## GitHub Actions build

This repository includes `.github/workflows/build-private-signer-wheels.yml` for building private wheels on GitHub-hosted Linux, Windows, and macOS runners.

Configure these repository secrets before running it:

| Secret | Value |
| --- | --- |
| `PWA_SIGNER_REPOSITORY` | Private signer repository, for example `WangChuDi/cs-demo-pwa-signer-private`. |
| `PWA_SIGNER_REPOSITORY_TOKEN` | Fine-grained PAT or GitHub App token with read access to that private repository. |

The private signer repository should be a normal buildable Python extension project with its own `pyproject.toml`. It may use Cython, Nuitka, Rust/PyO3, or another compiled-extension backend, but it must produce an importable `cs_demo_pwa_signer` module.

Run the workflow manually from GitHub Actions:

1. Open **Actions**.
2. Select **Build Private PWA Signer Wheels**.
3. Click **Run workflow**.
4. Set `signer_ref` to the private signer branch, tag, or commit to build.
5. Set `upload_release` to `true` only when running from a tag and you want the wheels attached to that release.

The workflow builds:

- Linux x86_64 and aarch64 wheels.
- Windows x64 wheels.
- macOS Intel and Apple Silicon wheels.
- CPython 3.9, 3.10, 3.11, and 3.12 wheels.

Every built wheel is smoke-tested by importing `cs_demo_pwa_signer` and checking that both required functions exist. Then `scripts/verify_private_signer_wheel.py` rejects any wheel containing source-like files. Passing wheels are uploaded as GitHub Actions artifacts named `cs-demo-pwa-signer-wheels-*`.

`docker-publish.yml` also builds Linux signer wheels before Docker image builds. For automatic tag/release Docker builds, tag the private signer repository with the same tag as this public repository, or run the Docker workflow manually and set `signer_ref` to the desired private signer ref.

## Supported wheel matrix

The public package supports Python 3.9 and newer, but compiled extension wheels are ABI-specific. Build these signer wheels for each release target you support:

| Target | Python 3.9 | Python 3.10 | Python 3.11 | Python 3.12 |
| --- | --- | --- | --- | --- |
| Windows x64 | `cp39-cp39-win_amd64` | `cp310-cp310-win_amd64` | `cp311-cp311-win_amd64` | `cp312-cp312-win_amd64` |
| Linux x86_64 | `cp39-cp39-manylinux_*_x86_64` | `cp310-cp310-manylinux_*_x86_64` | `cp311-cp311-manylinux_*_x86_64` | `cp312-cp312-manylinux_*_x86_64` |
| Linux arm64 | `cp39-cp39-manylinux_*_aarch64` | `cp310-cp310-manylinux_*_aarch64` | `cp311-cp311-manylinux_*_aarch64` | `cp312-cp312-manylinux_*_aarch64` |
| macOS Intel | `cp39-cp39-macosx_*_x86_64` | `cp310-cp310-macosx_*_x86_64` | `cp311-cp311-macosx_*_x86_64` | `cp312-cp312-macosx_*_x86_64` |
| macOS Apple Silicon | `cp39-cp39-macosx_*_arm64` | `cp310-cp310-macosx_*_arm64` | `cp311-cp311-macosx_*_arm64` | `cp312-cp312-macosx_*_arm64` |

Example filenames:

```text
cs_demo_pwa_signer-0.1.0-cp312-cp312-win_amd64.whl
cs_demo_pwa_signer-0.1.0-cp312-cp312-manylinux_2_28_x86_64.whl
cs_demo_pwa_signer-0.1.0-cp312-cp312-manylinux_2_28_aarch64.whl
cs_demo_pwa_signer-0.1.0-cp312-cp312-macosx_11_0_arm64.whl
```

Prefer `manylinux` tags for Linux release wheels. Plain `linux_x86_64` wheels are acceptable for local/private deployment only when the target distribution matches the build environment.

Example inspection command:

```bash
python -m zipfile --list wheelhouse/cs_demo_pwa_signer-0.1.0-*.whl
python scripts/verify_private_signer_wheel.py wheelhouse/cs_demo_pwa_signer-0.1.0-*.whl
python scripts/select_private_signer_wheel.py wheelhouse
```

`select_private_signer_wheel.py` checks the current interpreter tag, OS, and CPU architecture, then prints the one compatible wheel path. It fails if no matching wheel or multiple matching wheels are present.

## Local installation

Place the private wheel under `wheelhouse/`, then install it before installing or running the downloader:

```bash
pip install "$(python scripts/select_private_signer_wheel.py wheelhouse)"
pip install -e .
```

On Windows PowerShell:

```powershell
$wheel = python scripts/select_private_signer_wheel.py wheelhouse
pip install $wheel
pip install -e .
```

Public tests mock the signer boundary and do not require the private wheel. Actual PWA signing and PWA downloads require the wheel at runtime.

## Docker builds

For local Docker builds, put the private wheel in `wheelhouse/` before running `docker build`:

```bash
docker build --build-arg PYTHON_VERSION=3.12 -t cs-demo-downloader .
docker build --build-arg PYTHON_VERSION=3.12 -f Dockerfile.wine -t cs-demo-downloader:wine .
```

Use a wheel matching the target Python ABI, OS, and CPU architecture. Docker builds run `scripts/select_private_signer_wheel.py` inside the image and install exactly the compatible wheel for that `PYTHON_VERSION` and image platform.

For Linux `amd64` and `arm64` builds, include both matching Linux wheels in `wheelhouse/` before invoking `docker buildx`:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --build-arg PYTHON_VERSION=3.12 \
  -t cs-demo-downloader .
```

For CI/release Docker builds, fetch the wheel from a private package index or private artifact store before building, or replace the wheelhouse install step with an authenticated `pip install cs-demo-pwa-signer==0.1.0` that uses build secrets.
