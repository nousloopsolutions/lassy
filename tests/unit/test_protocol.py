from datetime import UTC, datetime, timedelta

import pytest

from lassy.protocol import JobEnvelope, sign_bytes


SECRET = "a" * 32


def signed_job(**updates: object) -> JobEnvelope:
    now = datetime.now(UTC)
    data = {
        "id": "job_12345678",
        "kind": "repo_status",
        "workspace": "lassy",
        "prompt": None,
        "issued_at": now,
        "expires_at": now + timedelta(minutes=5),
        "nonce": "nonce-1234567890abcdef",
        "signature": "0" * 64,
        **updates,
    }
    unsigned = JobEnvelope.model_validate(data)
    signature = sign_bytes(unsigned.signing_payload(), SECRET)
    return unsigned.model_copy(update={"signature": signature})


def test_valid_signature_is_accepted() -> None:
    job = signed_job()
    job.verify(SECRET)


def test_tampered_job_is_rejected() -> None:
    job = signed_job().model_copy(update={"workspace": "other"})
    with pytest.raises(ValueError, match="signature"):
        job.verify(SECRET)


def test_expired_job_is_rejected() -> None:
    now = datetime.now(UTC)
    job = signed_job(issued_at=now - timedelta(minutes=2), expires_at=now - timedelta(minutes=1))
    with pytest.raises(ValueError, match="expired"):
        job.verify(SECRET, now=now)


def test_non_health_job_requires_workspace() -> None:
    job = signed_job(workspace=None)
    with pytest.raises(ValueError, match="registered workspace"):
        job.verify(SECRET)
