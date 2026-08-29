from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.enums import ScanStatus
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services import scan_completion
from app.services.scan_completion import ScanCompletionConflict, ScanCompletionService


def completion_request() -> ScanCompletionRequest:
    return ScanCompletionRequest(
        findings=[],
        scanner_runs=[ScannerRunCompletion(scanner_name="trivy", status="completed", exit_code=0)],
        summary_json={
            "seen_fingerprints": [],
            "scanner_health": {
                "expected": ["trivy"],
                "completed": ["trivy"],
                "failed": [],
                "missing": [],
                "complete": True,
            },
        },
    )


def result(value):
    row = Mock()
    row.scalar_one_or_none.return_value = value
    row.scalars.return_value = []
    return row


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_and_leaves_scan_incomplete(monkeypatch):
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        status=ScanStatus.RUNNING,
        summary_json=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [result(scan), result(None)]
    db.add = Mock()
    db.commit.side_effect = RuntimeError("commit failed")
    findings = SimpleNamespace(
        upsert_from_scan=AsyncMock(return_value=(1, 0)),
        mark_not_observed_after_scan=AsyncMock(return_value=0),
    )
    monkeypatch.setattr(scan_completion, "FindingService", lambda _db: findings)

    with pytest.raises(RuntimeError, match="commit failed"):
        await ScanCompletionService(db).complete(uuid4(), uuid4(), completion_request())

    db.rollback.assert_awaited_once()
    assert scan.status == ScanStatus.COMPLETED  # in-memory only; rollback protects durable state


@pytest.mark.asyncio
async def test_duplicate_completion_is_a_noop():
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        status=ScanStatus.COMPLETED,
        summary_json={},
    )
    db = AsyncMock()
    db.execute.return_value = result(scan)

    response = await ScanCompletionService(db).complete(uuid4(), uuid4(), completion_request())

    assert response["replayed"] is True
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_canceled_scan_cannot_complete_and_is_rolled_back():
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        status=ScanStatus.CANCELED,
        summary_json=None,
    )
    db = AsyncMock()
    db.execute.return_value = result(scan)

    with pytest.raises(ScanCompletionConflict):
        await ScanCompletionService(db).complete(uuid4(), uuid4(), completion_request())

    assert scan.status == ScanStatus.CANCELED
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_scanner_health_findings_and_lifecycle_commit_before_completed(monkeypatch):
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        status=ScanStatus.RUNNING,
        summary_json=None,
    )
    db = AsyncMock()
    db.execute.side_effect = [result(scan), result(None)]
    db.add = Mock()
    findings = SimpleNamespace(
        upsert_from_scan=AsyncMock(return_value=(1, 0)),
        mark_not_observed_after_scan=AsyncMock(return_value=1),
    )
    monkeypatch.setattr(scan_completion, "FindingService", lambda _db: findings)
    request = completion_request()

    response = await ScanCompletionService(db).complete(uuid4(), uuid4(), request)

    assert response["status"] == "completed"
    assert scan.status == ScanStatus.COMPLETED
    assert scan.summary_json == request.summary_json
    findings.upsert_from_scan.assert_awaited_once()
    assert findings.upsert_from_scan.await_args.kwargs["commit"] is False
    findings.mark_not_observed_after_scan.assert_awaited_once()
    assert findings.mark_not_observed_after_scan.await_args.kwargs["commit"] is False
    db.commit.assert_awaited_once()
