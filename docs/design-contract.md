# LASSY Local Agent Stack — Design Contract

**Status:** Approved direction for detailed implementation planning  
**Date:** 2026-08-25  
**Target repository:** existing public GitHub repository `https://github.com/nousloopsolutions/lassy` (currently empty)

## 1. Objective

Build LASSY: a portable, free-first agent workstation that gives the owner one primary interface for local coding, browser automation, files, terminals, and task execution. The system must run first on the existing Windows 11 RTX 4090 Laptop GPU machine, then install predictably on additional Windows PCs and an Intel i9 MacBook Pro.

LASSY must provide a command-line lifecycle experience suitable for non-expert installation and support:

- `lassy doctor` for read-only dependency, compatibility, hardware, port, and service checks.
- `lassy plan` for an explainable machine-specific installation plan.
- `lassy install` for idempotent user-space installation.
- `lassy repair` for classified, reversible repairs.
- `lassy update` for staged, verified updates.
- `lassy rollback` for returning to the last healthy version.
- `lassy start`, `status`, and `stop` for normal operation.

The first release must prove useful work locally before adding a custom orchestrator. It must favor supported product interfaces—Agent Canvas APIs, MCP, ACP, Cline CLI/SDK, and OpenAI-compatible model endpoints—over bespoke glue.

## 2. Verified Starting Point

- Primary host: Windows 11, NVIDIA GeForce RTX 4090 Laptop GPU, 16,376 MiB VRAM.
- Ollama is installed and running at `http://127.0.0.1:11434`.
- Installed Ollama models include `gpt-oss:20b`, `qwen3-coder:30b`, `qwen2.5-coder:32b`, `hermes3:8b`, `hermes3:3b`, `llava`, and `nomic-embed-text`.
- Browser Use 0.13.8 is installed in an isolated Python 3.12 environment and passed a real Chromium smoke test with `gpt-oss:20b` at 16,384-token context.
- Agent Canvas 1.15.0 is globally installed.
- Kilo Code is installed in VS Code.
- Atomic Chat 2.0.19 is installed; its own local model store is empty.
- Cline and Aider are not installed.
- `C:\Users\hovla\ai-stack` does not exist; no earlier megaplan implementation should be assumed.

## 3. Architectural Decision

### 3.1 Control surface

Agent Canvas is the primary browser-based command surface. It owns conversations, workspace selection, terminals, LLM profiles, MCP connections, automations, and supported ACP agents.

Atomic Chat remains a local chat and model-management interface. It is not the service supervisor for an Ollama-based deployment. Cline and Kilo remain IDE-native specialist interfaces.

### 3.2 Integration contracts

Use integrations in this order:

1. OpenAI-compatible model API.
2. MCP for narrowly scoped tools such as browser automation.
3. ACP for compatible agent processes.
4. Agent Canvas conversation and settings APIs.
5. Cline CLI or SDK for programmatic coding tasks.
6. A custom policy/job service only if the preceding interfaces leave a measured gap.

Do not implement keyword-based routing in the first release.

### 3.3 Execution topology

The system has three deployment profiles:

#### `windows-gpu-host`

- Runs Ollama natively with NVIDIA acceleration.
- Runs Agent Canvas natively for the first release.
- Runs Browser Use with a dedicated automation browser profile.
- Runs Cline CLI/extension and Kilo Code.
- May run LiteLLM after the local-only path passes.
- Accepts remote model requests only through an authenticated gateway on an approved private network.

#### `windows-client`

- Runs Agent Canvas, Cline, Kilo, and optionally Browser Use locally.
- Uses a local Ollama instance when hardware passes the model benchmark.
- Otherwise uses the authenticated gateway on the primary GPU host.
- Never connects to a raw LAN-exposed Ollama port.

#### `macos-intel-client`

- Requires macOS Sonoma 14 or newer.
- Runs Agent Canvas, Cline, and Browser Use natively when their preflight checks pass.
- Uses the authenticated primary-host gateway by default.
- Ollama on x86 macOS is CPU-only; it is limited to small models and diagnostic/offline fallback workloads.
- The profile must not download 20B–32B models automatically.

## 4. Component Roles

| Component | Release role |
|---|---|
| Agent Canvas | Primary command UI and conversation/workspace manager |
| Ollama | Primary local inference runtime on capable hosts |
| Atomic Chat | Human-facing local chat/model UI; optional separate inference source |
| Browser Use | Dedicated browser automation tool exposed through MCP or a narrow adapter |
| Cline | Controlled coding worker; interactive approval mode and separately configured headless mode |
| Kilo Code | Optional interactive IDE worker and free-model access |
| LiteLLM | Stage-two authenticated gateway and logical model alias layer |
| Codex | Explicit high-capability escalation and review tier |
| Devin | Long-running implementation/escalation tier; also builds this repository |
| OpenRouter/Kilo free models | Optional free cloud fallback with explicit disclosure |
| Aider | Deferred until a benchmark shows unique value over the installed coding workers |
| Custom router | Deferred pending a written decision record supported by test evidence |

