from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import Project, Scan
from app.services.scans import ScanAuthorizationError, ScanService


@pytest.mark.asyncio
async def test_delete_scan_allows_non_completed_statuses():
    scan_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(id=scan_id, status=ScanStatusEnum.FAILED)

    db = AsyncMock()
    db.delete = AsyncMock()
    service = ScanService(db)
    service.get_by_id = AsyncMock(return_value=scan)

    deleted = await service.delete(scan_id, user_id)

    assert deleted is scan
    assert scan.deleted_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_scan_rejects_completed_scans():
    scan_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(id=scan_id, status=ScanStatusEnum.COMPLETED)

    db = AsyncMock()
    db.delete = Mock()
    service = ScanService(db)
    service.get_by_id = AsyncMock(return_value=scan)

    with pytest.raises(ValueError, match="completed scans"):
        await service.delete(scan_id, user_id)

    db.delete.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_scan_returns_none_when_user_cannot_access_scan():
    scan_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = ScanService(db)
    service.get_by_id = AsyncMock(return_value=None)

    canceled = await service.cancel(scan_id, user_id=user_id)

    assert canceled is None
    db.commit.assert_not_awaited()


async def _scans_db_with_org(scan, project):
    db = AsyncMock()

    async def get(model, _obj_id):
        if model is Scan:
            return scan
        if model is Project:
            return project
        raise AssertionError(f"unexpected model {model}")

    db.get = AsyncMock(side_effect=get)
    return db


async def test_update_status_rejects_principal_from_other_org():
    scan_id = uuid4()
    principal_org_id = uuid4()
    scan_org_id = uuid4()

    scan = SimpleNamespace(
        id=scan_id,
        project_id=str(uuid4()),
        status=ScanStatusEnum.RUNNING,
        error_message=None,
        summary_json=None,
    )
    project = SimpleNamespace(organization_id=str(scan_org_id))
    db = await _scans_db_with_org(scan, project)

    service = ScanService(db)

    with pytest.raises(ScanAuthorizationError) as excinfo:
        await service.update_status(
            scan_id,
            ScanStatusEnum.FAILED,
            error_message="worker failed",
            caller_organization_id=principal_org_id,
        )

    assert ScanAuthorizationError.code == "scan_org_mismatch"
    assert "organization" in str(excinfo.value)
    assert scan.status is ScanStatusEnum.RUNNING
    assert scan.error_message is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


async def test_update_status_allows_org_matched_principal():
    scan_id = uuid4()
    org_id = uuid4()

    scan = SimpleNamespace(
        id=scan_id,
        project_id=str(uuid4()),
        status=ScanStatusEnum.RUNNING,
        error_message=None,
        summary_json=None,
    )
    project = SimpleNamespace(organization_id=str(org_id))
    db = await _scans_db_with_org(scan, project)

    service = ScanService(db)

    result = await service.update_status(
        scan_id,
        ScanStatusEnum.FAILED,
        error_message="worker failed",
        summary_json={"totals": {"findings": 1}},
        caller_organization_id=org_id,
    )

    assert result is scan
    assert scan.status is ScanStatusEnum.FAILED
    assert scan.error_message == "worker failed"
    assert scan.summary_json == {"totals": {"findings": 1}}
    db.commit.assert_awaited_once()
