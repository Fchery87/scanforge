from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import Project, Repository, Scan, ScannerRun
from app.schemas.canonical_findings import CanonicalFindingCandidate, CanonicalFindingInstance
from app.services.findings import FindingService
from app.services.scans import ScanAuthorizationError, ScanService


async def _org_db(mapping):
    db = AsyncMock()
    db.add = Mock()

    async def get(model, _obj_id):
        if model in mapping:
            return mapping[model]
        raise AssertionError(f"unexpected model {model}")

    db.get = AsyncMock(side_effect=get)
    return db


# --- POST /internal/scans/{scan_id}/scanner-runs (ScanService.create_scanner_run) ---


@pytest.mark.asyncio
async def test_create_scanner_run_rejects_principal_from_other_org():
    scan_id = uuid4()
    principal_org_id = uuid4()
    scan_org_id = uuid4()

    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(scan_org_id))
    db = await _org_db({Scan: scan, Project: project})

    with pytest.raises(ScanAuthorizationError) as excinfo:
        await ScanService(db).create_scanner_run(
            scan_id,
            "trivy",
            scanner_version="0.50.0",
            status=ScanStatusEnum.RUNNING,
            caller_organization_id=principal_org_id,
        )

    assert ScanAuthorizationError.code == "scan_org_mismatch"
    assert "organization" in str(excinfo.value)
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_scanner_run_allows_org_matched_principal():
    scan_id = uuid4()
    org_id = uuid4()

    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(org_id))
    db = await _org_db({Scan: scan, Project: project})

    run = await ScanService(db).create_scanner_run(
        scan_id,
        "trivy",
        scanner_version="0.50.0",
        status=ScanStatusEnum.RUNNING,
        caller_organization_id=org_id,
    )

    assert run.scan_id == scan_id
    assert run.scanner_name == "trivy"
    assert run.scanner_version == "0.50.0"
    assert run.status is ScanStatusEnum.RUNNING
    db.commit.assert_awaited_once()


# --- PATCH /internal/scanner-runs/{run_id} (ScanService.update_scanner_run) ---


@pytest.mark.asyncio
async def test_update_scanner_run_rejects_principal_from_other_org():
    run_id = uuid4()
    scan_id = uuid4()
    principal_org_id = uuid4()
    scan_org_id = uuid4()

    run = SimpleNamespace(
        id=run_id,
        scan_id=str(scan_id),
        status=ScanStatusEnum.RUNNING,
        duration_ms=None,
        exit_code=None,
        error_message=None,
        artifact_uri=None,
        metadata_json=None,
    )
    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(scan_org_id))
    db = await _org_db({ScannerRun: run, Scan: scan, Project: project})

    with pytest.raises(ScanAuthorizationError) as excinfo:
        await ScanService(db).update_scanner_run(
            run_id,
            ScanStatusEnum.FAILED,
            duration_ms=1200,
            caller_organization_id=principal_org_id,
        )

    assert ScanAuthorizationError.code == "scan_org_mismatch"
    assert "organization" in str(excinfo.value)
    assert run.status is ScanStatusEnum.RUNNING
    assert run.duration_ms is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_scanner_run_allows_org_matched_principal():
    run_id = uuid4()
    scan_id = uuid4()
    org_id = uuid4()

    run = SimpleNamespace(
        id=run_id,
        scan_id=str(scan_id),
        status=ScanStatusEnum.RUNNING,
        duration_ms=None,
        exit_code=None,
        error_message=None,
        artifact_uri=None,
        metadata_json=None,
    )
    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(org_id))
    db = await _org_db({ScannerRun: run, Scan: scan, Project: project})

    updated = await ScanService(db).update_scanner_run(
        run_id,
        ScanStatusEnum.FAILED,
        duration_ms=1200,
        exit_code=1,
        error_message="scanner crashed",
        artifact_uri="scan-artifacts/x/y.json",
        metadata_json={"trivy": {"vulns": 3}},
        caller_organization_id=org_id,
    )

    assert updated is run
    assert run.status is ScanStatusEnum.FAILED
    assert run.duration_ms == 1200
    assert run.exit_code == 1
    assert run.error_message == "scanner crashed"
    assert run.artifact_uri == "scan-artifacts/x/y.json"
    assert run.metadata_json == {"trivy": {"vulns": 3}}
    db.commit.assert_awaited_once()


