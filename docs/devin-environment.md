# Devin Environment

Devin builds this repository from a **Linux** sandbox environment. It cannot
certify native Windows, NVIDIA GPU, browser-profile, or Intel macOS behavior.
Hardware-dependent and platform-native behavior is verified separately on
physical machines and reported through redacted JSON evidence; those reports
are never committed to this repository.

## Blueprint

Paste the blueprint below into **Devin Settings → Environment → Blueprints**
so Devin's sandbox matches the repository toolchain.

```yaml
initialize:
  - name: Install Python 3.12
    uses: github.com/actions/setup-python@v5
    with:
      python-version: "3.12"
  - name: Install Node.js 22
    uses: github.com/actions/setup-node@v4
    with:
      node-version: "22"
  - name: Install uv and shellcheck
    run: |
      curl -LsSf https://astral.sh/uv/install.sh | sh
      sudo apt-get update -qq
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq shellcheck
maintenance:
  - name: Sync repository dependencies
    run: uv sync --all-extras --dev
knowledge:
  - name: lint
    contents: uv run ruff check .
  - name: unit tests
    contents: uv run pytest tests/unit -q
  - name: full tests
    contents: uv run pytest -q
  - name: architecture
    contents: Read docs/design-contract.md before changing interfaces or dependencies.
```

## What this environment can and cannot verify

| Capability | Verified in Devin Linux sandbox? |
|---|---|
| Python package build, lint, unit tests | Yes |
| Configuration parsing and profile resolution | Yes |
| Fake-server integration contracts | Yes |
| Native Windows bootstrap/launch/stop | No — requires a physical Windows host |
| NVIDIA GPU detection and VRAM reporting | No — requires the physical GPU host |
| Browser Use against a real browser profile | No — requires a physical machine |
| Intel macOS bootstrap and gateway client | No — requires the physical Intel Mac |

Physical-machine smoke tests are separate from CI, emit redacted JSON reports,
and are uploaded as private workflow artifacts or attached to a private release
candidate — never committed to the public repository.
