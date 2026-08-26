# LASSY Remote Runner

The runner connects the primary PC to a Cloudflare control plane without
opening an inbound port. It polls over HTTPS, verifies a short-lived HMAC-signed
job, maps the requested workspace name through a local registry, executes one
fixed action, writes an append-only audit record, and returns a signed result.

## Job allowlist

| Kind | Effect | Default risk |
|---|---|---|
| `health` | Report runner and required executable availability | Automatic |
| `repo_status` | Read Git branch and working-tree status | Automatic |
| `repo_test` | Run the repository's pinned pytest command through uv | Automatic |
| `repo_lint` | Run the repository's pinned Ruff command through uv | Automatic |
| `opencode_review` | Read-only OpenCode review with shell/edit/network denied | Automatic |

There is deliberately no generic command, arbitrary executable, filesystem
path, model endpoint, browser-control, deployment, or code-edit job.

## Local configuration

Copy `config/workspaces.example.yaml` outside the public checkout. Replace the
placeholder with each exact repository root and grant only the job types that
repository needs. Store the runner secret in the operating-system credential
facility and inject it as `LASSY_RUNNER_SECRET` when the service starts; never
put it in YAML, command history, Git, or a desktop shortcut.

The remaining non-secret settings are:

- `LASSY_CONTROL_URL`: HTTPS base URL of the Cloudflare control Worker.
- `LASSY_RUNNER_ID`: stable opaque identifier such as `bigg-rigg-primary`.
- `--workspace-config`: local registry YAML path.
- `--data-dir`: private directory for audit and recovery state.

`lassy runner-once` performs one poll. `lassy runner` continuously polls and
sleeps when no job is available.

## Recovery and invariants

- Result submission is recoverable: a signed result is written atomically to
  `pending-result.json` before upload and resent before another claim.
- Claimed job IDs are persisted before execution. A replay is rejected even if
  the prior result upload failed.
- Output is capped at 32,000 UTF-8 bytes. Long output is marked truncated.
- Commands use argument arrays with `shell=False`; no command text comes from
  the control plane.
- Removing the local service or runner secret immediately stops remote work.

## MCP inventory decision

Do not install every third-party MCP server behind the gateway. Wonderland
Gateway already supplies knowledge-graph memory and sequential thinking, and
Cloudflare supplies the authenticated aggregation/control layer. A filesystem
MCP would duplicate the runner boundary and increase the impact of prompt
injection. The first optional additions to evaluate later are Serena for
read-only symbolic code navigation and SafeDep or Semgrep as local CI gates.
They should run inside an isolated job workspace and return bounded results,
not become broadly exposed gateway tools.
