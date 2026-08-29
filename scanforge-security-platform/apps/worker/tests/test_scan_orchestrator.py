from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from app.scanners.base import ScannerResult
from app.services.scan_orchestrator import ScanContext, ScanOrchestrator


class DummyQueue:
    def __init__(self):
        self.requeued_jobs = []
        self.acked_jobs = []

    async def update_job_status(self, *_args, **_kwargs):
        return None

    async def increment_retry(self, *_args, **_kwargs):
        return 0

    async def requeue(self, job, delay_seconds: int = 0):
        self.requeued_jobs.append((job, delay_seconds))

    async def enqueue_to_dlq(self, *_args, **_kwargs):
        return None

    async def transfer_to_dlq(self, job):
        await self.enqueue_to_dlq(job)
        await self.ack(job.job_id, job.stream_id)

    async def ack(self, *args, **_kwargs):
        self.acked_jobs.append(args)

    async def release(self, *_args, **_kwargs):
        return None


class DummyR2:
    def upload_raw_output(self, scan_id: str, scanner_name: str, output_data: dict) -> str:
        return f"https://cdn.example/scans/{scan_id}/{scanner_name}/raw_output.json"

    def upload_file(self, file_path: Path, key: str) -> dict:
        return {"storage_uri": f"https://cdn.example/{key}"}


@pytest.mark.asyncio
async def test_upload_artifacts_returns_scanner_run_updates(tmp_path: Path):
    artifact = tmp_path / "trivy-results.json"
    artifact.write_text("{}")

    orchestrator = ScanOrchestrator(queue=DummyQueue(), r2=DummyR2())
    updates = []

    async def capture_update(run_id: str, **kwargs):
        updates.append((run_id, kwargs))

    orchestrator._execution._update_scanner_run = capture_update
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="job-1",
    )
    context.scanner_results = {
        "trivy": ScannerResult(
            scanner_name="trivy",
            success=True,
            raw_output={"Results": []},
            artifact_paths=[artifact],
        )
    }
    context.scanner_run_ids = {"trivy": "run-1"}

    uploads = await orchestrator._execution.upload_artifacts(context)

    assert uploads["trivy_raw"] == "https://cdn.example/scans/scan-1/trivy/raw_output.json"
    assert (
        uploads["scanner_runs"]["trivy"]["artifact_uri"] == "https://cdn.example/scans/scan-1/trivy/trivy-results.json"
    )
    assert updates == [
        (
            "run-1",
            {
                "artifact_uri": "https://cdn.example/scans/scan-1/trivy/trivy-results.json",
                "metadata_json": {
                    "raw_output_uri": "https://cdn.example/scans/scan-1/trivy/raw_output.json",
                    "artifact_uri": "https://cdn.example/scans/scan-1/trivy/trivy-results.json",
                },
            },
        )
    ]


def test_scan_summary_uses_duration_ms():
    duration_seconds = 12.3

    summary = {
        "duration_ms": int(duration_seconds * 1000),
        "duration_seconds": round(duration_seconds, 1),
    }

    assert summary["duration_ms"] == 12300


def test_diff_scan_records_changed_files_scope():
    changed_files = ["src/app.py", "infra/main.tf"]

    summary = {
        "scope": "diff",
        "changed_files": changed_files,
    }

    assert summary["scope"] == "diff"
    assert summary["changed_files"] == changed_files


def test_scan_summary_records_scanner_health_separately_from_scan_status():
    context = ScanContext(
        scan_id="scan-1",
        organization_id="org-1",
        repository_id="repo-1",
        project_id="project-1",
        branch="main",
        commit_sha=None,
        job_id="job-1",
        expected_scanners=["trivy", "gitleaks"],
    )
    context.scanner_results = {
        "trivy": ScannerResult(scanner_name="trivy", success=True, raw_output={}, artifact_paths=[]),
        "gitleaks": ScannerResult(
            scanner_name="gitleaks",
            success=False,
            raw_output={},
            artifact_paths=[],
            error="scanner failed",
        ),
    }
    context.findings = [
        {"canonical_fingerprint": "fp-1"},
        {"canonical_fingerprint": "fp-2"},
    ]

    summary = ScanOrchestrator(queue=DummyQueue(), r2=DummyR2())._build_completion_summary(
        context,
        job_type="scan.repo.full",
        duration_seconds=3.2,
    )

    assert summary["scanner_health"] == {
        "expected": ["trivy", "gitleaks"],
        "completed": ["trivy"],
        "failed": ["gitleaks"],
        "missing": [],
        "complete": False,
    }
    assert summary["scanners_run"] == ["trivy", "gitleaks"]
    assert summary["seen_fingerprints"] == ["fp-1", "fp-2"]


