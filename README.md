# LASSY — Local Agent Stack

LASSY is a portable, free-first agent workstation that gives the owner one
command-line lifecycle interface for local coding, browser automation, files,
terminals, and task execution. It configures, launches, diagnoses, repairs,
updates, rolls back, and verifies the approved local-first agent stack.

## Release stage

**Pre-release / restricted runner.** The repository now contains the
configuration foundation and an outbound-only remote runner for signed,
allowlisted jobs. It is not a general remote shell and is not yet a complete
installer or service lifecycle. See
[`docs/design-contract.md`](docs/design-contract.md) for the full design and
the release sequence.

## Supported profiles

Release 1 targets three deployment profiles:

| Profile | Target host | Inference |
|---|---|---|
| `windows-gpu-host` | Windows 11 with a supported NVIDIA GPU (the primary host currently has an RTX 4090) | Local Ollama with NVIDIA acceleration |
| `windows-client` | Additional Windows PCs | Authenticated gateway to the GPU host; local Ollama optional |
| `macos-intel-client` | Intel i9 MacBook Pro, macOS Sonoma 14+ | Authenticated gateway by default; local Ollama CPU-only diagnostic fallback |

Ollama binds to loopback on every profile. Remote clients reach the primary
GPU host only through an authenticated gateway; raw Ollama port `11434` is
never exposed to the LAN or public internet.

## Non-goals (Release 1)

- No custom keyword router or unrestricted second chat UI. OpenCode and
  Wonderland Gateway are the initial command surfaces.
- No unrestricted desktop-control API, generic command endpoint, or FastAPI
  service.
- No automatic GPU driver installation, firewall changes, or large model
  downloads.
- No committed secrets, model weights, browser profiles, conversation stores,
  screenshots, or machine-specific absolute paths.
- No license is added until the repository owner explicitly chooses one.

## Tech stack

Python 3.12, [uv](https://docs.astral.sh/uv/), Pydantic 2, PyYAML, httpx,
pytest, Ruff, PowerShell 7, Bash, Node.js 22+, OpenCode, Ollama,
Browser Use, optional Cline, and GitHub Actions.

## Developer commands

```bash
# Install dependencies (pinned, with dev extras)
uv sync --all-extras --dev

# Lint
uv run ruff check .

# Run the full test suite
uv run pytest -q

# Run unit tests only
uv run pytest tests/unit -q
```

Dependencies are pinned and `uv.lock` is committed. Use `uv sync --locked` in
CI to reject drift.

## Documentation

- [Design contract](docs/design-contract.md) — approved architecture, security
  boundaries, repository layout, and definition of done.
- [Devin environment](docs/devin-environment.md) — Linux blueprint used by the
  agent that builds this repository.
- [Remote runner](docs/remote-runner.md) — signed job protocol, allowlist,
  recovery behavior, and operating instructions.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). One task per pull request, tests
before review, no committed host data, and no merge by an agent.
