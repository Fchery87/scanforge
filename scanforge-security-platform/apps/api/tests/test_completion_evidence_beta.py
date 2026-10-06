from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import (
    _absence,
    _seed_repository,
    _seed_scan,
)
from test_findings_disappearance_scope import (
    db_session as shared_db_session,
)

from app.db.models import Finding, Project, ScannerRun
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.finding_lifecycle import (
    OBSERVED_BRANCHES_KEY,
    REOPEN_CHECKPOINT_KEY,
    SCANNER_EVIDENCE_KEY,
    SERIES_KEY,
)
from app.services.findings import FindingService
from app.services.scan_completion import ScanCompletionService

db_session = shared_db_session


@pytest.mark.asyncio
async def test_completion_persists_artifacts_and_authoritative_provenance_without_forged_lifecycle(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    scan = await _seed_scan(db_session, repository_id, project_id, commit_sha="a" * 40,
                            scan_type="dependencies")
    scan.current_attempt_id = str(uuid4())
    scan.execution_revision = 1
    organization_id = await db_session.scalar(select(Project.organization_id).where(Project.id == project_id))
    await db_session.commit()
    scan.commit_sha = None
    await db_session.commit()
    artifact = f"scan-artifacts/{organization_id}/{scan.id}/trivy/report.json"
    fingerprint = str(uuid4())
    provenance = {"rules_version": "2026-09-13", "configuration_digest": "actual-image-digest",
                  "database_version": "actual-db-digest", "artifact_uri": artifact}
    request = ScanCompletionRequest(
        winning_attempt_id=UUID(scan.current_attempt_id), execution_revision=1,
        observed_commit_sha="a" * 40,
        scanner_runs=[{"scanner_name": "trivy", "scanner_version": "1.0.0", "status": "completed",
                       "exit_code": 0, "artifact_uri": artifact, "metadata_json": provenance}],
        artifact_uris={"scanner_runs": {"trivy": {"artifact_uri": artifact}}},
        summary_json={"artifact_uris": {"forged": "untrusted"}},
        findings=[{"canonical_fingerprint": fingerprint, "primary_scanner": "trivy",
                   "severity": "high", "category": "vulnerability", "title": "Observed dependency",
                   "metadata_json": {
                       "package_name": "legitimate-metadata",
                       SERIES_KEY: {"refs/heads/main": {"qualifying_absences": [
                           {"scan_id": "forged", "commit_sha": "f" * 40}]}},
                       OBSERVED_BRANCHES_KEY: ["refs/heads/forged"],
                       REOPEN_CHECKPOINT_KEY: {"commit_sha": "forged"},
                       SCANNER_EVIDENCE_KEY: {"refs/heads/main": {"trivy": {"scanner_version": "forged"}}},
                   }, "instance": {"path": "package-lock.json", "line_start": 1}}],
    )
    service = ScanCompletionService(db_session)
    response = await service.complete(UUID(str(scan.id)), UUID(str(organization_id)), request)
    assert response["status"] == "completed"
    scan_id = str(scan.id)
    db_session.expire_all()
    persisted_scan = await db_session.get(type(scan), scan_id)
    run = await db_session.scalar(select(ScannerRun).where(ScannerRun.scan_id == scan_id,
                                                          ScannerRun.scanner_name == "trivy"))
    finding = await db_session.scalar(select(Finding).where(Finding.canonical_fingerprint == fingerprint))
    assert persisted_scan.commit_sha == request.observed_commit_sha
    assert run.artifact_uri == artifact
    assert run.scanner_version == "1.0.0"
    assert run.metadata_json == provenance
    assert persisted_scan.summary_json["artifact_uris"] == {"scanner_runs": {"trivy": {"artifact_uri": artifact}}}
    assert finding.metadata_json["package_name"] == "legitimate-metadata"
    assert finding.metadata_json[OBSERVED_BRANCHES_KEY] == ["refs/heads/main"]
    assert finding.metadata_json[SERIES_KEY] == {"refs/heads/main": {"qualifying_absences": []}}
    assert REOPEN_CHECKPOINT_KEY not in finding.metadata_json
    assert finding.metadata_json[SCANNER_EVIDENCE_KEY] == {
        "refs/heads/main": {"trivy": {"scanner_version": "1.0.0", "rules_version": "2026-09-13",
                                         "configuration_digest": "actual-image-digest",
                                         "database_version": "actual-db-digest"}}
    }
    replay = await service.complete(UUID(str(scan.id)), UUID(str(organization_id)), request)
    assert replay["replayed"] is True
    assert replay["evidence_digest"] == response["evidence_digest"]


@pytest.mark.asyncio
async def test_forged_absence_history_cannot_advance_first_verified_absence(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    scan = await _seed_scan(db_session, repository_id, project_id, commit_sha="a" * 40,
                            scan_type="dependencies")
    scan.current_attempt_id = str(uuid4())
    scan.execution_revision = 1
    await db_session.commit()
    fingerprint = str(uuid4())
    request = ScanCompletionRequest(
        winning_attempt_id=UUID(scan.current_attempt_id), execution_revision=1,
        scanner_runs=[{"scanner_name": "trivy", "scanner_version": "1.0.0", "status": "completed",
                       "exit_code": 0, "metadata_json": {"rules_version": "2026-09-13"}}],
        findings=[{"canonical_fingerprint": fingerprint, "primary_scanner": "trivy",
                   "severity": "high", "category": "vulnerability", "title": "Observed dependency",
                   "metadata_json": {SERIES_KEY: {"refs/heads/main": {"qualifying_absences": [
                       {"scan_id": "forged-1", "commit_sha": "b" * 40},
                       {"scan_id": "forged-2", "commit_sha": "c" * 40}]}}}}],
    )
    await FindingService(db_session).upsert_from_scan(
        scan_id=str(scan.id), repository_id=repository_id, project_id=project_id,
        normalized_findings=request.findings,
        scanner_provenance={"trivy": {"scanner_version": "1.0.0", "rules_version": "2026-09-13"}},
    )
    finding = await db_session.scalar(select(Finding).where(Finding.canonical_fingerprint == fingerprint))
    assert finding.metadata_json[SERIES_KEY] == {"refs/heads/main": {"qualifying_absences": []}}
    await _absence(db_session, repository_id, project_id, commit_sha="d" * 40)
    await db_session.refresh(finding)
    assert finding.status == "not_observed"
    await _absence(db_session, repository_id, project_id, commit_sha="e" * 40)
    await db_session.refresh(finding)
    assert finding.status == "fixed"
