"""Outbound-only polling runner for the Cloudflare LASSY control plane."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from lassy.audit import AuditLog
from lassy.executor import JobExecutor
from lassy.protocol import JobEnvelope, JobResult
from lassy.workspaces import WorkspaceRegistry


class Runner:
    def __init__(
        self,
        *,
        control_url: str,
        runner_id: str,
        secret: str,
        workspace_config: Path,
        data_dir: Path,
        client: httpx.Client | None = None,
    ) -> None:
        if not control_url.startswith("https://") and not control_url.startswith(
            "http://127.0.0.1"
        ):
            raise ValueError("control URL must use HTTPS or loopback HTTP")
        self.control_url = control_url.rstrip("/")
        self.runner_id = runner_id
        self.secret = secret
        self.registry = WorkspaceRegistry.load(workspace_config)
        self.executor = JobExecutor(self.registry)
        self.audit = AuditLog(data_dir / "audit.jsonl")
        self.seen_path = data_dir / "seen-jobs.json"
        self.pending_result_path = data_dir / "pending-result.json"
        self.seen_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.Client(timeout=30)

    def run_once(self) -> bool:
        if self._flush_pending_result():
            return True
        response = self.client.post(
            f"{self.control_url}/runner/claim",
            headers={"Authorization": f"Bearer {self.secret}"},
            json={"runner_id": self.runner_id},
        )
        if response.status_code == 204:
            return False
        response.raise_for_status()
        raw = response.json()
        started = datetime.now(UTC)
        try:
            job = JobEnvelope.model_validate(raw)
            job.verify(self.secret, now=started)
            if job.id in self._seen():
                raise ValueError("job replay detected")
            self._remember(job.id)
            execution = self.executor.execute(job)
            status = "succeeded" if execution.exit_code == 0 else "failed"
            result = JobResult(
                job_id=job.id,
                runner_id=self.runner_id,
                status=status,
                started_at=started,
                finished_at=datetime.now(UTC),
                exit_code=execution.exit_code,
                output=execution.output,
                output_truncated=execution.truncated,
            ).signed(self.secret)
        except Exception as exc:
            job_id = str(raw.get("id", "invalid-job"))[:80]
            result = JobResult(
                job_id=job_id,
                runner_id=self.runner_id,
                status="rejected",
                started_at=started,
                finished_at=datetime.now(UTC),
                output=f"{type(exc).__name__}: {exc}",
            ).signed(self.secret)
        self.audit.append(result.model_dump(mode="json"))
        self._write_json_atomic(
            self.pending_result_path, result.model_dump(mode="json")
        )
        self._flush_pending_result()
        return True

    def _flush_pending_result(self) -> bool:
        if not self.pending_result_path.exists():
            return False
        payload = json.loads(self.pending_result_path.read_text(encoding="utf-8"))
        submitted = self.client.post(
            f"{self.control_url}/runner/result",
            headers={"Authorization": f"Bearer {self.secret}"},
            json=payload,
        )
        submitted.raise_for_status()
        self.pending_result_path.unlink()
        return True

    def run_forever(self, poll_seconds: float = 5.0) -> None:
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(poll_seconds)

    def _seen(self) -> set[str]:
        if not self.seen_path.exists():
            return set()
        return set(json.loads(self.seen_path.read_text(encoding="utf-8")))

    def _remember(self, job_id: str) -> None:
        seen = list(self._seen())[-999:]
        seen.append(job_id)
        self._write_json_atomic(self.seen_path, seen)

    @staticmethod
    def _write_json_atomic(path: Path, value: object) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(value), encoding="utf-8")
        temp.replace(path)
