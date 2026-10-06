from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.enums import ScanStatus
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services import scan_completion
from app.services.scan_completion import (
    CompletionPayloadConflict,
    CompletionSuperseded,
    ScanCompletionConflict,
    ScanCompletionService,
)


def _completion_request(*, fingerprint: str = "", attempt_id=None) -> ScanCompletionRequest:
    finding = {
        "canonical_fingerprint": fingerprint,
        "severity": "high",
        "category": "code",
        "title": "Test finding",
    }
    return ScanCompletionRequest(
        winning_attempt_id=attempt_id or uuid4(),
        execution_revision=1,
        findings=[finding] if fingerprint else [],
        scanner_runs=[
            ScannerRunCompletion(scanner_name="trivy", status="completed", exit_code=0),
        ],
        summary_json={
            "seen_fingerprints": ["forged"],
            "scanner_health": {"complete": False},
        },
    )


def _result(value):
    row = Mock()
    row.scalar_one_or_none.return_value = value
    row.scalars.return_value = []
    return row


@pytest.mark.asyncio
async def test_completion_derives_summary_fingerprints_and_scanner_health(monkeypatch):
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        scan_type="dependencies",
        status=ScanStatus.RUNNING,
        summary_json=None,
        current_attempt_id=None,
        execution_revision=0,
    )
    request = _completion_request(fingerprint="accepted")
    scan.current_attempt_id = str(request.winning_attempt_id)
    scan.execution_revision = request.execution_revision
    db = AsyncMock()
    db.execute.side_effect = [_result(scan), _result(None), _result(None)]
    db.add = Mock()
    findings = SimpleNamespace(
        upsert_from_scan=AsyncMock(return_value=(1, 0)),
        mark_not_observed_after_scan=AsyncMock(return_value=0),
    )
    monkeypatch.setattr(scan_completion, "FindingService", lambda _db: findings)
    response = await ScanCompletionService(db).complete(uuid4(), uuid4(), request)

    assert response["status"] == "completed"
    assert scan.summary_json["seen_fingerprints"] == ["accepted"]
    assert scan.summary_json["scanner_health"] == {
        "expected": ["grype", "osv", "syft", "trivy"],
        "completed": ["trivy"],
        "failed": [],
        "missing": ["grype", "osv", "syft"],
        "complete": False,
    }
    lifecycle_call = findings.mark_not_observed_after_scan.await_args.kwargs
    assert lifecycle_call["seen_fingerprints"] == {"accepted"}
    assert lifecycle_call["scan_summary"]["coverage_complete"] is False
    assert lifecycle_call["scan_summary"]["coverage_comparable"] is False
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_completion_rejects_duplicate_or_unknown_scanners():
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        scan_type="secrets",
        status=ScanStatus.RUNNING,
        current_attempt_id=None,
        execution_revision=0,
    )
    db = AsyncMock()
    db.execute.side_effect = [_result(scan), _result(None)]
    service = ScanCompletionService(db)

    duplicate = _completion_request()
    scan.current_attempt_id = str(duplicate.winning_attempt_id)
    scan.execution_revision = duplicate.execution_revision
    duplicate.scanner_runs.append(duplicate.scanner_runs[0].model_copy())
    with pytest.raises(ScanCompletionConflict, match="duplicate"):
        await service.complete(uuid4(), uuid4(), duplicate)

    db.execute.side_effect = [_result(scan), _result(None)]
    unknown = _completion_request()
    scan.current_attempt_id = str(unknown.winning_attempt_id)
    scan.execution_revision = unknown.execution_revision
    unknown.scanner_runs[0].scanner_name = "semgrep"
    with pytest.raises(ScanCompletionConflict, match="unknown"):
        await service.complete(uuid4(), uuid4(), unknown)


@pytest.mark.asyncio
async def test_completion_replay_requires_same_payload():
    scan_id = str(uuid4())
    attempt_id = uuid4()
    receipt = SimpleNamespace(
        scan_id=scan_id,
        winning_attempt_id=str(attempt_id),
        execution_revision=1,
        evidence_digest=scan_completion.canonical_evidence_digest(
            _completion_request(fingerprint="same", attempt_id=attempt_id)
        ),
        terminal_status="completed",
        inserted_findings=1,
        updated_findings=0,
        scanner_runs_total=1,
        scanner_runs_complete=True,
        response_json={"marker": "accepted"},
    )
    scan = SimpleNamespace(
        id=scan_id,
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        scan_type="secrets",
        status=ScanStatus.COMPLETED,
        current_attempt_id=str(attempt_id),
        execution_revision=1,
    )
    db = AsyncMock()
    db.execute.side_effect = [_result(scan), _result(receipt)]
    request = _completion_request(fingerprint="same", attempt_id=attempt_id)

    response = await ScanCompletionService(db).complete(uuid4(), uuid4(), request)
    assert response["replayed"] is True
    assert response["marker"] == "accepted"
    db.commit.assert_not_awaited()

    db.execute.side_effect = [_result(scan), _result(receipt)]
    changed = _completion_request(fingerprint="changed", attempt_id=attempt_id)
    with pytest.raises(CompletionPayloadConflict):
        await ScanCompletionService(db).complete(uuid4(), uuid4(), changed)


@pytest.mark.asyncio
async def test_completion_rejects_stale_attempt_before_mutation():
    scan = SimpleNamespace(
        id=str(uuid4()),
        project_id=str(uuid4()),
        repository_id=str(uuid4()),
        scan_type="secrets",
        status=ScanStatus.RUNNING,
        current_attempt_id=str(uuid4()),
        execution_revision=4,
    )
    db = AsyncMock()
    db.execute.side_effect = [_result(scan), _result(None)]

    with pytest.raises(CompletionSuperseded):
        await ScanCompletionService(db).complete(uuid4(), uuid4(), _completion_request())

    db.add.assert_not_called()
    db.rollback.assert_awaited_once()
