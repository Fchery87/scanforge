from uuid import UUID, uuid4

import pytest
from test_findings_disappearance_scope import _seed_repository
from test_findings_disappearance_scope import db_session as _db_session

from app.api.v1.routes import internal
from app.db.models import Project, Scan, ScanCompletionReceipt, ScannerRun
from app.middleware.service_auth import WorkerPrincipal

db_session = _db_session


async def execution(db):
    repository_id, project_id = await _seed_repository(db)
    project = await db.get(Project, project_id)
    scan = Scan(
        id=str(uuid4()), repository_id=repository_id, project_id=project_id,
        status=internal.ScanStatus.QUEUED, scan_type="secrets", branch_name="main", trigger_type="manual",
    )
    db.add(scan)
    await db.commit()
    principal = WorkerPrincipal(
        worker_id=uuid4(), organization_id=UUID(project.organization_id),
        capabilities=frozenset({"scans:read", "scans:write", "findings:write"}),
    )
    return scan, principal


@pytest.mark.asyncio
async def test_claim_issues_attempt_and_status_polls_preserve_it(db_session):
    scan, principal = await execution(db_session)
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    for _ in range(3):
        polled = await internal.get_scan_execution_context(UUID(scan.id), principal, db_session)
        assert polled["attempt_id"] == claimed["attempt_id"]
        assert polled["execution_revision"] == 1
    reclaimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    assert reclaimed["attempt_id"] != claimed["attempt_id"]
    assert reclaimed["execution_revision"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["completed"])
async def test_terminal_scan_rejects_claim_and_progress(db_session, state):
    scan, principal = await execution(db_session)
    scan.status = internal.ScanStatus(state)
    await db_session.commit()
    with pytest.raises(internal.HTTPException) as error:
        await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    assert error.value.status_code == 409
    with pytest.raises(internal.HTTPException) as error:
        await internal.create_scanner_run(
            UUID(scan.id), internal.CreateScannerRunRequest(
                scanner_name="gitleaks", attempt_id=uuid4(), execution_revision=1,
            ), principal, db_session,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_superseded_progress_rejected(db_session):
    scan, principal = await execution(db_session)
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    with pytest.raises(internal.HTTPException) as error:
        await internal.update_scan_status_internal(
            UUID(scan.id), internal.ScanProgressUpdate(
                status="failed", attempt_id=claimed["attempt_id"], execution_revision=1,
            ), principal, db_session,
        )
    assert error.value.status_code == 409
    assert scan.status == internal.ScanStatus.RUNNING


@pytest.mark.asyncio
async def test_progress_cannot_publish_artifacts_or_provenance(db_session):
    scan, principal = await execution(db_session)
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    db_session.add(ScannerRun(
        id=str(uuid4()), scan_id=scan.id, scanner_name="gitleaks", status=internal.ScanStatus.RUNNING,
    ))
    await db_session.commit()
    created = await internal.create_scanner_run(
        UUID(scan.id), internal.CreateScannerRunRequest(
            scanner_name="gitleaks", attempt_id=claimed["attempt_id"], execution_revision=1,
        ), principal, db_session,
    )
    with pytest.raises(internal.HTTPException) as error:
        await internal.update_scanner_run(
            UUID(created["id"]), internal.UpdateScannerRunRequest(
                artifact_uri="scan-artifacts/other-org/scan/trivy/raw.json",
                attempt_id=claimed["attempt_id"], execution_revision=1,
            ), principal, db_session,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_legacy_findings_endpoint_cannot_mutate_evidence(db_session):
    scan, principal = await execution(db_session)
    with pytest.raises(internal.HTTPException) as error:
        await internal.persist_scan_findings(
            UUID(scan.id), internal.PersistFindingsRequest(findings=[]), principal, db_session,
        )
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_canceled_claim_returns_durable_cancellation_without_new_attempt(db_session):
    scan, principal = await execution(db_session)
    scan.status = internal.ScanStatus.CANCELED
    await db_session.commit()
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    assert claimed["status"] == "canceled"
    assert claimed["attempt_id"] is None
    assert claimed["execution_revision"] == 0


@pytest.mark.asyncio
async def test_completed_claim_with_receipt_preserves_winning_attempt(db_session):
    scan, principal = await execution(db_session)
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    scan.status = internal.ScanStatus.COMPLETED
    db_session.add(ScanCompletionReceipt(
        scan_id=scan.id, winning_attempt_id=claimed["attempt_id"], execution_revision=1,
        evidence_digest="a" * 64, terminal_status="completed",
    ))
    await db_session.commit()
    replayed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    assert replayed["status"] == "completed"
    assert replayed["attempt_id"] == claimed["attempt_id"]
    assert replayed["execution_revision"] == 1


@pytest.mark.asyncio
async def test_terminal_scan_cannot_get_new_upload_url(db_session):
    scan, principal = await execution(db_session)
    claimed = await internal.claim_scan_execution(UUID(scan.id), principal, db_session)
    scan.status = internal.ScanStatus.COMPLETED
    await db_session.commit()
    with pytest.raises(internal.HTTPException) as error:
        await internal.create_artifact_upload_url(
            UUID(scan.id), internal.ArtifactUploadRequest(
                scanner_name="trivy", filename="report.json", size_bytes=2,
                attempt_id=claimed["attempt_id"], execution_revision=1,
            ), principal, db_session,
        )
    assert error.value.status_code == 409
