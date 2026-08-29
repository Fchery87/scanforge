from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import internal
from app.api.v1.routes.internal import require_scan_access
from app.schemas.scans import ScanProgressUpdate
from app.middleware import service_auth
from app.services.worker_identities import (
    WorkerIdentityService,
    WorkerPrincipal,
    hash_worker_credential,
)


def test_worker_credential_hash_is_keyed_and_deterministic():
    credential = "worker-secret"
    assert hash_worker_credential(credential, "pepper") == hash_worker_credential(credential, "pepper")
    assert hash_worker_credential(credential, "pepper") != hash_worker_credential(credential, "other")
    assert credential not in hash_worker_credential(credential, "pepper")


@pytest.mark.asyncio
async def test_valid_worker_credential_returns_scoped_principal(monkeypatch):
    worker_id = uuid4()
    organization_id = uuid4()
    identity = SimpleNamespace(
        id=worker_id,
        organization_id=str(organization_id),
        capabilities_json=["scans:read"],
        disabled_at=None,
        last_seen_at=None,
    )
    result = Mock()
    result.scalar_one_or_none.return_value = identity
    db = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock())
    monkeypatch.setattr("app.services.worker_identities.settings.WORKER_CREDENTIAL_PEPPER", "pepper")

    principal = await WorkerIdentityService(db).authenticate("credential")

    assert principal == WorkerPrincipal(worker_id, organization_id, frozenset({"scans:read"}))
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_or_disabled_worker_credential_is_rejected(monkeypatch):
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result), commit=AsyncMock())
    monkeypatch.setattr("app.services.worker_identities.settings.WORKER_CREDENTIAL_PEPPER", "pepper")

    assert await WorkerIdentityService(db).authenticate("unknown") is None


@pytest.mark.asyncio
async def test_unconfigured_worker_auth_returns_503(monkeypatch):
    monkeypatch.setattr(service_auth.settings, "WORKER_CREDENTIAL_PEPPER", "")
    with pytest.raises(HTTPException) as exc:
        await service_auth.require_service_auth("credential")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_scheduler_auth_rejects_worker_header_and_accepts_scheduler_header(monkeypatch):
    monkeypatch.setattr(service_auth.settings, "SCHEDULER_API_KEY", "scheduler-secret")

    with pytest.raises(HTTPException) as exc:
        await service_auth.require_scheduler_auth(None)
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException) as exc:
        await service_auth.require_scheduler_auth("worker-secret")
    assert exc.value.status_code == 401

    assert await service_auth.require_scheduler_auth("scheduler-secret") is None


@pytest.mark.asyncio
async def test_unconfigured_scheduler_auth_returns_503(monkeypatch):
    monkeypatch.setattr(service_auth.settings, "SCHEDULER_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        await service_auth.require_scheduler_auth("credential")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_canceled_scan_rejects_later_progress_write():
    scan_id = uuid4()
    org_id = uuid4()
    scan = SimpleNamespace(status=internal.ScanStatus.CANCELED, error_message=None, summary_json=None)
    principal = WorkerPrincipal(uuid4(), org_id, frozenset({"scans:write"}))
    row = Mock()
    row.scalar_one_or_none.return_value = scan
    db = SimpleNamespace(execute=AsyncMock(return_value=row))

    with pytest.raises(HTTPException) as exc:
        await internal.update_scan_status_internal(
            scan_id=scan_id,
            data=ScanProgressUpdate(status="running"),
            principal=principal,
            db=db,
        )

    assert exc.value.status_code == 409
    assert scan.status == internal.ScanStatus.CANCELED


@pytest.mark.asyncio
async def test_worker_cannot_read_scan_from_another_organization():
    principal = WorkerPrincipal(uuid4(), uuid4(), frozenset({"scans:read"}))
    result = Mock()
    result.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as exc:
        await require_scan_access(uuid4(), principal, db)
    assert exc.value.status_code == 404
