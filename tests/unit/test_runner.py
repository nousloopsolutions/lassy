import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from lassy.protocol import JobEnvelope, sign_bytes
from lassy.runner import Runner


SECRET = "b" * 32


def _health_job() -> dict[str, object]:
    now = datetime.now(UTC)
    unsigned = JobEnvelope(
        id="job_health_1234",
        kind="health",
        workspace=None,
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
        nonce="nonce-health-12345678",
        signature="0" * 64,
    )
    return unsigned.model_copy(
        update={"signature": sign_bytes(unsigned.signing_payload(), SECRET)}
    ).model_dump(mode="json")


def _runner(tmp_path: Path, handler: httpx.MockTransport) -> Runner:
    workspaces = tmp_path / "workspaces.yaml"
    workspaces.write_text("workspaces: {}\n", encoding="utf-8")
    return Runner(
        control_url="https://control.example.com",
        runner_id="bigg-rigg",
        secret=SECRET,
        workspace_config=workspaces,
        data_dir=tmp_path / "data",
        client=httpx.Client(transport=handler),
    )


def test_runner_claims_executes_and_returns_signed_result(tmp_path: Path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path == "/runner/claim":
            return httpx.Response(200, json=_health_job())
        return httpx.Response(200, json={"ok": True})

    runner = _runner(tmp_path, httpx.MockTransport(handle))
    assert runner.run_once() is True
    assert [path for path, _ in calls] == ["/runner/claim", "/runner/result"]
    result = calls[1][1]
    assert result["status"] == "succeeded"
    assert result["signature"]
    assert not runner.pending_result_path.exists()


def test_pending_result_is_retried_before_claiming(tmp_path: Path) -> None:
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    runner = _runner(tmp_path, httpx.MockTransport(handle))
    runner.pending_result_path.write_text('{"job_id":"job_old"}', encoding="utf-8")
    assert runner.run_once() is True
    assert paths == ["/runner/result"]
    assert not runner.pending_result_path.exists()


def test_runner_retries_transient_network_failure_with_bounded_backoff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner(tmp_path, httpx.MockTransport(lambda request: httpx.Response(204)))
    attempts = 0
    sleeps: list[float] = []

    def run_once() -> bool:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary outage")
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_once", run_once)
    monkeypatch.setattr("lassy.runner.time.sleep", sleeps.append)

    with pytest.raises(KeyboardInterrupt):
        runner.run_forever(poll_seconds=2, max_backoff_seconds=10)

    assert sleeps == [2]
    audit_record = json.loads(runner.audit.path.read_text(encoding="utf-8"))
    assert audit_record["event"] == "runner_poll_error"
    assert audit_record["error_type"] == "ConnectError"
    assert audit_record["retry_in_seconds"] == 2