## 5. Model Policy

Consumers request logical capabilities instead of hard-coding provider model names:

- `local-fast`: classification, summaries, light transformations.
- `local-code`: repository work and tool-heavy coding.
- `local-browser`: structured browser actions.
- `local-vision`: screenshot understanding.
- `cloud-free`: explicitly permitted free cloud fallback.
- `escalation-code`: Codex or another approved high-capability coding agent.
- `escalation-autonomous`: Devin for long-running work.

Before LiteLLM is introduced, the configuration resolver maps these aliases directly to Ollama model IDs. After LiteLLM is introduced, the aliases become authenticated gateway model names without changing clients.

Context length is a per-capability setting. The implementation must not set a global 16K context and call the problem solved. The preflight/benchmark process records requested context, allocated context, CPU/GPU split from `ollama ps`, cold-start time, warm latency, and task success. Agent Canvas requires a larger prompt budget than the already-passing Browser Use smoke test, so model and context must be chosen together.

## 6. Security and Trust Boundaries

- Ollama binds to loopback by default.
- Remote clients connect through LiteLLM or a later gateway with authentication; they never access Ollama directly.
- Remote access is limited to a user-approved private overlay or LAN boundary. Public internet exposure is out of scope.
- Every agent receives explicit workspace roots. Home-directory-wide write access is prohibited by default.
- Browser automation uses a dedicated profile, not the everyday Chrome profile.
- Browser tasks support allowed-domain restrictions.
- Cline interactive mode requires approvals. Headless mode uses a separate configuration directory and explicit command allow/deny policy.
- Secrets never enter Git. Repository files contain only environment-variable names and `.example` templates.
- Host secrets are stored in the operating system’s secure credential facility or entered at runtime.
- Subprocesses use argument arrays and fixed executable paths. Shell-string concatenation is prohibited.
- Every side-effecting task produces an audit record containing timestamp, host ID, workspace, agent, model alias, requested action, result, and verification status. Prompt content may be redacted.
- Destructive file operations, credential access, application control, and arbitrary commands are not exposed through a generic desktop endpoint.

## 7. Repository Boundary

The repository contains portable configuration, launchers, diagnostics, tests, and documentation. It does not contain model weights, browser profiles, secrets, conversation databases, screenshots containing private data, or machine-specific absolute paths.

```text
lassy/
├── README.md
├── SECURITY.md
├── pyproject.toml
├── uv.lock
├── config/
│   ├── stack.schema.json
│   ├── defaults.yaml
│   └── profiles/
│       ├── windows-gpu-host.yaml
│       ├── windows-client.yaml
│       └── macos-intel-client.yaml
├── compatibility/
│   ├── schema.json
│   └── releases/
│       └── v0.1.0.yaml
├── installer/
│   ├── install.ps1
│   └── install.sh
├── src/lassy/
│   ├── __init__.py
│   ├── audit.py
│   ├── cli.py
│   ├── capabilities.py
│   ├── config.py
│   ├── diagnostics.py
│   ├── evidence.py
│   ├── health.py
│   ├── installer.py
│   ├── maintenance.py
│   ├── paths.py
│   ├── planner.py
│   ├── repair.py
│   ├── release.py
│   ├── reports.py
│   ├── state.py
│   ├── subprocesses.py
│   ├── update.py
│   └── verify.py
├── integrations/
│   ├── agent-canvas/
│   ├── browser-use/
│   ├── cline/
│   └── litellm/
├── scripts/
│   ├── bootstrap-windows.ps1
│   ├── launch-windows.ps1
│   ├── stop-windows.ps1
│   ├── bootstrap-macos.sh
│   ├── launch-macos.sh
│   └── stop-macos.sh
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── smoke/
├── docs/
│   ├── architecture.md
│   ├── security-model.md
│   ├── model-benchmark.md
│   ├── operations.md
│   ├── devin-environment.md
│   └── adr/
└── .github/workflows/
    ├── ci.yml
    ├── intel-mac.yml
    └── release.yml
```

Runtime data uses platform-native user-data directories and is gitignored.

The public repository must never contain secrets or private machine reports. Public visibility does not decide licensing: Devin must not add or change a license until the repository owner explicitly approves one.

## 8. Operational Contract

The repository exposes one host CLI:

