# Security Policy

## Reporting a vulnerability

Report security issues privately to the repository owner. **Do not open a
public GitHub issue for a vulnerability.** Until a dedicated security contact
address is published, use GitHub's private vulnerability reporting
(`Security` → `Report a vulnerability`) or contact the owner directly.

Include a description of the issue, affected versions, reproduction steps, and
any redacted evidence. Do not include live secrets, access tokens, or private
machine reports in your report.

## Trust boundaries

### Ollama loopback binding

Ollama binds to `127.0.0.1` (loopback) on every supported profile. Raw Ollama
port `11434` is **never** exposed to the LAN or the public internet.

Remote clients reach the primary GPU host only through an authenticated
gateway (LiteLLM, added after the local-only path passes). Clients never
connect to a raw LAN-exposed Ollama port.

### Workspace isolation

Every agent receives explicit workspace roots. Home-directory-wide write
access is prohibited by default. Browser automation uses a dedicated profile,
not the everyday Chrome profile, and supports allowed-domain restrictions.
Cline interactive mode requires approvals; headless mode uses a separate
configuration directory and an explicit command allow/deny policy.

### Subprocess safety

All subprocesses use argument arrays with `shell=False` and fixed executable
paths. Shell-string concatenation is prohibited. Executable identity is
verified before a recorded PID is terminated.

### Audit records

Every side-effecting task produces an audit record containing timestamp, host
ID, workspace, agent, model alias, requested action, result, and verification
status. Prompt content may be redacted.

### No generic desktop control

Destructive file operations, credential access, application control, and
arbitrary commands are not exposed through a generic desktop endpoint. No
unrestricted desktop-control API or FastAPI router exists in Release 1.

## Secrets

- Secrets never enter Git. Repository files contain only environment-variable
  names and `.example` templates.
- Host secrets are stored in the operating system's secure credential facility
  or entered at runtime.
- The public repository must never contain secrets, private machine reports,
  model weights, browser profiles, conversation databases, or screenshots
  containing private data.

## Update and repair safety

- `lassy repair --safe` touches only LASSY-owned reversible state. Installing
  or upgrading external applications, downloading models, changing
  PATH/startup behavior, terminating unowned processes, modifying
  network/firewall settings, accessing credentials, or deleting caches
  requires explicit approval.
- LASSY never repairs GPU drivers, the operating system, or a personal browser
  profile.
- Update application is opt-in and stable-channel only. A new version becomes
  active only after signature/checksum validation and post-update health
  checks; failure restores the prior healthy version.
