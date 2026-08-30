from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.error_messages import GENERIC_QUEUE_ERROR
from app.services.scan_lifecycle import ScanLifecycleService


def _scan(repository_id, project_id):
    return SimpleNamespace(
        id=uuid4(),
        repository_id=repository_id,
        project_id=project_id,
        branch_name="main",
        commit_sha="deadbeef",
        status="queued",
        error_message=None,
    )


@pytest.mark.asyncio
async def test_create_manual_scan_creates_scan_and_enqueues_job():
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    user_id = uuid4()
    scan = _scan(repository_id, project_id)
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(scan, None, None)))
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="job-123"))
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    data = SimpleNamespace(repository_id=repository_id, scan_type="full")

    result = await ScanLifecycleService(db, scan_service=scan_service, queue=queue).create_manual_scan(
        org_id=org_id,
        data=data,
        user_id=user_id,
    )

    assert result is scan
    scan_service.create.assert_awaited_once_with(repository_id, data, user_id)
    queue.enqueue.assert_awaited_once_with(
        "scan.repo.full",
        {"scan_id": str(scan.id)},
        organization_id=org_id,
    )
    db.commit.assert_not_awaited()
    db.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_manual_scan_records_generic_error_when_enqueue_fails():
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    user_id = uuid4()
    scan = _scan(repository_id, project_id)
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(scan, None, None)))
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=RuntimeError("Authorization token leaked")))
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    data = SimpleNamespace(repository_id=repository_id, scan_type="secrets")

    result = await ScanLifecycleService(db, scan_service=scan_service, queue=queue).create_manual_scan(
        org_id=org_id,
        data=data,
        user_id=user_id,
    )

    assert result is scan
    assert scan.status == "failed"
    assert scan.error_message == GENERIC_QUEUE_ERROR
    queue.enqueue.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(scan)


@pytest.mark.asyncio
async def test_create_scheduled_scan_uses_same_scan_job_invariants():
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    schedule = SimpleNamespace(id=uuid4(), repository_id=repository_id, scan_type="dependencies")
    scan = _scan(repository_id, project_id)
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(scan, None, project)))
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="job-456"))
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    outcome = await ScanLifecycleService(db, scan_service=scan_service, queue=queue).create_scheduled_scan(schedule)

    assert outcome.scan is scan
    assert outcome.enqueued is True
    scan_service.create.assert_awaited_once()
    created_data = scan_service.create.await_args.args[1]
    assert created_data.repository_id == repository_id
    assert created_data.trigger_type == "scheduled"
    assert created_data.scan_type == "dependencies"
    queue.enqueue.assert_awaited_once_with(
        "scan.dependencies",
        {"scan_id": str(scan.id)},
        organization_id=org_id,
    )


@pytest.mark.asyncio
async def test_create_scheduled_scan_reports_enqueue_failure_without_marking_schedule_run():
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    schedule = SimpleNamespace(id=uuid4(), repository_id=repository_id, scan_type="full")
    scan = _scan(repository_id, project_id)
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(scan, None, project)))
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=RuntimeError("queue unavailable")))
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    outcome = await ScanLifecycleService(db, scan_service=scan_service, queue=queue).create_scheduled_scan(schedule)

    assert outcome.scan is scan
    assert outcome.enqueued is False
    assert scan.status == "failed"
    assert scan.error_message == GENERIC_QUEUE_ERROR
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(scan)
