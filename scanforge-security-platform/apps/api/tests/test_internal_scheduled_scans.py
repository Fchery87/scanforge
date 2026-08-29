from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.routes import internal
from app.schemas.scans import ScanStatusUpdate
from app.services.worker_identities import WorkerPrincipal


@pytest.mark.asyncio
async def test_run_due_scan_schedules_marks_only_enqueued_schedules(monkeypatch):
    queued_schedule = SimpleNamespace(id=uuid4())
    failed_schedule = SimpleNamespace(id=uuid4())
    schedule_service = SimpleNamespace(
        get_due_schedules=AsyncMock(return_value=[queued_schedule, failed_schedule]),
        mark_run=AsyncMock(),
    )
    lifecycle = SimpleNamespace(
        create_scheduled_scan=AsyncMock(
            side_effect=[
                SimpleNamespace(enqueued=True),
                SimpleNamespace(enqueued=False),
            ]
        )
    )

    monkeypatch.setattr(internal, "ScanScheduleService", lambda _db: schedule_service)
    monkeypatch.setattr(internal, "ScanLifecycleService", lambda _db: lifecycle)

    result = await internal.run_due_scan_schedules(db=object())

    assert result == {"found": 2, "queued": 1, "failed": 1}
    schedule_service.mark_run.assert_awaited_once_with(queued_schedule.id)


@pytest.mark.asyncio
async def test_run_due_scan_schedules_counts_lifecycle_exceptions(monkeypatch):
    schedule = SimpleNamespace(id=uuid4())
    schedule_service = SimpleNamespace(
        get_due_schedules=AsyncMock(return_value=[schedule]),
        mark_run=AsyncMock(),
    )
    lifecycle = SimpleNamespace(create_scheduled_scan=AsyncMock(side_effect=RuntimeError("boom")))

    monkeypatch.setattr(internal, "ScanScheduleService", lambda _db: schedule_service)
    monkeypatch.setattr(internal, "ScanLifecycleService", lambda _db: lifecycle)

    result = await internal.run_due_scan_schedules(db=object())

    assert result == {"found": 1, "queued": 0, "failed": 1}
    schedule_service.mark_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_scan_execution_context_loads_authoritative_scan_context():
    scan_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(
        id=scan_id,
        project_id=str(project_id),
        repository_id=str(repository_id),
        scan_type="dependencies",
        branch_name="main",
        commit_sha="deadbeef",
        requested_by_user_id=user_id,
        status=internal.ScanStatus.RUNNING,
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    principal = WorkerPrincipal(uuid4(), org_id, frozenset({"scans:read"}))
    result_row = SimpleNamespace(scalar_one_or_none=lambda: scan)

    class Db:
        async def execute(self, _query):
            return result_row

        async def get(self, model, key):
            if model is internal.Scan and key == str(scan_id):
                return scan
            if model is internal.Project and key == str(project_id):
                return project
            return None

    result = await internal.get_scan_execution_context(scan_id=scan_id, principal=principal, db=Db())

    assert result == {
        "scan_id": str(scan_id),
        "org_id": str(org_id),
        "repository_id": str(repository_id),
        "project_id": str(project_id),
        "scan_type": "dependencies",
        "expected_scanners": ["trivy", "osv", "syft", "grype"],
        "coverage_scope": {
            "branch": "main",
            "commit_sha": "deadbeef",
            "scan_type": "dependencies",
        },
        "branch": "main",
        "commit_sha": "deadbeef",
        "user_id": str(user_id),
        "status": "running",
    }


@pytest.mark.asyncio
async def test_completed_scan_status_requires_atomic_completion_endpoint(monkeypatch):
    scan_id = uuid4()
    scan = SimpleNamespace(id=scan_id, repository_id="repo-1", status="running", summary_json=None, error_message=None)
    lifecycle = SimpleNamespace(mark_not_observed_for_completed_scan=AsyncMock(return_value=2))
    principal = WorkerPrincipal(uuid4(), uuid4(), frozenset({"scans:write"}))
    result_row = SimpleNamespace(scalar_one_or_none=lambda: scan)

    class Db:
        async def execute(self, _query):
            return result_row

        async def get(self, model, key):
            if model is internal.Scan and key == str(scan_id):
                return scan
            return None

        async def commit(self):
            return None

        async def refresh(self, _scan):
            return None

    monkeypatch.setattr(internal, "FindingService", lambda _db: lifecycle)

    summary = {"scanner_health": {"completed": ["trivy"]}}
    with pytest.raises(internal.HTTPException) as exc:
        await internal.update_scan_status_internal(
            scan_id=scan_id,
            data=ScanStatusUpdate(status="completed", summary_json=summary),
            principal=principal,
            db=Db(),
        )

    assert exc.value.status_code == 409
    lifecycle.mark_not_observed_for_completed_scan.assert_not_awaited()