```text
lassy doctor --profile auto --json
lassy plan --profile auto
lassy install --profile auto --dry-run
lassy install --profile <profile>
lassy configure --profile <profile>
lassy health --json
lassy benchmark --capability <alias>
lassy verify --suite local
lassy repair --check
lassy repair --safe
lassy update --check
lassy update --apply
lassy rollback
lassy report --output <path>
```

Bootstrap scripts install pinned prerequisites and then call the Python CLI. Launch scripts start only the services enabled by the selected profile, wait for health checks, print URLs without secrets, and write PID/state data under the user-data directory. Stop scripts terminate only processes whose PID and executable identity match recorded state.

Installation is user-space and versioned. Each LASSY release has its own managed environment under the platform data directory; a small shim selects the active version. Updates stage a new version beside the current version, verify its signed compatibility manifest, run health checks, and switch the active pointer only after success. The last healthy version remains available for rollback.

`lassy repair --safe` may regenerate derived LASSY configuration, rebuild a LASSY-owned environment from a pinned manifest, clear stale LASSY PID records, restart LASSY-owned processes, and restore the last healthy active-version pointer. Installing or upgrading external applications, downloading models, changing PATH/startup behavior, terminating unowned processes, modifying network/firewall settings, accessing credentials, or deleting caches requires explicit approval. LASSY never repairs GPU drivers, the operating system, or a personal browser profile.

Update checks are allowed by default and transmit only the installed LASSY version and release channel to GitHub. Automatic application of updates is opt-in, stable-channel only, and disabled until release-manifest signing is configured. Failed post-update health checks trigger automatic rollback.

## 9. Release Sequence

1. Repository foundation and configuration contracts.
2. Cross-platform preflight and machine report.
3. Windows GPU-host bootstrap and local-only Agent Canvas/Ollama path.
4. Browser Use MCP integration and end-to-end local task.
5. Cline interactive and headless profiles.
6. Verification suite and Windows CI.
7. Intel Mac client bootstrap and manual/GitHub Intel validation.
8. Authenticated LiteLLM gateway and Windows client profile.
9. Signed release bundle and installation guide.
10. Capability resolver, versioned installer, classified repair engine, and signed staged updater.
11. Evidence-based decision on whether a custom job/policy service is justified.

## 10. Definition of Done

Release 1 is complete when:

- A clean Windows 11 machine can run the bootstrap, configure a profile, launch enabled services, and produce a passing machine-readable verification report.
- Agent Canvas can use an approved Ollama model and complete a file task in an isolated workspace.
- Agent Canvas or Cline can invoke Browser Use against an allowed test domain and save a result artifact.
- Cline works interactively with approval and separately in a restricted headless test workspace.
- A second Windows client can use the authenticated primary-host model gateway without raw Ollama exposure.
- The Intel i9 Mac can install the client profile, run Agent Canvas/Cline/Browser Use checks, and use the primary gateway.
- Local-only mode makes no cloud model calls.
- Cloud fallback requires an explicit profile setting and is visible in the audit report.
- CI passes on Ubuntu and Windows; the Intel macOS workflow passes manually or on its scheduled release gate.
- Installation, upgrade, rollback, troubleshooting, and uninstall instructions are verified on physical machines.
- A clean supported machine can run the bootstrap installer, receive an explainable profile recommendation, and preview every planned mutation before approval.
- `lassy doctor` distinguishes required, optional, incompatible, and degraded dependencies and returns stable machine-readable exit codes.
- `lassy repair --safe` repairs only LASSY-owned reversible state; approval-required actions are listed but not executed.
- A staged update either passes health checks and becomes active or rolls back to the prior healthy version.
- No custom keyword router or unrestricted desktop-control API has been added.

## 11. References Used for This Contract

- Devin environment configuration: https://docs.devin.ai/onboard-devin/environment
- Devin declarative blueprints: https://docs.devin.ai/onboard-devin/environment/blueprints
- Agent Canvas overview: https://github.com/OpenHands/docs/blob/main/openhands/usage/agent-canvas/overview.mdx
- OpenHands local-model guidance: https://github.com/OpenHands/docs/blob/main/openhands/usage/llms/local-llms.mdx
- Cline CLI: https://github.com/cline/cline/blob/main/apps/cli/README.md
- Cline configuration: https://docs.cline.bot/getting-started/config
- Browser Use CLI: https://github.com/browser-use/browser-use/blob/main/browser_use/skill_cli/README.md
- Ollama macOS requirements: https://docs.ollama.com/macos
- Ollama context guidance: https://docs.ollama.com/context-length
- GitHub runner images: https://github.com/actions/runner-images