# --- POST /internal/scans/{scan_id}/artifacts/upload-url (ScanService.authorize_scan_access) ---


@pytest.mark.asyncio
async def test_artifact_upload_boundary_rejects_principal_from_other_org():
    scan_id = uuid4()
    principal_org_id = uuid4()
    scan_org_id = uuid4()

    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(scan_org_id))
    db = await _org_db({Scan: scan, Project: project})

    with pytest.raises(ScanAuthorizationError) as excinfo:
        await ScanService(db).authorize_scan_access(
            scan_id,
            caller_organization_id=principal_org_id,
        )

    assert ScanAuthorizationError.code == "scan_org_mismatch"
    assert "organization" in str(excinfo.value)


@pytest.mark.asyncio
async def test_artifact_upload_boundary_allows_org_matched_principal():
    scan_id = uuid4()
    org_id = uuid4()

    scan = SimpleNamespace(id=scan_id, project_id=str(uuid4()))
    project = SimpleNamespace(organization_id=str(org_id))
    db = await _org_db({Scan: scan, Project: project})

    result = await ScanService(db).authorize_scan_access(
        scan_id,
        caller_organization_id=org_id,
    )

    assert result == (scan, project)


# --- POST /internal/scans/{scan_id}/findings (FindingService.upsert_from_scan) ---


async def _findings_db(project, repository):
    db = AsyncMock()
    db.add = Mock()

    async def get(model, _obj_id):
        if model is Repository:
            return repository
        if model is Project:
            return project
        raise AssertionError(f"unexpected model {model}")

    db.get = AsyncMock(side_effect=get)
    empty_result = Mock()
    empty_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=empty_result)
    db.scalar = AsyncMock(return_value=None)
    return db


@pytest.mark.asyncio
async def test_upsert_findings_rejects_principal_from_other_org():
    scan_id = uuid4()
    project_id = uuid4()
    principal_org_id = uuid4()
    scan_org_id = uuid4()

    project = SimpleNamespace(id=project_id, organization_id=str(scan_org_id))
    repository = SimpleNamespace(id=uuid4(), importance="normal")
    db = await _findings_db(project, repository)

    with pytest.raises(ScanAuthorizationError) as excinfo:
        await FindingService(db).upsert_from_scan(
            scan_id=str(scan_id),
            repository_id=str(repository.id),
            project_id=str(project_id),
            normalized_findings=[
                CanonicalFindingCandidate(
                    canonical_fingerprint="fp-1",
                    severity="high",
                    category="secret",
                    instance=CanonicalFindingInstance(path="config.py", line_start=7),
                )
            ],
            caller_organization_id=principal_org_id,
        )

    assert ScanAuthorizationError.code == "scan_org_mismatch"
    assert "organization" in str(excinfo.value)
    db.execute.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_findings_allows_org_matched_principal():
    scan_id = uuid4()
    project_id = uuid4()
    org_id = uuid4()

    project = SimpleNamespace(id=project_id, organization_id=str(org_id))
    repository = SimpleNamespace(id=uuid4(), importance="normal")
    db = await _findings_db(project, repository)

    new_count, updated_count = await FindingService(db).upsert_from_scan(
        scan_id=str(scan_id),
        repository_id=str(repository.id),
        project_id=str(project_id),
        normalized_findings=[
            CanonicalFindingCandidate(
                canonical_fingerprint="fp-1",
                severity="high",
                category="secret",
                instance=CanonicalFindingInstance(path="config.py", line_start=7),
            )
        ],
        caller_organization_id=org_id,
    )

    assert (new_count, updated_count) == (1, 0)
    db.add.assert_called()
    db.commit.assert_awaited_once()
