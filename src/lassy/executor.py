"""Fixed-command execution for allowlisted LASSY jobs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from lassy.protocol import JobEnvelope
from lassy.workspaces import WorkspaceRegistry


MAX_OUTPUT_BYTES = 32_000


@dataclass(frozen=True)
class ExecutionResult:
    exit_code: int
    output: str
    truncated: bool


class JobExecutor:
    def __init__(self, registry: WorkspaceRegistry) -> None:
        self.registry = registry
        self.git = _require_executable("git")
        self.uv = _require_executable("uv")
        self.opencode = shutil.which("opencode")

    def execute(self, job: JobEnvelope) -> ExecutionResult:
        if job.kind == "health":
            payload = {
                "runner": "ok",
                "git": self.git,
                "uv": self.uv,
                "opencode_available": self.opencode is not None,
            }
            return ExecutionResult(0, json.dumps(payload, sort_keys=True), False)

        assert job.workspace is not None
        cwd = self.registry.require(job.workspace, job.kind)
        if job.kind == "repo_status":
            return self._run([self.git, "status", "--short", "--branch"], cwd)
        if job.kind == "repo_test":
            return self._run([self.uv, "run", "pytest", "-q"], cwd)
        if job.kind == "repo_lint":
            return self._run([self.uv, "run", "ruff", "check", "."], cwd)
        if job.kind == "opencode_review":
            if self.opencode is None:
                raise RuntimeError("OpenCode is not installed")
            env = {
                **os.environ,
                "OPENCODE_DISABLE_AUTOUPDATE": "true",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true",
                "OPENCODE_PERMISSION": json.dumps(
                    {
                        "*": "deny",
                        "read": "allow",
                        "glob": "allow",
                        "grep": "allow",
                        "list": "allow",
                        "lsp": "allow",
                        "edit": "deny",
                        "bash": "deny",
                        "external_directory": "deny",
                        "webfetch": "deny",
                        "websearch": "deny",
                        "task": "deny",
                    },
                    separators=(",", ":"),
                ),
            }
            return self._run(
                [self.opencode, "run", "--format", "json", "--agent", "plan", job.prompt or ""],
                cwd,
                env=env,
                timeout=900,
            )
        raise ValueError("unsupported job kind")

    def _run(
        self,
        command: list[str],
        cwd: Path,
        *,
        env: dict[str, str] | None = None,
        timeout: int = 600,
    ) -> ExecutionResult:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        combined = completed.stdout + completed.stderr
        encoded = combined.encode("utf-8")
        truncated = len(encoded) > MAX_OUTPUT_BYTES
        if truncated:
            combined = encoded[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
        return ExecutionResult(completed.returncode, combined, truncated)


def _require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"required executable '{name}' is not installed")
    return str(Path(executable).resolve())
