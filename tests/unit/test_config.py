from pathlib import Path

import pytest

from lassy.config import ResolvedConfig, load_config


# --- Given tests from the plan ---


def test_macos_intel_defaults_to_remote_gateway(repo_root: Path) -> None:
    config = load_config(repo_root, "macos-intel-client", {})
    assert config.inference.mode == "gateway"
    assert config.local_models.auto_pull is False
    assert config.security.ollama_bind == "127.0.0.1"


def test_public_ollama_bind_is_rejected(repo_root: Path) -> None:
    with pytest.raises(ValueError, match="raw Ollama exposure is prohibited"):
        load_config(repo_root, "invalid-public-ollama", {})


# --- Profile behavior tests ---


def test_windows_gpu_host_defaults_to_local(repo_root: Path) -> None:
    config = load_config(repo_root, "windows-gpu-host", {})
    assert config.inference.mode == "local"
    assert config.components.ollama is True
    assert config.components.opencode is True
    assert config.components.browser_use is False
    assert config.components.cline is False
    assert config.components.gateway is False


def test_windows_client_defaults_to_gateway(repo_root: Path) -> None:
    config = load_config(repo_root, "windows-client", {})
    assert config.inference.mode == "gateway"
    assert config.components.ollama is False
    assert config.components.opencode is True
    assert config.components.cline is False
    assert config.components.gateway is True


def test_macos_intel_components(repo_root: Path) -> None:
    config = load_config(repo_root, "macos-intel-client", {})
    assert config.components.opencode is True
    assert config.components.browser_use is False
    assert config.components.cline is False
    assert config.components.ollama is False
    assert config.components.gateway is True


# --- Model alias tests ---


def test_model_aliases_mapped_to_ollama_ids(repo_root: Path) -> None:
    config = load_config(repo_root, "windows-gpu-host", {})
    assert config.models.local_fast == "deepseek-coder:6.7b"
    assert config.models.local_code == "qwen3:30b"
    assert config.models.local_browser == "qwen3:30b"
    assert config.models.local_vision is None


# --- Env override tests ---


def test_env_gateway_url(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-client",
        {"NOUS_STACK_GATEWAY_URL": "http://127.0.0.1:4000"},
    )
    assert config.gateway is not None
    assert config.gateway.url == "http://127.0.0.1:4000"


def test_env_gateway_key(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-client",
        {
            "NOUS_STACK_GATEWAY_URL": "http://127.0.0.1:4000",
            "NOUS_STACK_GATEWAY_KEY": "secret123",
        },
    )
    assert config.gateway is not None
    assert config.gateway.key == "secret123"


def test_env_workspace_root(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-gpu-host",
        {"NOUS_STACK_WORKSPACE_ROOT": "/tmp/workspace"},
    )
    assert config.workspace_root == Path("/tmp/workspace")


def test_env_data_dir(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-gpu-host",
        {"NOUS_STACK_DATA_DIR": "/tmp/data"},
    )
    assert config.data_dir == Path("/tmp/data")


def test_env_browser_domains_csv(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-gpu-host",
        {"NOUS_STACK_BROWSER_DOMAINS": "example.com, test.org"},
    )
    assert config.security.browser_domains == ["example.com", "test.org"]


# --- Validation tests ---


def test_gateway_host_outside_allowlist_rejected(repo_root: Path) -> None:
    with pytest.raises(ValueError, match="gateway host"):
        load_config(
            repo_root,
            "windows-client",
            {"NOUS_STACK_GATEWAY_URL": "http://8.8.8.8:4000"},
        )


def test_gateway_host_in_allowlist_accepted(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-client",
        {"NOUS_STACK_GATEWAY_URL": "http://127.0.0.1:4000"},
    )
    assert config.gateway is not None
    assert config.gateway.url == "http://127.0.0.1:4000"


def test_remote_gateway_host_from_env_can_be_explicitly_allowed(
    repo_root: Path,
) -> None:
    config = load_config(
        repo_root,
        "windows-client",
        {
            "NOUS_STACK_GATEWAY_URL": "https://gateway.example.com/v1",
            "NOUS_STACK_ALLOWED_GATEWAY_HOSTS": "gateway.example.com",
        },
    )
    assert config.gateway is not None
    assert config.gateway.url == "https://gateway.example.com/v1"


def test_gateway_key_without_url_has_actionable_error(repo_root: Path) -> None:
    with pytest.raises(ValueError, match="requires a configured gateway URL"):
        load_config(
            repo_root,
            "windows-gpu-host",
            {"NOUS_STACK_GATEWAY_KEY": "secret123"},
        )


# --- Immutability and structural tests ---


def test_config_is_immutable(repo_root: Path) -> None:
    config = load_config(repo_root, "windows-gpu-host", {})
    with pytest.raises(Exception):
        config.inference.mode = "gateway"  # type: ignore[misc]


def test_unknown_profile_raises(repo_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(repo_root, "nonexistent-profile", {})


# --- Merge order test ---


def test_merge_order_env_overrides_profile(repo_root: Path) -> None:
    config = load_config(
        repo_root,
        "windows-client",
        {"NOUS_STACK_GATEWAY_URL": "http://127.0.0.1:4000"},
    )
    assert config.inference.mode == "gateway"
    assert config.gateway is not None
    assert config.gateway.url == "http://127.0.0.1:4000"


def test_resolved_config_type_returned(repo_root: Path) -> None:
    config = load_config(repo_root, "windows-gpu-host", {})
    assert isinstance(config, ResolvedConfig)
    assert config.profile == "windows-gpu-host"
