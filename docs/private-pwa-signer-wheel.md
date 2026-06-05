# Private PWA signer wheel

`cs-demo-downloader` does not contain the PWA signing algorithm source. PWA URL and header signing are delegated to proprietary compiled `cs-demo-pwa-signer` artifacts. This public repository may carry audited compiled fallback artifacts, but the signer source and any source distributions must remain outside this repository.

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
- If a compiled artifact is vendored into this public repository, extract only the compiled extension payload needed by `cs-demo-downloader`; do not vendor source-like files or an sdist.

## GitHub Actions build

This repository includes `.github/workflows/build-private-signer-wheels.yml` for building private wheels on GitHub-hosted Linux, Windows, and macOS runners, then syncing the audited wheelhouse plus bundled compiled signer matrix back into this public repository.

Configure these repository secrets before running it:

| Secret | Value |
| --- | --- |
| `PWA_SIGNER_REPOSITORY` | Private signer repository in `OWNER/REPO` format. |
| `PWA_SIGNER_REPOSITORY_TOKEN` | Fine-grained PAT or GitHub App token with read access to that private repository. |

When this workflow runs in the public downloader repository, no extra secret is required to update that same repository. The built-in `GITHUB_TOKEN` can upload Actions artifacts, optionally attach wheels to a tag release, commit refreshed wheel artifacts directly to the default branch, or open a pull request containing the bundled fallback binary.

The private signer repository should be a normal buildable Python extension project with its own `pyproject.toml`. It may use Cython, Nuitka, Rust/PyO3, or another compiled-extension backend, but it must produce an importable `cs_demo_pwa_signer` module.

Run the workflow manually from GitHub Actions:

1. Open **Actions**.
2. Select **Build Private PWA Signer Wheels**.
3. Click **Run workflow**.
4. Set `signer_ref` to the private signer branch, tag, or commit to build.
5. Set `upload_release` to `true` only when running from a tag and you want the wheels attached to that release.
6. Set `sync_public_repo` to `true` when you want the workflow to update `wheelhouse/` and the bundled signer fallback matrix under `src/cs_demo_downloader/_vendor/cs_demo_pwa_signer/`. Manual runs default to `sync_mode=pull-request`; choose `sync_mode=commit` only when direct default-branch updates are allowed.

You can also trigger the same workflow automatically from the private signer repository with `repository_dispatch` using event type `pwa-signer-updated`. Keep the workflow file on this public repository's default branch, and send only a small payload containing the signer ref plus optional booleans. For `repository_dispatch`, `sync_public_repo` defaults to `true` and `sync_mode` defaults to `commit`, so successful private builds update the current repository automatically:

```bash
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $PUBLIC_REPO_DISPATCH_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/OWNER/CS-Demo-Downloader/dispatches \
  -d '{
    "event_type": "pwa-signer-updated",
    "client_payload": {
      "signer_ref": "refs/tags/v0.1.0",
      "sync_public_repo": true,
      "sync_mode": "commit",
      "upload_release": false
    }
  }'
```

Recommended private-repository setup:

- Store a dedicated dispatch token in the private repository secrets. Use the minimum access needed to invoke `repository_dispatch` on the public downloader repository. A fine-grained PAT or GitHub App installation token is appropriate.
- Trigger it only after the private repository has produced or approved the signer ref you want to mirror.
- Pass `signer_ref` as a branch, tag, or commit that already exists in the private signer repository.
- Omit `sync_public_repo` to accept the automatic default of `true` for `repository_dispatch` runs.
- Omit `sync_mode` to accept the automatic default of `commit` for `repository_dispatch` runs; set it to `pull-request` if the public repository protects the default branch.
- Omit `upload_release` to keep release attachment disabled by default for automatic runs.
- Do not include private source paths, patch contents, or algorithm details in the dispatch payload.

A minimal private-repository workflow can dispatch the exact private commit after pushes or tags:

```yaml
name: Notify Downloader Signer Update

on:
  push:
    branches: [main]
    tags:
      - 'v*'

jobs:
  dispatch:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger downloader artifact sync
        env:
          PUBLIC_REPO_DISPATCH_TOKEN: ${{ secrets.PUBLIC_REPO_DISPATCH_TOKEN }}
          SIGNER_REF: ${{ github.sha }}
          SOURCE_REF: ${{ github.ref }}
          SOURCE_RUN: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: |
          python - <<'PY'
          import json
          import os

          payload = {
              'event_type': 'pwa-signer-updated',
              'client_payload': {
                  'signer_ref': os.environ['SIGNER_REF'],
                  'source_ref': os.environ['SOURCE_REF'],
                  'source_run': os.environ['SOURCE_RUN'],
                  'sync_public_repo': True,
                  'sync_mode': 'commit',
              },
          }
          with open('dispatch-payload.json', 'w', encoding='utf-8') as payload_file:
              json.dump(payload, payload_file)
          PY

          curl -L \
            -X POST \
            -H "Accept: application/vnd.github+json" \
            -H "Authorization: Bearer ${PUBLIC_REPO_DISPATCH_TOKEN}" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            https://api.github.com/repos/OWNER/CS-Demo-Downloader/dispatches \
            --data @dispatch-payload.json
```

The workflow builds:

- Linux x86_64 and aarch64 wheels.
- Windows x64 wheels.
- macOS Intel and Apple Silicon wheels.
- CPython 3.9, 3.10, 3.11, and 3.12 wheels.

Every built wheel is smoke-tested by importing `cs_demo_pwa_signer` and checking that both required functions exist. Then `scripts/verify_private_signer_wheel.py` rejects any wheel containing source-like files. Passing wheels are uploaded as GitHub Actions artifacts named `cs-demo-pwa-signer-wheels-*`.

When `sync_public_repo` is enabled, the workflow also downloads those wheel artifacts, copies them into `wheelhouse/`, extracts one compiled extension payload from each wheel into a tag-named vendored directory, and writes `_vendor/cs_demo_pwa_signer/manifest.json`. `sync_mode=commit` commits only `wheelhouse/` plus `src/cs_demo_downloader/_vendor/cs_demo_pwa_signer/` back to the current repository, which makes the next `pip install git+https://github.com/WangChuDi/CS-Demo-Downloader.git` include the refreshed bundled signer without a separate private wheel install. `sync_mode=pull-request` keeps the old reviewable path and records the source event, source ref, source run, requested signer ref, resolved private signer SHA, and public workflow run for provenance.

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

When the current runtime is covered by the synchronized bundled signer matrix, `cs-demo-downloader` can load the extracted compiled fallback automatically and the normal user flow stays a single install command such as `pip install git+https://github.com/WangChuDi/CS-Demo-Downloader.git` or `pip install .`. No separate `cs-demo-pwa-signer` install is required on those supported bundled runtimes.

Maintainers doing local validation on an uncovered runtime can still use the private wheel fallback. Place the matching private wheel under `wheelhouse/`, then install it before installing or running the downloader:

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

Public tests mock the signer boundary and verify that installed packages carry a bundled signer manifest plus matching vendored binaries on compatible runners. Actual PWA signing and PWA downloads require either the bundled fallback matrix to match the runtime or, for maintainer-only fallback scenarios, a separately installed matching wheel.

## Docker builds

For local Docker builds, use the synchronized `wheelhouse/` committed by the artifact-sync workflow when it covers your target image. Maintainers building an uncovered target can place the matching private wheel in `wheelhouse/` before running `docker build`:

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

For CI/release Docker builds, prefer the synchronized bundled signer matrix when it covers the target image. For maintainer-only fallback builds on uncovered targets, fetch the wheel from a private package index or private artifact store before building.
