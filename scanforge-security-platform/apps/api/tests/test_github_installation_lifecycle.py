"""P2.5 / #53: GitHub installation and repository lifecycle reconciliation.

Seams under test:
1. The App-level webhook route (`POST /webhooks/github/app`): lifecycle event fixtures
   update or revoke repository authority; the installation binding is the only source of
   authority and foreign installations cannot affect another organization.
2. `RepositoryService.connect`: integration identity is derived from the verified
   organization binding, never from browser-supplied fields.
3. The repository webhook route: ignored/deferred events never poison deduplication of
   later supported deliveries, and revoked repositories receive no scan authority.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.api.v1.routes import webhooks
from app.db.base import Base
from app.db.models import (
    Organization,
    OrganizationIntegration,
    OrganizationMember,
    Project,
    Repository,
    RepositoryIntegration,
    User,
    WebhookDelivery,
)
from app.schemas.repositories import RepositoryConnect
from app.services.repositories import RepositoryAuthorizationError, RepositoryService


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR())

    def bind_processor(self, dialect):
        if dialect.name == "postgresql":
            return None

        def process(value):
            return str(value) if value is not None else None

        return process


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(45)"


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_downcast_postgres_uuid_columns()


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    _downcast_postgres_uuid_columns()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


class _FakeRequest:
    def __init__(self, payload, *, event, delivery):
        self._payload = payload
        self.headers = {"x-github-event": event, "x-github-delivery": delivery}

    async def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _signature_ok(monkeypatch):
    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))


async def _seed(session, *, installation_id="77001", repo_id="900123", owner="acme-sec", name="payments-api"):
    user, org, proj = uuid4(), uuid4(), uuid4()
    session.add_all(
        [
            User(id=user, auth_provider_user_id=f"u-{user}", email=f"{user}@example.com"),
            Organization(id=org, name="Org", slug=f"org-{org}", created_by_user_id=user),
            OrganizationMember(id=str(uuid4()), organization_id=org, user_id=user, role="owner"),
            Project(
                id=proj,
                organization_id=org,
                name="Proj",
                slug=f"proj-{proj}",
                created_by_user_id=user,
            ),
            OrganizationIntegration(
                organization_id=org,
                provider="github",
                installation_id=installation_id,
                account_login=owner,
                account_type="Organization",
            ),
        ]
    )
    await session.flush()
    repo = Repository(
        project_id=proj,
        provider="github",
        external_repo_id=repo_id,
        owner_name=owner,
        repo_name=name,
        full_name=f"{owner}/{name}",
        default_branch="main",
        clone_url=f"https://github.com/{owner}/{name}.git",
        html_url=f"https://github.com/{owner}/{name}",
        is_active=True,
        lifecycle_state="connected",
    )
    session.add(repo)
    await session.flush()
    session.add(
        RepositoryIntegration(
            repository_id=repo.id,
            installation_id=installation_id,
            provider_account_id=owner,
            access_metadata={"verified": True},
        )
    )
    await session.commit()
    return SimpleNamespace(user=user, org=org, proj=proj, repo=repo)


async def _deliver_app_event(session, event, payload, *, delivery=None):
    return await webhooks.github_app_webhook(
        request=_FakeRequest(payload, event=event, delivery=delivery or f"d-{uuid4()}"),
        db=session,
    )


async def _reload(session, repo):
    await session.refresh(repo)
    return repo


# --- 1. lifecycle fixtures -------------------------------------------------


@pytest.mark.asyncio
async def test_installation_deleted_revokes_binding_and_repository_authority(db_session):
    t = await _seed(db_session)

    response = await _deliver_app_event(
        db_session,
        "installation",
        {"action": "deleted", "installation": {"id": 77001, "account": {"login": "acme-sec"}}},
    )

    assert response["status"] == "processed"
    assert (
        await db_session.scalar(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == t.org)
        )
    ) is None
    repo = await _reload(db_session, t.repo)
    assert repo.is_active is False
    assert repo.lifecycle_state == "reauthorization_required"


@pytest.mark.asyncio
async def test_installation_suspend_revokes_and_unsuspend_restores(db_session):
    t = await _seed(db_session)
    payload = {"installation": {"id": 77001}}

    await _deliver_app_event(db_session, "installation", {"action": "suspend", **payload})
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (False, "reauthorization_required")

    await _deliver_app_event(db_session, "installation", {"action": "unsuspend", **payload})
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_unsuspend_does_not_restore_repository_disconnected_by_a_human(db_session):
    t = await _seed(db_session)
    t.repo.is_active = False
    t.repo.lifecycle_state = "disconnected"
    await db_session.commit()

    await _deliver_app_event(db_session, "installation", {"action": "unsuspend", "installation": {"id": 77001}})

    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (False, "disconnected")


@pytest.mark.asyncio
async def test_permission_change_revokes_without_contents_read_and_restores_with_it(db_session):
    t = await _seed(db_session)

    await _deliver_app_event(
        db_session,
        "installation",
        {
            "action": "new_permissions_accepted",
            "installation": {"id": 77001, "permissions": {"metadata": "read"}},
        },
    )
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (False, "reauthorization_required")

    await _deliver_app_event(
        db_session,
        "installation",
        {
            "action": "new_permissions_accepted",
            "installation": {"id": 77001, "permissions": {"metadata": "read", "contents": "read"}},
        },
    )
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_repository_removed_from_installation_revokes_only_that_repository(db_session):
    t = await _seed(db_session)
    other = Repository(
        project_id=t.proj,
        provider="github",
        external_repo_id="900124",
        owner_name="acme-sec",
        repo_name="other",
        full_name="acme-sec/other",
        default_branch="main",
        is_active=True,
        lifecycle_state="connected",
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(RepositoryIntegration(repository_id=other.id, installation_id="77001"))
    await db_session.commit()

    await _deliver_app_event(
        db_session,
        "installation_repositories",
        {
            "action": "removed",
            "installation": {"id": 77001},
            "repositories_removed": [{"id": 900123, "full_name": "acme-sec/payments-api"}],
            "repositories_added": [],
        },
    )

    assert (await _reload(db_session, t.repo)).lifecycle_state == "reauthorization_required"
    assert (await _reload(db_session, other)).lifecycle_state == "connected"

    await _deliver_app_event(
        db_session,
        "installation_repositories",
        {
            "action": "added",
            "installation": {"id": 77001},
            "repositories_added": [{"id": 900123, "full_name": "acme-sec/payments-api"}],
            "repositories_removed": [],
        },
    )
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_repository_rename_updates_names_and_preserves_identity(db_session):
    t = await _seed(db_session)
    original_id = str(t.repo.id)

    await _deliver_app_event(
        db_session,
        "repository",
        {
            "action": "renamed",
            "changes": {"repository": {"name": {"from": "payments-api"}}},
            "repository": {
                "id": 900123,
                "name": "billing-api",
                "full_name": "acme-sec/billing-api",
                "owner": {"login": "acme-sec"},
                "default_branch": "main",
            },
            "installation": {"id": 77001},
        },
    )

    repo = await _reload(db_session, t.repo)
    assert str(repo.id) == original_id
    assert repo.full_name == "acme-sec/billing-api"
    assert repo.repo_name == "billing-api"
    assert repo.lifecycle_state == "connected"


@pytest.mark.asyncio
async def test_repository_transfer_to_foreign_owner_requires_reauthorization(db_session):
    t = await _seed(db_session)

    await _deliver_app_event(
        db_session,
        "repository",
        {
            "action": "transferred",
            "changes": {"owner": {"from": {"organization": {"login": "acme-sec"}}}},
            "repository": {
                "id": 900123,
                "name": "payments-api",
                "full_name": "other-corp/payments-api",
                "owner": {"login": "other-corp"},
                "default_branch": "main",
            },
            "installation": {"id": 77001},
        },
    )

    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (False, "reauthorization_required")
    assert repo.owner_name == "acme-sec"  # history/binding is not rewritten to the foreign owner


@pytest.mark.asyncio
async def test_default_branch_change_updates_repository(db_session):
    t = await _seed(db_session)

    await _deliver_app_event(
        db_session,
        "repository",
        {
            "action": "edited",
            "changes": {"default_branch": {"from": "main"}},
            "repository": {
                "id": 900123,
                "name": "payments-api",
                "full_name": "acme-sec/payments-api",
                "owner": {"login": "acme-sec"},
                "default_branch": "trunk",
            },
            "installation": {"id": 77001},
        },
    )

    assert (await _reload(db_session, t.repo)).default_branch == "trunk"


@pytest.mark.asyncio
async def test_repository_deleted_revokes_authority(db_session):
    t = await _seed(db_session)

    await _deliver_app_event(
        db_session,
        "repository",
        {
            "action": "deleted",
            "repository": {"id": 900123, "full_name": "acme-sec/payments-api", "owner": {"login": "acme-sec"}},
            "installation": {"id": 77001},
        },
    )

    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (False, "reauthorization_required")


@pytest.mark.asyncio
async def test_foreign_installation_cannot_change_another_organizations_repository(db_session):
    t = await _seed(db_session)

    response = await _deliver_app_event(
        db_session,
        "repository",
        {
            "action": "deleted",
            "repository": {"id": 900123, "full_name": "acme-sec/payments-api", "owner": {"login": "acme-sec"}},
            "installation": {"id": 55555},
        },
    )

    assert response["status"] == "ignored"
    repo = await _reload(db_session, t.repo)
    assert (repo.is_active, repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_redelivered_lifecycle_event_replays_original_response(db_session):
    await _seed(db_session)
    payload = {"action": "suspend", "installation": {"id": 77001}}

    first = await _deliver_app_event(db_session, "installation", payload, delivery="same-delivery")
    second = await _deliver_app_event(db_session, "installation", payload, delivery="same-delivery")

    assert first == second


_LIFECYCLE_REPLAYS = [
    ("installation", {"action": "deleted", "installation": {"id": 77001}}),
    ("installation", {"action": "suspend", "installation": {"id": 77001}}),
    ("installation", {"action": "unsuspend", "installation": {"id": 77001}}),
    (
        "installation",
        {"action": "new_permissions_accepted", "installation": {"id": 77001, "permissions": {"metadata": "read"}}},
    ),
    (
        "installation_repositories",
        {"action": "removed", "installation": {"id": 77001}, "repositories_removed": [{"id": 900123}]},
    ),
    (
        "installation_repositories",
        {"action": "added", "installation": {"id": 77001}, "repositories_added": [{"id": 900123}]},
    ),
    ("repository", {"action": "deleted", "installation": {"id": 77001}, "repository": {"id": 900123}}),
    (
        "repository",
        {
            "action": "renamed",
            "installation": {"id": 77001},
            "repository": {
                "id": 900123,
                "name": "billing-api",
                "full_name": "acme-sec/billing-api",
                "owner": {"login": "acme-sec"},
            },
        },
    ),
    (
        "repository",
        {
            "action": "transferred",
            "installation": {"id": 77001},
            "repository": {
                "id": 900123,
                "name": "payments-api",
                "full_name": "other-corp/payments-api",
                "owner": {"login": "other-corp"},
            },
        },
    ),
    (
        "repository",
        {
            "action": "edited",
            "changes": {"default_branch": {"from": "main"}},
            "installation": {"id": 77001},
            "repository": {"id": 900123, "default_branch": "trunk"},
        },
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("event", "payload"), _LIFECYCLE_REPLAYS, ids=lambda v: v if isinstance(v, str) else None)
async def test_lifecycle_handlers_are_idempotent_when_a_delivery_is_applied_twice(db_session, event, payload):
    """Review C8: handlers run before the delivery row is committed, so a crash in between (or a
    concurrent duplicate) re-applies them. Applying the same event again must change nothing."""
    t = await _seed(db_session)

    async def _state():
        await db_session.refresh(t.repo)
        integration = await db_session.scalar(
            select(RepositoryIntegration).where(RepositoryIntegration.repository_id == t.repo.id)
        )
        await db_session.refresh(integration)
        return (
            t.repo.is_active,
            t.repo.lifecycle_state,
            t.repo.full_name,
            t.repo.default_branch,
            dict(integration.access_metadata or {}),
        )

    await _deliver_app_event(db_session, event, payload)
    once = await _state()
    await _deliver_app_event(db_session, event, payload)

    assert await _state() == once


@pytest.mark.asyncio
async def test_distinct_lifecycle_deliveries_with_identical_content_both_apply(db_session):
    """Suspend, unsuspend, suspend again: the second suspend is not a replay of the first."""
    t = await _seed(db_session)
    suspend = {"action": "suspend", "installation": {"id": 77001}}
    unsuspend = {"action": "unsuspend", "installation": {"id": 77001}}

    await _deliver_app_event(db_session, "installation", suspend)
    await _deliver_app_event(db_session, "installation", unsuspend)
    await _deliver_app_event(db_session, "installation", suspend)

    assert (await _reload(db_session, t.repo)).lifecycle_state == "reauthorization_required"


@pytest.mark.asyncio
async def test_app_webhook_ignores_unsupported_events_and_requires_delivery_id(db_session):
    await _seed(db_session)

    response = await _deliver_app_event(db_session, "star", {"action": "created"})
    assert response["status"] == "ignored"

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.github_app_webhook(
            request=_FakeRequest({"installation": {"id": 77001}}, event="installation", delivery=""),
            db=db_session,
        )
    assert exc_info.value.status_code == 400


# --- 2. server-derived integration ------------------------------------------


def test_repository_connect_schema_rejects_browser_supplied_installation_identity():
    with pytest.raises(ValueError, match="Extra inputs"):
        RepositoryConnect(
            provider="github",
            owner_name="acme-sec",
            repo_name="x",
            full_name="acme-sec/x",
            installation_id="99999",
        )
    with pytest.raises(ValueError, match="Extra inputs"):
        RepositoryConnect(
            provider="github",
            owner_name="acme-sec",
            repo_name="x",
            full_name="acme-sec/x",
            provider_account_id="someone-else",
        )


@pytest.mark.asyncio
async def test_connect_derives_installation_from_verified_org_binding(db_session):
    t = await _seed(db_session)

    connected = await RepositoryService(db_session).connect(
        t.proj,
        RepositoryConnect(
            provider="github",
            external_repo_id="900999",
            owner_name="acme-sec",
            repo_name="new-repo",
            full_name="acme-sec/new-repo",
            default_branch="main",
        ),
        t.user,
    )

    integration = await RepositoryService(db_session).get_integration(connected.id)
    assert integration is not None
    assert integration.installation_id == "77001"
    assert integration.provider_account_id == "acme-sec"


@pytest.mark.asyncio
async def test_connect_github_without_org_binding_is_denied(db_session):
    t = await _seed(db_session)
    await db_session.delete(
        await db_session.scalar(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == t.org)
        )
    )
    await db_session.commit()

    with pytest.raises(RepositoryAuthorizationError):
        await RepositoryService(db_session).connect(
            t.proj,
            RepositoryConnect(
                provider="github",
                external_repo_id="900999",
                owner_name="acme-sec",
                repo_name="new-repo",
                full_name="acme-sec/new-repo",
            ),
            t.user,
        )


# --- 3. ignored events never poison dedup ------------------------------------


async def _deliver_repo_event(session, t, event, payload, *, delivery):
    # Use the key types the ORM loaded (UUID on Postgres, text on the SQLite stand-in).
    repo = await session.get(webhooks.Repository, t.repo.id)
    project = await session.get(webhooks.Project, repo.project_id)
    return await webhooks.github_webhook(
        org_id=project.organization_id,
        project_id=repo.project_id,
        repository_id=repo.id,
        request=_FakeRequest(payload, event=event, delivery=delivery),
        db=session,
    )


def _pr_payload(action):
    return {
        "action": action,
        "number": 7,
        "pull_request": {"number": 7, "head": {"sha": "a" * 40, "ref": "feat"}, "base": {"sha": "b" * 40}},
        "repository": {"id": 900123, "full_name": "acme-sec/payments-api"},
        "installation": {"id": 77001},
    }


@pytest.mark.asyncio
async def test_ignored_pull_request_action_does_not_block_later_supported_delivery(db_session, monkeypatch):
    t = await _seed(db_session)
    monkeypatch.setattr(webhooks, "is_beta_capability_enabled", lambda _name: True)
    handler = AsyncMock(return_value={"status": "queued", "scan_id": "scan-1"})
    monkeypatch.setattr(webhooks, "_handle_pull_request_event", handler)

    ignored = await _deliver_repo_event(db_session, t, "pull_request", _pr_payload("edited"), delivery="d-1")
    assert ignored["status"] == "ignored"
    handler.assert_not_awaited()

    queued = await _deliver_repo_event(db_session, t, "pull_request", _pr_payload("synchronize"), delivery="d-2")
    assert queued == {"status": "queued", "scan_id": "scan-1"}
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_deferred_event_while_capability_disabled_does_not_block_after_enable(db_session, monkeypatch):
    t = await _seed(db_session)
    handler = AsyncMock(return_value={"status": "queued", "scan_id": "scan-2"})
    monkeypatch.setattr(webhooks, "_handle_pull_request_event", handler)

    monkeypatch.setattr(webhooks, "is_beta_capability_enabled", lambda _name: False)
    deferred = await _deliver_repo_event(db_session, t, "pull_request", _pr_payload("opened"), delivery="d-1")
    assert deferred["status"] == "ignored"

    monkeypatch.setattr(webhooks, "is_beta_capability_enabled", lambda _name: True)
    queued = await _deliver_repo_event(db_session, t, "pull_request", _pr_payload("opened"), delivery="d-2")
    assert queued["status"] == "queued"


@pytest.mark.asyncio
async def test_ignored_redelivery_by_same_delivery_id_still_replays(db_session):
    t = await _seed(db_session)
    first = await _deliver_repo_event(db_session, t, "star", {"repository": {"id": 900123, "full_name": "acme-sec/payments-api"}, "installation": {"id": 77001}}, delivery="d-1")
    second = await _deliver_repo_event(db_session, t, "star", {"repository": {"id": 900123, "full_name": "acme-sec/payments-api"}, "installation": {"id": 77001}}, delivery="d-1")
    assert first == second == {"status": "ignored", "event": "star"}
    rows = (await db_session.execute(select(WebhookDelivery))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_revoked_repository_receives_no_scan_from_repository_webhook(db_session, monkeypatch):
    t = await _seed(db_session)
    t.repo.is_active = False
    t.repo.lifecycle_state = "reauthorization_required"
    await db_session.commit()
    push = AsyncMock(return_value={"status": "queued"})
    monkeypatch.setattr(webhooks, "_handle_push_event", push)

    response = await _deliver_repo_event(
        db_session,
        t,
        "push",
        {
            "ref": "refs/heads/main",
            "after": "c" * 40,
            "repository": {"id": 900123, "full_name": "acme-sec/payments-api"},
            "installation": {"id": 77001},
        },
        delivery="d-1",
    )

    assert response["status"] == "ignored"
    push.assert_not_awaited()