def test_scan_type_mappings_include_checkov_and_grype():
    orchestrator = ScanOrchestrator(queue=DummyQueue(), r2=DummyR2())

    assert "checkov" in orchestrator._get_scanners_for_type("scan.repo.full")
    assert "grype" in orchestrator._get_scanners_for_type("scan.repo.full")
    assert "checkov" in orchestrator._get_scanners_for_type("scan.repo.diff")
    assert "grype" in orchestrator._get_scanners_for_type("scan.dependencies")


@pytest.mark.asyncio
async def test_failed_job_requeues_with_same_job_id():
    queue = DummyQueue()
    orchestrator = ScanOrchestrator(queue=queue, r2=DummyR2())

    async def fail_status(*_args, **_kwargs):
        return None

    async def not_canceled(*_args, **_kwargs):
        return False

    async def explode_repo(*_args, **_kwargs):
        raise RuntimeError("clone failed")

    orchestrator._update_status = fail_status
    orchestrator._update_scan_status = fail_status
    orchestrator._stop_if_canceled = not_canceled
    orchestrator._execution.prepare_repository = explode_repo

    async def load_context(job):
        return ScanContext(
            scan_id=job.payload["scan_id"],
            organization_id="org-1",
            repository_id="repo-1",
            project_id="project-1",
            branch=None,
            commit_sha=None,
            job_id=job.job_id,
        )

    orchestrator._load_scan_context = load_context

    from app.clients.queue import QueueJob

    job = QueueJob(
        job_type="scan.repo.full",
        job_id="job-123",
        payload={
            "scan_id": "scan-1",
        },
        created_at="2026-03-31T00:00:00",
    )

    success = await orchestrator.process_job(job)

    assert success is False
    assert len(queue.requeued_jobs) == 1
    assert queue.requeued_jobs[0][0].job_id == "job-123"
    assert queue.acked_jobs == []


@pytest.mark.asyncio
async def test_canceled_job_is_acknowledged_without_clone_or_completion():
    queue = DummyQueue()
    orchestrator = ScanOrchestrator(queue=queue, r2=DummyR2())
    orchestrator._update_status = AsyncMock()
    orchestrator._update_scan_status = AsyncMock()
    orchestrator._execution.prepare_repository = AsyncMock()
    orchestrator._persistence.complete_scan = AsyncMock()
    orchestrator._load_scan_context = AsyncMock(
        return_value=ScanContext(
            scan_id="scan-1",
            organization_id="org-1",
            repository_id="repo-1",
            project_id="project-1",
            branch=None,
            commit_sha=None,
            job_id="scan-1",
            stream_id="1-0",
            authoritative_status="canceled",
        )
    )

    from app.clients.queue import QueueJob

    success = await orchestrator.process_job(
        QueueJob(job_type="scan.repo.full", job_id="scan-1", payload={"scan_id": "scan-1"}, created_at="now")
    )

    assert success is True
    assert queue.acked_jobs == [("scan-1", "1-0")]
    orchestrator._execution.prepare_repository.assert_not_awaited()
    orchestrator._persistence.complete_scan.assert_not_awaited()
    orchestrator._update_scan_status.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timeout"), httpx.HTTPStatusError("500", request=None, response=None)])
