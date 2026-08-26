"""Typed configuration resolver for LASSY.

Loads and merges ``config/defaults.yaml`` with a named profile YAML and
applies supported environment-variable overrides, returning an immutable
``ResolvedConfig`` Pydantic model. Later tasks consume only
``ResolvedConfig``; they do not parse YAML directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Mapping
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class EndpointConfig(BaseModel):
    """An authenticated endpoint (gateway or otherwise)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    url: str
    key: str | None = None


class ModelAliases(BaseModel):
    """Logical capability aliases mapped to Ollama model IDs.

    Context length is a per-capability concern handled by preflight in
    a later task; this model stores only the model ID strings.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    local_fast: str | None = None
    local_code: str | None = None
    local_browser: str | None = None
    local_vision: str | None = None
    cloud_free: str | None = None
    escalation_code: str | None = None
    escalation_autonomous: str | None = None


class SecurityConfig(BaseModel):
    """Security boundaries enforced at configuration time."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    ollama_bind: str = "127.0.0.1"
    allowed_gateway_hosts: list[str] = []
    browser_domains: list[str] = []

    @field_validator("ollama_bind")
    @classmethod
    def _loopback_only(cls, v: str) -> str:
        if v not in _LOOPBACK_HOSTS:
            raise ValueError(
                "raw Ollama exposure is prohibited; ollama_bind must be loopback"
            )
        return v


class InferenceConfig(BaseModel):
    """Inference mode: local Ollama or authenticated gateway."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    mode: Literal["local", "gateway"]


class LocalModelsConfig(BaseModel):
    """Local model download policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    auto_pull: bool = False


class ComponentsConfig(BaseModel):
    """Component enable/disable flags per profile."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    opencode: bool = False
    browser_use: bool = False
    cline: bool = False
    kilo: bool = False
    ollama: bool = False
    gateway: bool = False


class ResolvedConfig(BaseModel):
    """Fully resolved, immutable configuration consumed by all later tasks."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    profile: str
    inference: InferenceConfig
    local_models: LocalModelsConfig
    models: ModelAliases
    security: SecurityConfig
    components: ComponentsConfig
    ollama: EndpointConfig
    gateway: EndpointConfig | None = None
    workspace_root: Path | None = None
    data_dir: Path | None = None

    @model_validator(mode="after")
    def _validate_endpoints(self) -> ResolvedConfig:
        ollama_host = urlparse(self.ollama.url).hostname or ""
        if ollama_host not in _LOOPBACK_HOSTS:
            raise ValueError(
                "raw Ollama exposure is prohibited; ollama URL must be loopback"
            )
        if self.gateway is not None:
            gw_host = urlparse(self.gateway.url).hostname or ""
            allowed = _LOOPBACK_HOSTS | set(self.security.allowed_gateway_hosts)
            if gw_host not in allowed:
                raise ValueError(
                    f"gateway host '{gw_host}' is not in the allowed list "
                    f"(loopback plus allowed_gateway_hosts)"
                )
        return self


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base``.

    Nested dicts are merged recursively; non-dict values in ``override``
    replace the corresponding value in ``base``.
    """
    result = {**base}
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(merged: dict, env: Mapping[str, str]) -> dict:
    """Apply supported environment-variable overrides."""
    result = {**merged}
    if "NOUS_STACK_ALLOWED_GATEWAY_HOSTS" in env:
        hosts = [
            host.strip().lower()
            for host in env["NOUS_STACK_ALLOWED_GATEWAY_HOSTS"].split(",")
            if host.strip()
        ]
        result.setdefault("security", {})
        result["security"]["allowed_gateway_hosts"] = hosts
    if "NOUS_STACK_GATEWAY_URL" in env:
        if result.get("gateway") is None:
            result["gateway"] = {}
        result["gateway"]["url"] = env["NOUS_STACK_GATEWAY_URL"]
    if "NOUS_STACK_GATEWAY_KEY" in env:
        if result.get("gateway") is None or not result["gateway"].get("url"):
            raise ValueError(
                "NOUS_STACK_GATEWAY_KEY requires a configured gateway URL"
            )
        result["gateway"]["key"] = env["NOUS_STACK_GATEWAY_KEY"]
    if "NOUS_STACK_WORKSPACE_ROOT" in env:
        result["workspace_root"] = env["NOUS_STACK_WORKSPACE_ROOT"]
    if "NOUS_STACK_DATA_DIR" in env:
        result["data_dir"] = env["NOUS_STACK_DATA_DIR"]
    if "NOUS_STACK_BROWSER_DOMAINS" in env:
        domains = [
            d.strip() for d in env["NOUS_STACK_BROWSER_DOMAINS"].split(",") if d.strip()
        ]
        result.setdefault("security", {})
        result["security"]["browser_domains"] = domains
    return result


def load_config(
    repo_root: Path, profile: str, env: Mapping[str, str]
) -> ResolvedConfig:
    """Load and merge defaults, a named profile, and env overrides.

    Merge order: ``config/defaults.yaml`` → ``config/profiles/<profile>.yaml``
    → environment overrides. Returns an immutable ``ResolvedConfig``.

    Raises:
        FileNotFoundError: If the profile YAML does not exist.
        ValueError: If validation fails (e.g. non-loopback Ollama bind).
    """
    defaults_path = repo_root / "config" / "defaults.yaml"
    profile_path = repo_root / "config" / "profiles" / f"{profile}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile}")
    with open(defaults_path) as f:
        defaults = yaml.safe_load(f) or {}
    with open(profile_path) as f:
        profile_data = yaml.safe_load(f) or {}
    merged = _deep_merge(defaults, profile_data)
    merged = _apply_env_overrides(merged, env)
    merged["profile"] = profile
    return ResolvedConfig.model_validate(merged)
