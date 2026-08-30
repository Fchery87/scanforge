from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.middleware.service_auth import WorkerPrincipal, require_service_auth
from app.services.worker_identities import WorkerIdentityService


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _IdentityDb:
    def __init__(self, identity=None):
        self.identity = identity
        self.added = []
        self.commit = AsyncMock()

    async def execute(self, _statement):
        return _ScalarResult(self.identity)

    def add(self, value):
        self.added.append(value)


@pytest.mark.asyncio
async def test_valid_credential_returns_organization_scoped_worker_principal(monkeypatch):
    credential = "worker-credential"
    worker_id = uuid4()
    organization_id = uuid4()
    service = WorkerIdentityService(_IdentityDb(), pepper="test-pepper")
    identity = SimpleNamespace(
        id=worker_id,
        organization_id=organization_id,
        credential_hash=service.hash_credential(credential),
        capabilities_json=["scan:execute"],
        disabled_at=None,
        last_seen_at=None,
    )
    db = _IdentityDb(identity)
    monkeypatch.setattr("app.middleware.service_auth.settings.WORKER_CREDENTIAL_PEPPER", "test-pepper")

    principal = await require_service_auth(x_service_key=credential, db=db)

    assert principal == WorkerPrincipal(
        worker_id=worker_id,
        organization_id=organization_id,
        capabilities=frozenset({"scan:execute"}),
    )
    assert isinstance(identity.last_seen_at, datetime)
    assert identity.last_seen_at.tzinfo is UTC
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(("credential", "disabled"), [("unknown", False), ("valid", True), ("", False)])
async def test_invalid_disabled_or_malformed_credentials_are_rejected(monkeypatch, credential, disabled):
    service = WorkerIdentityService(_IdentityDb(), pepper="test-pepper")
    identity = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        credential_hash=service.hash_credential("valid"),
        capabilities_json=[],
        disabled_at=object() if disabled else None,
        last_seen_at=None,
    )
    monkeypatch.setattr("app.middleware.service_auth.settings.WORKER_CREDENTIAL_PEPPER", "test-pepper")

    db = _IdentityDb(identity)
    with pytest.raises(HTTPException) as error:
        await require_service_auth(x_service_key=credential, db=db)

    assert error.value.status_code == 401
    assert identity.last_seen_at is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_worker_credential_pepper_is_unavailable(monkeypatch):
    monkeypatch.setattr("app.middleware.service_auth.settings.WORKER_CREDENTIAL_PEPPER", "")

    with pytest.raises(HTTPException) as error:
        await require_service_auth(x_service_key="credential", db=_IdentityDb())

    assert error.value.status_code == 503


def test_worker_identity_creation_stores_only_hmac_credential_hash():
    credential = "plaintext-credential"
    db = _IdentityDb()
    service = WorkerIdentityService(db, pepper="test-pepper")

    identity, generated_credential = service.create_identity(
        organization_id=uuid4(),
        name="private-beta-worker",
        capabilities={"scan:execute"},
        credential=credential,
    )

    assert generated_credential == credential
    assert identity.credential_hash == service.hash_credential(credential)
    assert identity.credential_hash != credential
    assert not hasattr(identity, "credential")
    assert db.added == [identity]


@pytest.mark.asyncio
async def test_rotated_credential_rejects_the_disabled_identity(monkeypatch):
    old_credential = "old-credential"
    service = WorkerIdentityService(_IdentityDb(), pepper="test-pepper")
    old_identity = SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        name="private-beta-worker",
        credential_hash=service.hash_credential(old_credential),
        capabilities_json=["scan:execute", "notifications:write"],
        disabled_at=None,
        last_seen_at=None,
    )

    class Db(_IdentityDb):
        def __init__(self):
            super().__init__()
            self.identities = {old_identity.credential_hash: old_identity}

        async def get(self, _model, _key):
            return old_identity

        async def flush(self):
            return None

        def add(self, identity):
            super().add(identity)
            self.identities[identity.credential_hash] = identity

        async def execute(self, statement):
            credential_hash = next(iter(statement.compile().params.values()))
            return _ScalarResult(self.identities.get(credential_hash))

    db = Db()
    service = WorkerIdentityService(db, pepper="test-pepper")
    _replacement, replacement_credential = await service.rotate_identity(old_identity.id)
    monkeypatch.setattr("app.middleware.service_auth.settings.WORKER_CREDENTIAL_PEPPER", "test-pepper")

    with pytest.raises(HTTPException) as old_error:
        await require_service_auth(x_service_key=old_credential, db=db)
    replacement_principal = await require_service_auth(x_service_key=replacement_credential, db=db)

    assert old_error.value.status_code == 401
    assert replacement_principal.organization_id == old_identity.organization_id
    assert old_identity.disabled_at is not None
