"""P2.5 / #54: reconcile GitHub state after missed events.

Seam under test: `GitHubReconciliationService` driven by a fake GitHub state provider
(no network). The webhook route is used only to prove that redelivered stale events cannot
undo a reconciliation. Live GitHub App verification is recorded as not run (verifier-blocked).

Behaviors:
- After an ingress outage a repository converges to the current head with one head
  observation and no scans, findings or generations for intervening commits.
- Missed delete/suspend/permission/removal events are applied; missed unsuspend/re-add
  events are applied; human disconnects are never reversed.
- Reinstall under a new installation id rebinds revoked repositories by immutable repo id.
- Receipts and safe errors are persisted; transient provider failures never change authority.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.api.v1.routes import webhooks
from app.db.base import Base
from app.db.models import (
    FindingBranchObservation,
    Organization,
    OrganizationIntegration,
    OrganizationMember,
    Project,
    Repository,
    RepositoryBranchGeneration,
    RepositoryIntegration,
    Scan,
    User,
)
from app.db.models.github_reconciliation import GitHubReconciliationReceipt
from app.services.github_reconciliation import (
    GitHubProviderError,
    GitHubReconciliationService,
    InstallationSnapshot,
    RepositorySnapshot,
)
from app.services.github_state_provider import GitHubAppStateProvider

SHA_A = "a" * 40
SHA_D = "d" * 40
FULL_PERMS = {"metadata": "read", "contents": "read"}


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


class FakeGitHub:
    """In-memory GitHub state. `installations` maps id -> snapshot (absent means 404)."""

    def __init__(self):
        self.installations: dict[str, InstallationSnapshot] = {}
        self.repositories: dict[str, list[RepositorySnapshot]] = {}
        self.heads: dict[str, str] = {}
        self.compare_status: dict[tuple[str, str], str] = {}
        self.failure: Exception | None = None
        self.compare_calls: list[tuple[str, str]] = []

    def _maybe_fail(self):
        if self.failure is not None:
            raise self.failure

    async def get_installation(self, installation_id):
        self._maybe_fail()
        return self.installations.get(installation_id)

    async def list_repositories(self, installation_id):
        self._maybe_fail()
        return list(self.repositories.get(installation_id, []))

    async def resolve_head(self, installation_id, owner_name, repo_name, branch_name):  # noqa: ARG002
        self._maybe_fail()
        return self.heads[f"{owner_name}/{repo_name}"]

    async def compare_commits(self, installation_id, owner_name, repo_name, base_sha, head_sha):  # noqa: ARG002
        self._maybe_fail()
        self.compare_calls.append((base_sha, head_sha))
        return {
            "status": self.compare_status.get((base_sha, head_sha), "unknown"),
            "base_sha": base_sha,
            "head_sha": head_sha,
        }


def _snap(repo_id="900123", owner="acme-sec", name="payments-api", branch="main"):
    return RepositorySnapshot(
        external_repo_id=repo_id,
        owner_name=owner,
        repo_name=name,
        full_name=f"{owner}/{name}",
        default_branch=branch,
    )


def _healthy(github, installation_id="77001", repos=None):
    github.installations[installation_id] = InstallationSnapshot(suspended=False, permissions=FULL_PERMS)
    github.repositories[installation_id] = repos if repos is not None else [_snap()]


async def _add_repo(session, project_id, *, installation_id, repo_id, owner, name):
    repo = Repository(
        project_id=project_id,
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
    session.add(
        RepositoryBranchGeneration(
            repository_id=repo.id,
            full_ref_name="refs/heads/main",
            branch_name="main",
            generation_number=1,
            head_commit_sha=SHA_A,
            ancestry_status="verified_initial",
        )
    )
    await session.commit()
    return repo


async def _seed(session, *, installation_id="77001", repo_id="900123", owner="acme-sec", name="payments-api"):
    user, org, proj = uuid4(), uuid4(), uuid4()
    session.add_all(
        [
            User(id=user, auth_provider_user_id=f"u-{user}", email=f"{user}@example.com"),
            Organization(id=org, name="Org", slug=f"org-{org}", created_by_user_id=user),
            OrganizationMember(id=str(uuid4()), organization_id=org, user_id=user, role="owner"),
            Project(id=proj, organization_id=org, name="Proj", slug=f"proj-{proj}", created_by_user_id=user),
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
    repo = await _add_repo(
        session, proj, installation_id=installation_id, repo_id=repo_id, owner=owner, name=name
    )
    return SimpleNamespace(user=user, org=org, proj=proj, repo=repo)


async def _count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def _generations(session, repo):
    rows = await session.execute(
        select(RepositoryBranchGeneration)
        .where(RepositoryBranchGeneration.repository_id == repo.id)
        .order_by(RepositoryBranchGeneration.generation_number)
    )
    return list(rows.scalars())


# --- outage: converge to current head without fabricated observations -------


@pytest.mark.asyncio
async def test_outage_converges_to_current_head_without_intermediate_observations(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_D  # B and C landed during the outage
    gh.compare_status[(SHA_A, SHA_D)] = "ahead"
    scans_before = await _count(db_session, Scan)

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation(
        "77001", trigger="outage_recovery"
    )

    gens = await _generations(db_session, t.repo)
    assert [(g.generation_number, g.head_commit_sha, g.retired_at) for g in gens] == [(1, SHA_D, None)]
    assert gens[0].ancestry_status == "verified_descendant"
    assert gh.compare_calls == [(SHA_A, SHA_D)]  # only the endpoints are ever compared
    assert await _count(db_session, Scan) == scans_before
    assert await _count(db_session, FindingBranchObservation) == 0
    assert result["status"] == "completed"
    repo_result = result["repositories"][0]
    assert (repo_result["previous_head"], repo_result["current_head"]) == (SHA_A, SHA_D)
    assert repo_result["intermediate_commits_observed"] is False


@pytest.mark.asyncio
async def test_force_push_during_outage_starts_new_generation_without_absence_credit(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_D
    gh.compare_status[(SHA_A, SHA_D)] = "diverged"

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    gens = await _generations(db_session, t.repo)
    assert [g.generation_number for g in gens] == [1, 2]
    assert gens[0].retired_at is not None
    assert (gens[1].head_commit_sha, gens[1].ancestry_status) == (SHA_D, "diverged_reset")
    assert result["repositories"][0]["absence_credit_eligible"] is False


@pytest.mark.asyncio
async def test_reconciling_twice_is_idempotent(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_D
    gh.compare_status[(SHA_A, SHA_D)] = "ahead"
    service = GitHubReconciliationService(db_session, gh)

    await service.reconcile_installation("77001")
    second = await service.reconcile_installation("77001")

    assert len(await _generations(db_session, t.repo)) == 1
    assert second["repositories"][0]["absence_credit_eligible"] is False
    assert second["repositories"][0]["head_changed"] is False


@pytest.mark.asyncio
async def test_revoked_repositories_do_not_advance_heads(db_session):
    t = await _seed(db_session)
    t.repo.is_active = False
    t.repo.lifecycle_state = "disconnected"
    await db_session.commit()
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_D

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    assert (await _generations(db_session, t.repo))[0].head_commit_sha == SHA_A


# --- missed lifecycle events -------------------------------------------------


@pytest.mark.asyncio
async def test_missed_installation_delete_revokes_repositories_and_binding(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()  # installation 404s

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (False, "reauthorization_required")
    assert (
        await db_session.scalar(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == t.org)
        )
    ) is None
    assert result["installation_state"] == "deleted"


@pytest.mark.asyncio
async def test_missed_suspend_then_missed_unsuspend(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.installations["77001"] = InstallationSnapshot(suspended=True, permissions=FULL_PERMS)
    gh.heads["acme-sec/payments-api"] = SHA_A
    service = GitHubReconciliationService(db_session, gh)

    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (False, "reauthorization_required")

    gh.installations["77001"] = InstallationSnapshot(suspended=False, permissions=FULL_PERMS)
    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_missed_permission_loss_and_regrant(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_A
    gh.installations["77001"] = InstallationSnapshot(suspended=False, permissions={"metadata": "read"})
    service = GitHubReconciliationService(db_session, gh)

    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert t.repo.lifecycle_state == "reauthorization_required"

    gh.installations["77001"] = InstallationSnapshot(suspended=False, permissions=FULL_PERMS)
    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert t.repo.lifecycle_state == "connected"


@pytest.mark.asyncio
async def test_missed_repository_removal_and_readd(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh, repos=[_snap(repo_id="1", name="unrelated")])
    service = GitHubReconciliationService(db_session, gh)

    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert t.repo.lifecycle_state == "reauthorization_required"

    gh.repositories["77001"] = [_snap()]
    gh.heads["acme-sec/payments-api"] = SHA_A
    await service.reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (True, "connected")


@pytest.mark.asyncio
async def test_missed_rename_and_default_branch_change_are_applied(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh, repos=[_snap(name="billing-api", branch="trunk")])
    gh.heads["acme-sec/billing-api"] = SHA_A

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(t.repo)
    assert (t.repo.full_name, t.repo.repo_name, t.repo.default_branch) == (
        "acme-sec/billing-api",
        "billing-api",
        "trunk",
    )
    assert t.repo.lifecycle_state == "connected"


@pytest.mark.asyncio
async def test_human_disconnect_survives_reconciliation(db_session):
    t = await _seed(db_session)
    t.repo.is_active = False
    t.repo.lifecycle_state = "disconnected"
    await db_session.commit()
    gh = FakeGitHub()
    _healthy(gh)

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (False, "disconnected")


@pytest.mark.asyncio
async def test_reconciling_one_installation_never_touches_another(db_session):
    mine = await _seed(db_session, installation_id="77001", repo_id="900123")
    other = await _seed(db_session, installation_id="88002", repo_id="900999", owner="other-org", name="svc")
    gh = FakeGitHub()  # both installations 404

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(mine.repo)
    await db_session.refresh(other.repo)
    assert mine.repo.lifecycle_state == "reauthorization_required"
    assert (other.repo.is_active, other.repo.lifecycle_state) == (True, "connected")


# --- reinstall and redelivery -----------------------------------------------


@pytest.mark.asyncio
async def test_reinstall_under_new_installation_rebinds_deleted_repository(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    service = GitHubReconciliationService(db_session, gh)
    await service.reconcile_installation("77001")  # missed delete
    # Reinstall: the organization is bound to a fresh installation id.
    db_session.add(
        OrganizationIntegration(
            organization_id=t.org,
            provider="github",
            installation_id="77777",
            account_login="acme-sec",
            account_type="Organization",
        )
    )
    await db_session.commit()
    _healthy(gh, installation_id="77777")
    gh.heads["acme-sec/payments-api"] = SHA_A

    result = await service.reconcile_organization(t.org)

    await db_session.refresh(t.repo)
    integration = await db_session.scalar(
        select(RepositoryIntegration).where(RepositoryIntegration.repository_id == t.repo.id)
    )
    assert (t.repo.is_active, t.repo.lifecycle_state) == (True, "connected")
    assert integration.installation_id == "77777"
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_reinstall_does_not_rebind_human_disconnected_repository(db_session):
    t = await _seed(db_session)
    t.repo.is_active = False
    t.repo.lifecycle_state = "disconnected"
    await db_session.commit()
    org_integration = await db_session.scalar(
        select(OrganizationIntegration).where(OrganizationIntegration.organization_id == t.org)
    )
    org_integration.installation_id = "77777"
    await db_session.commit()
    gh = FakeGitHub()
    _healthy(gh, installation_id="77777")

    await GitHubReconciliationService(db_session, gh).reconcile_organization(t.org)

    await db_session.refresh(t.repo)
    assert t.repo.lifecycle_state == "disconnected"


@pytest.mark.asyncio
async def test_redelivered_stale_event_cannot_undo_reconciliation(db_session, monkeypatch):
    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    t = await _seed(db_session)

    class _Req:
        def __init__(self):
            self.headers = {"x-github-event": "installation", "x-github-delivery": "dlv-suspend-1"}

        async def json(self):
            return {"action": "suspend", "installation": {"id": 77001}}

    await webhooks.github_app_webhook(request=_Req(), db=db_session)
    gh = FakeGitHub()
    _healthy(gh)  # unsuspend was missed; reconciliation restores
    gh.heads["acme-sec/payments-api"] = SHA_A
    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")
    await db_session.refresh(t.repo)
    assert t.repo.lifecycle_state == "connected"

    replay = await webhooks.github_app_webhook(request=_Req(), db=db_session)  # same GUID redelivered

    await db_session.refresh(t.repo)
    assert replay["status"] == "processed"
    assert t.repo.lifecycle_state == "connected"


# --- receipts and safe errors -----------------------------------------------


@pytest.mark.asyncio
async def test_receipt_is_persisted_for_each_run(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh)
    gh.heads["acme-sec/payments-api"] = SHA_D
    gh.compare_status[(SHA_A, SHA_D)] = "ahead"

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001", trigger="outage_recovery")

    receipt = await db_session.scalar(select(GitHubReconciliationReceipt))
    assert receipt.installation_id == "77001"
    assert str(receipt.organization_id) == str(t.org)
    assert (receipt.trigger, receipt.status) == ("outage_recovery", "completed")
    assert receipt.error_code is None
    assert receipt.summary["repositories"][0]["current_head"] == SHA_D
    assert receipt.finished_at is not None


@pytest.mark.asyncio
async def test_provider_failure_records_safe_error_and_preserves_authority(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    gh.failure = GitHubProviderError(
        "rate_limited", "GET failed with Authorization: Bearer ghs_SECRETTOKEN123 and ghp_ANOTHERSECRET456"
    )

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (True, "connected")  # unknown is not revoked
    assert (await _generations(db_session, t.repo))[0].head_commit_sha == SHA_A
    assert result["status"] == "failed"
    receipt = await db_session.scalar(select(GitHubReconciliationReceipt))
    assert (receipt.status, receipt.error_code) == ("failed", "rate_limited")
    stored = f"{receipt.error_message} {receipt.summary} {result}"
    assert "SECRETTOKEN" not in stored
    assert "ANOTHERSECRET" not in stored
    assert "ghs_" not in stored
    assert "ghp_" not in stored


@pytest.mark.asyncio
async def test_unexpected_exception_is_recorded_by_type_only(db_session):
    await _seed(db_session)
    gh = FakeGitHub()
    gh.failure = RuntimeError("boom token=ghs_LEAKY999")

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    receipt = await db_session.scalar(select(GitHubReconciliationReceipt))
    assert result["status"] == "failed"
    assert receipt.error_code == "unexpected_error"
    assert "LEAKY" not in f"{receipt.error_message}"


@pytest.mark.asyncio
async def test_missed_transfer_to_another_owner_revokes_authority(db_session):
    t = await _seed(db_session)
    gh = FakeGitHub()
    _healthy(gh, repos=[_snap(owner="someone-else")])
    gh.heads["someone-else/payments-api"] = SHA_D

    await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    await db_session.refresh(t.repo)
    assert (t.repo.is_active, t.repo.lifecycle_state) == (False, "reauthorization_required")
    assert (await _generations(db_session, t.repo))[0].head_commit_sha == SHA_A


@pytest.mark.asyncio
async def test_app_provider_maps_failures_to_safe_codes(db_session):
    class _Svc:
        def __init__(self, status):
            self.status = status

        async def _get_installation_details(self, installation_id):  # noqa: ARG002
            request = httpx.Request("GET", "https://api.github.com/x", headers={"Authorization": "Bearer ghs_TOKEN"})
            raise httpx.HTTPStatusError(
                "boom ghs_TOKEN", request=request, response=httpx.Response(self.status, request=request)
            )

    assert await GitHubAppStateProvider(db_session, _Svc(404)).get_installation("1") is None
    with pytest.raises(GitHubProviderError) as err:
        await GitHubAppStateProvider(db_session, _Svc(502)).get_installation("1")
    assert err.value.code == "github_http_502"
    assert "ghs_" not in err.value.message


@pytest.mark.asyncio
async def test_head_resolution_failure_for_one_repository_does_not_block_others(db_session):
    t = await _seed(db_session)
    second = await _add_repo(
        db_session, t.proj, installation_id="77001", repo_id="900124", owner="acme-sec", name="other"
    )
    gh = FakeGitHub()
    _healthy(gh, repos=[_snap(), _snap(repo_id="900124", name="other")])
    gh.heads["acme-sec/other"] = SHA_D
    gh.compare_status[(SHA_A, SHA_D)] = "ahead"
    # payments-api has no head in the fake -> per-repository error

    result = await GitHubReconciliationService(db_session, gh).reconcile_installation("77001")

    assert result["status"] == "completed_with_errors"
    assert (await _generations(db_session, second))[0].head_commit_sha == SHA_D
    assert (await _generations(db_session, t.repo))[0].head_commit_sha == SHA_A