async def test_completion_failure_is_not_acknowledged_and_remains_retryable(failure):
    queue = DummyQueue()
    orchestrator = ScanOrchestrator(queue=queue, r2=DummyR2())
    orchestrator._update_status = AsyncMock()
    orchestrator._update_scan_status = AsyncMock()
    orchestrator._stop_if_canceled = AsyncMock(return_value=False)
    orchestrator._execution.prepare_repository = AsyncMock(return_value=Path("/nonexistent"))
    orchestrator._execution.run_scanners = AsyncMock(return_value={})
    orchestrator._execution.upload_artifacts = AsyncMock(return_value={})
    orchestrator._ai_investigation.run = AsyncMock()
    orchestrator._persistence.complete_scan = AsyncMock(side_effect=failure)
    orchestrator._load_scan_context = AsyncMock(
        return_value=ScanContext(
            scan_id="scan-1",
            organization_id="org-1",
            repository_id="repo-1",
            project_id="project-1",
            branch=None,
            commit_sha=None,
            job_id="scan-1",
            stream_id="1-0",
        )
    )

    from app.clients.queue import QueueJob

    success = await orchestrator.process_job(
        QueueJob(job_type="scan.repo.full", job_id="scan-1", payload={"scan_id": "scan-1"}, created_at="now")
    )

    assert success is False
    assert queue.acked_jobs == []
    assert len(queue.requeued_jobs) == 1


@pytest.mark.asyncio
async def test_dlq_transfer_happens_before_original_acknowledgement():
    events = []
    queue = DummyQueue()

    async def transfer(job):
        events.append("dlq")
        events.append("ack")
        queue.acked_jobs.append((job.job_id, job.stream_id))

    queue.transfer_to_dlq = transfer
    queue.increment_retry = AsyncMock(return_value=ScanOrchestrator.MAX_RETRIES)
    orchestrator = ScanOrchestrator(queue=queue, r2=DummyR2())
    orchestrator._update_status = AsyncMock()
    orchestrator._update_scan_status = AsyncMock()
    orchestrator._execution.prepare_repository = AsyncMock(side_effect=RuntimeError("clone failed"))
    orchestrator._stop_if_canceled = AsyncMock(return_value=False)
    orchestrator._load_scan_context = AsyncMock(
        return_value=ScanContext(
            scan_id="scan-1",
            organization_id="org-1",
            repository_id="repo-1",
            project_id="project-1",
            branch=None,
            commit_sha=None,
            job_id="scan-1",
            stream_id="1-0",
        )
    )

    from app.clients.queue import QueueJob

    await orchestrator.process_job(
        QueueJob(job_type="scan.repo.full", job_id="scan-1", payload={"scan_id": "scan-1"}, created_at="now")
    )

    assert events == ["dlq", "ack"]


@pytest.mark.asyncio
async def test_load_scan_context_fetches_authoritative_context(monkeypatch):
    orchestrator = ScanOrchestrator(queue=DummyQueue(), r2=DummyR2(), api_base_url="http://api.local")
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "scan_id": "scan-1",
                "org_id": "org-1",
                "repository_id": "repo-1",
                "project_id": "project-1",
                "scan_type": "dependencies",
                "expected_scanners": ["trivy", "osv", "syft", "grype"],
                "coverage_scope": {
                    "branch": "main",
                    "commit_sha": "deadbeef",
                    "scan_type": "dependencies",
                },
                "branch": "main",
                "commit_sha": "deadbeef",
                "user_id": None,
            }

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers, timeout):
            requests.append({"url": url, "headers": headers, "timeout": timeout})
            return Response()

    monkeypatch.setattr("app.services.scan_orchestrator.httpx.AsyncClient", Client)

    from app.clients.queue import QueueJob

    context = await orchestrator._load_scan_context(
        QueueJob(job_type="scan.repo.full", job_id="job-1", payload={"scan_id": "scan-1"}, created_at="now")
    )

    assert context.scan_id == "scan-1"
    assert context.organization_id == "org-1"
    assert context.branch == "main"
    assert context.expected_scanners == ["trivy", "osv", "syft", "grype"]
    assert context.coverage_scope == {
        "branch": "main",
        "commit_sha": "deadbeef",
        "scan_type": "dependencies",
    }
    assert requests[0]["url"] == "http://api.local/api/v1/internal/scans/scan-1/execution-context"


@pytest.mark.asyncio
async def test_load_scan_context_rejects_payload_without_scan_id():
    from app.clients.queue import QueueJob

    with pytest.raises(ValidationError, match="scan_id"):
        QueueJob(job_type="scan.repo.full", job_id="job-1", payload={}, created_at="now")
