"""Signed, replay-resistant messages exchanged with the LASSY control plane."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


JobKind = Literal["health", "repo_status", "repo_test", "repo_lint", "opencode_review"]


class JobEnvelope(BaseModel):
    """A control-plane job whose signature covers every executable field."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{8,80}$")
    kind: JobKind
    workspace: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    prompt: str | None = Field(default=None, max_length=4000)
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=16, max_length=128)
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("issued_at", "expires_at")
    @classmethod
    def _timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value.astimezone(UTC)

    def signing_payload(self) -> bytes:
        data = self.model_dump(mode="json", exclude={"signature"})
        return canonical_json(data)

    def verify(self, secret: str, *, now: datetime | None = None) -> None:
        current = (now or datetime.now(UTC)).astimezone(UTC)
        expected = sign_bytes(self.signing_payload(), secret)
        if not hmac.compare_digest(self.signature, expected):
            raise ValueError("job signature is invalid")
        if self.issued_at > current:
            raise ValueError("job was issued in the future")
        if self.expires_at <= current:
            raise ValueError("job has expired")
        if self.expires_at <= self.issued_at:
            raise ValueError("job expiry must follow issue time")
        if self.kind != "health" and self.workspace is None:
            raise ValueError(f"{self.kind} requires a registered workspace")
        if self.kind == "opencode_review" and not self.prompt:
            raise ValueError("opencode_review requires a prompt")


class JobResult(BaseModel):
    """Bounded result returned to the control plane."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    job_id: str
    runner_id: str
    status: Literal["succeeded", "failed", "rejected"]
    started_at: datetime
    finished_at: datetime
    exit_code: int | None = None
    output: str = Field(max_length=32000)
    output_truncated: bool = False
    signature: str = ""

    def signing_payload(self) -> bytes:
        return canonical_json(self.model_dump(mode="json", exclude={"signature"}))

    def signed(self, secret: str) -> JobResult:
        return self.model_copy(update={"signature": sign_bytes(self.signing_payload(), secret)})


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_bytes(payload: bytes, secret: str) -> str:
    if len(secret) < 32:
        raise ValueError("runner secret must be at least 32 characters")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
