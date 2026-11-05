"""Completion is derived only from validated canonical evidence (P1.7, #44).

Seam: ``ScanCompletionService.complete`` against a real (SQLite) database, plus
the request schema that gates it.  Fixtures are shared with the R04 completion
boundary tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from test_r04_postgres_completion_red import (  # noqa: F401  (db_session is a fixture)
    _count,
    _seed_scan,
    completion_request,
    db_session,
)

from app.db.enums import ScanStatus
from app.db.models import (
    AuditLog,
    Finding,
    FindingReference,
    Scan,
    ScannerRun,
)
from app.db.models.scan import ScanCompletionReceipt
from app.schemas.canonical_findings import CanonicalFindingCandidate
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.evidence_contract import (
    EvidenceContractError,
    ScannerOutsideContractError,
    UnbackedFindingScannerError,
)
from app.services.scan_completion import ScanCompletionService


def _finding(scanner: str | None = "trivy", **overrides) -> CanonicalFindingCandidate:
    values = {
        "canonical_fingerprint": f"fp-{uuid4()}",
        "severity": "high",
        "category": "vulnerability",
        "title": "Vulnerable dependency",
        "primary_scanner": scanner,
        "instance": {"path": "requirements.txt"},
        "references": [{"type": "advisory", "value": "CVE-2026-0001"}],
    }
    values.update(overrides)
    return CanonicalFindingCandidate.model_validate(values)


async def _everything_written(session) -> dict[str, int]:
    return {
        "runs": await _count(session, ScannerRun),
        "findings": await _count(session, Finding),
        "references": await _count(session, FindingReference),
        "audit": await _count(session, AuditLog),
        "receipts": await _count(session, ScanCompletionReceipt),
    }


@pytest.mark.asyncio
async def test_forged_worker_summary_cannot_change_counts(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(
        findings=[_finding()],
        summary_json={
            "finding_count": 0,
            "critical_count": 0,
            "high_count": 0,
            "scanner_health": {"complete": False, "failed": ["trivy"]},
        },
    )

    response = await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    assert response["scanner_runs_complete"] is True
    stored = (await db_session.get(Scan, scan_id)).summary_json
    assert stored["finding_count"] == 1
    assert stored["high_count"] == 1
    assert stored["critical_count"] == 0
    assert stored["scanner_health"]["complete"] is True
    assert stored["severity_counts"]["high"] == 1


@pytest.mark.asyncio
async def test_forged_worker_counts_with_no_findings_are_zeroed(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(
        summary_json={"finding_count": 999, "critical_count": 50, "high_count": 7}
    )

    await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    stored = (await db_session.get(Scan, scan_id)).summary_json
    assert (stored["finding_count"], stored["critical_count"], stored["high_count"]) == (0, 0, 0)


@pytest.mark.asyncio
async def test_finding_from_a_scanner_with_no_run_is_rejected_and_nothing_is_written(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding(scanner="gitleaks")])

    with pytest.raises(UnbackedFindingScannerError) as excinfo:
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    assert isinstance(excinfo.value, EvidenceContractError)
    assert excinfo.value.code == "unbacked_finding_scanner"
    await db_session.rollback()
    assert all(v == 0 for v in (await _everything_written(db_session)).values())
    assert (await db_session.get(Scan, scan_id)).status == ScanStatus.RUNNING


@pytest.mark.asyncio
async def test_finding_from_a_failed_scanner_run_is_rejected(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding(scanner="trivy")])
    data.scanner_runs[0].status = "failed"
    data.scanner_runs[0].outcome_status = "failed"

    with pytest.raises(UnbackedFindingScannerError):
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)


@pytest.mark.asyncio
async def test_scanner_run_outside_the_execution_contract_is_rejected(db_session):
    scan, org_id = await _seed_scan(db_session)  # contract expects only trivy
    scan_id = str(scan.id)
    data = completion_request()
    data.scanner_runs.append(data.scanner_runs[0].model_copy(update={"scanner_name": "gitleaks"}))

    with pytest.raises(ScannerOutsideContractError) as excinfo:
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    assert excinfo.value.code == "scanner_outside_contract"
    await db_session.rollback()
    assert all(v == 0 for v in (await _everything_written(db_session)).values())


def test_unknown_finding_and_reference_fields_are_rejected():
    base = {
        "winning_attempt_id": str(uuid4()),
        "execution_revision": 1,
    }
    finding = {"canonical_fingerprint": "fp-1", "primary_scanner": "trivy"}

    with pytest.raises(ValidationError):
        ScanCompletionRequest.model_validate({**base, "findings": [{**finding, "status": "fixed"}]})
    with pytest.raises(ValidationError):
        ScanCompletionRequest.model_validate(
            {**base, "findings": [{**finding, "references": [{"type": "x", "value": "y", "trusted": True}]}]}
        )
    # Scanner-specific instance detail stays allowed (rule_id, commit, ...).
    ScanCompletionRequest.model_validate(
        {**base, "findings": [{**finding, "instance": {"path": "a", "rule_id": "r"}}]}
    )


@pytest.mark.asyncio
async def test_completion_commits_evidence_references_audit_and_receipt_together(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding()])

    await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    written = await _everything_written(db_session)
    assert written == {"runs": 1, "findings": 1, "references": 1, "audit": 1, "receipts": 1}
    audit = (await db_session.execute(select(AuditLog))).scalar_one()
    assert audit.action == "scan_completed"
    assert audit.target_type == "scan"
    assert audit.target_id == scan_id
    assert audit.organization_id == str(org_id)
    assert audit.metadata_json["evidence_digest"] == data_digest(data)
    assert audit.metadata_json["inserted_findings"] == 1


def data_digest(data) -> str:
    from app.services.evidence_contract import compute_canonical_evidence_digest

    return compute_canonical_evidence_digest(data)


@pytest.mark.asyncio
async def test_failure_at_final_commit_leaves_no_evidence_references_audit_or_receipt(
    db_session, monkeypatch
):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding()])

    async def exploding_commit():
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(db_session, "commit", exploding_commit)
    with pytest.raises(RuntimeError, match="injected commit failure"):
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)
    monkeypatch.undo()

    assert all(v == 0 for v in (await _everything_written(db_session)).values())
    refreshed = await db_session.get(Scan, scan_id)
    assert refreshed.status == ScanStatus.RUNNING
    assert refreshed.summary_json is None

    # The same evidence then commits cleanly: nothing half-applied blocks retry.
    await ScanCompletionService(db_session).complete(scan_id, org_id, data)
    assert (await _everything_written(db_session))["receipts"] == 1


@pytest.mark.asyncio
async def test_failure_while_writing_the_receipt_rolls_back_everything(db_session, monkeypatch):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding()])
    real_add = db_session.add

    def add_failing_on_receipt(obj, *args, **kwargs):
        if isinstance(obj, ScanCompletionReceipt):
            raise RuntimeError("injected receipt failure")
        return real_add(obj, *args, **kwargs)

    monkeypatch.setattr(db_session, "add", add_failing_on_receipt)
    with pytest.raises(RuntimeError, match="injected receipt failure"):
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)
    monkeypatch.undo()

    assert all(v == 0 for v in (await _everything_written(db_session)).values())


@pytest.mark.asyncio
async def test_identical_replay_returns_original_and_writes_no_second_audit(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request(findings=[_finding()])
    service = ScanCompletionService(db_session)
    first = await service.complete(scan_id, org_id, data)

    replay = await service.complete(scan_id, org_id, data)

    assert replay["replayed"] is True
    assert replay["evidence_digest"] == first["evidence_digest"]
    assert await _count(db_session, AuditLog) == 1
    total = (await db_session.execute(select(func.count()).select_from(Finding))).scalar_one()
    assert total == 1


def test_identical_completion_replay_is_accepted_after_the_lease_has_expired():
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.v1.routes.internal import ExecutionAttemptIdentity, assert_live_execution_authority
    from app.middleware.service_auth import WorkerPrincipal

    worker_id, attempt, incarnation = uuid4(), str(uuid4()), str(uuid4())
    principal = WorkerPrincipal(worker_id=worker_id, organization_id=uuid4(), capabilities=frozenset())
    scan = SimpleNamespace(
        current_attempt_id=attempt,
        execution_revision=2,
        worker_incarnation_id=incarnation,
        lease_owner=str(worker_id),
        lease_expires_at=datetime.now(UTC) - timedelta(hours=1),
        status=ScanStatus.COMPLETED,
    )
    identity = ExecutionAttemptIdentity(attempt, 2, incarnation)

    # A terminal scan's frozen receipt may be replayed after the lease lapsed ...
    assert_live_execution_authority(scan, principal, identity, allow_terminal=True)

    # ... but never by a superseded attempt, nor into a live scan with a dead lease.
    stale = ExecutionAttemptIdentity(str(uuid4()), 2, incarnation)
    with pytest.raises(HTTPException) as stale_error:
        assert_live_execution_authority(scan, principal, stale, allow_terminal=True)
    assert stale_error.value.detail["code"] == "stale_attempt"

    scan.status = ScanStatus.RUNNING
    with pytest.raises(HTTPException) as live_error:
        assert_live_execution_authority(scan, principal, identity, allow_terminal=True)
    assert live_error.value.detail["code"] == "lease_expired"
