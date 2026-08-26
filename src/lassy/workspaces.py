"""Explicit workspace registry; paths never arrive from remote job payloads."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class Workspace(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    path: Path
    allowed_jobs: frozenset[str] = Field(default_factory=frozenset)


class WorkspaceRegistry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workspaces: dict[str, Workspace]

    @classmethod
    def load(cls, path: Path) -> WorkspaceRegistry:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        registry = cls.model_validate(data)
        resolved: dict[str, Workspace] = {}
        for name, workspace in registry.workspaces.items():
            root = workspace.path.expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError(f"workspace '{name}' is not a directory")
            resolved[name] = workspace.model_copy(update={"path": root})
        return cls(workspaces=resolved)

    def require(self, name: str, kind: str) -> Path:
        workspace = self.workspaces.get(name)
        if workspace is None:
            raise ValueError(f"workspace '{name}' is not registered")
        if kind not in workspace.allowed_jobs:
            raise ValueError(f"job kind '{kind}' is not allowed for workspace '{name}'")
        return workspace.path
