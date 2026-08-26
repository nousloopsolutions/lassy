from pathlib import Path

import pytest

from lassy.workspaces import WorkspaceRegistry


def test_registry_rejects_unlisted_job(tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    config = tmp_path / "workspaces.yaml"
    config.write_text(
        f"workspaces:\n  demo:\n    path: '{workspace.as_posix()}'\n"
        "    allowed_jobs: [repo_status]\n",
        encoding="utf-8",
    )
    registry = WorkspaceRegistry.load(config)
    assert registry.require("demo", "repo_status") == workspace.resolve()
    with pytest.raises(ValueError, match="not allowed"):
        registry.require("demo", "repo_test")


def test_registry_rejects_remote_path_choice(tmp_path: Path) -> None:
    config = tmp_path / "workspaces.yaml"
    config.write_text("workspaces: {}\n", encoding="utf-8")
    registry = WorkspaceRegistry.load(config)
    with pytest.raises(ValueError, match="not registered"):
        registry.require("attacker-choice", "repo_status")
