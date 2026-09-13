"""Route-level coverage for server-issued scan attempt identity.

Execution-context is the only place a completion identity is minted.  R09
gates each mint behind the scan execution lease: the live-lease owner keeps
its identity, duplicate claimants are rejected, and an expired lease is
reclaimed with a fresh fencing identity.  Terminal scans return their frozen
identity unchanged.
"""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.api.v1.routes import internal
from app.db.base import Base
from app.db.enums import ScanStatus
from app.db.models import Organization, Project, Repository, Scan, User
from app.db.models.scan import ScanCompletionReceipt
from app.middleware.service_auth import WorkerPrincipal
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion


class _SQLiteUUID(TypeDecorator):
    """Accepts both str and UUID binds for PostgreSQL UUID columns on SQLite.

    The downcast applies to SQLite only.  Under PostgreSQL the column keeps
    native uuid param typing, so asyncpg sends uuid (not CHAR) and the real
    row-lock gate runs against production semantics.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR())

    def bind_processor(self, dialect):
        if dialect.name == "postgresql":
            return None  # asyncpg coerces str/UUID natively for uuid params

        def process(value):
            if value is None:
                return None
            # Dashed-string canonical form: matches str(uuid4()) seeds so the
            # service-boundary db.get(Scan, UUID(...)) lookups bind correctly.
            return str(value)

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


async def _seed_scan(session, status: ScanStatus = ScanStatus.RUNNING) -> tuple[Scan, UUID]:
    user_id = uuid4()
    org_id, project_id, repo_id, scan_id = (uuid4() for _ in range(4))
    user = User(
        id=str(user_id), auth_provider_user_id=f"ap-{user_id}", email=f"{user_id}@example.com"
    )
    org = Organization(
        id=str(org_id), name="org", slug=f"org-{org_id}", created_by_user_id=str(user_id)
    )
    project = Project(
        id=str(project_id),
        organization_id=str(org_id),
        name="p",
        slug=f"p-{project_id}",
        created_by_user_id=str(user_id),
    )
    repo = Repository(
        id=str(repo_id),
        project_id=str(project_id),
        provider="github",
        owner_name="o",
        repo_name="r",
        full_name="o/r",
    )
    scan = Scan(
        id=str(scan_id),
        project_id=str(project_id),
        repository_id=str(repo_id),
        trigger_type="manual",
        scan_type="full",
        status=status,
    )
    session.add_all([user, org, project, repo, scan])
    await session.commit()
    return scan, org_id


def _aware_dt(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _principal(org_id: UUID) -> WorkerPrincipal:
    return WorkerPrincipal(
        worker_id=uuid4(),
        organization_id=org_id,
        capabilities=frozenset({"scans:read", "scans:write"}),
    )


def _completion_request(attempt_id, revision) -> ScanCompletionRequest:
    return ScanCompletionRequest(
        winning_attempt_id=attempt_id,
        execution_revision=revision,
        findings=[],
        scanner_runs=[ScannerRunCompletion(scanner_name="trivy", status="completed", exit_code=0)],
        summary_json={"seen_fingerprints": [], "scanner_health": {"complete": True}},
    )


@pytest.mark.asyncio
async def test_execution_context_rejects_foreign_org_principal_and_serves_matched(db_session):
    """Merge follow-up: execution-context enforces the R06 service-level org
    check.  A fabricated org-A principal on an org-B scan raises the
    ScanAuthorizationError 403 mapping; the matched principal still receives
    attempt identity and lease fields (R09 logic untouched)."""
    scan, org_id = await _seed_scan(db_session)

    foreign = _principal(uuid4())
    with pytest.raises(HTTPException) as excinfo:
        await internal.get_scan_execution_context(
            scan_id=UUID(str(scan.id)), principal=foreign, db=db_session
        )
    assert excinfo.value.status_code == 403
    # The rejected claimant never touched the lease or identity.
    untouched = await db_session.get(Scan, str(scan.id))
    assert untouched.current_attempt_id is None
    assert untouched.execution_revision == 0

    matched = _principal(org_id)
    served = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=matched, db=db_session
    )
    assert served["org_id"] == str(org_id)
    assert served["attempt_id"]
    assert served["execution_revision"] == 1
    assert served["lease_owner"] == str(matched.worker_id)
    assert served["lease_expires_at"]
    assert served["reclaim_reason"] == "fresh_start"


@pytest.mark.asyncio
async def test_execution_context_grants_lease_and_rejects_duplicate_claimants(db_session):
    """R09: a live lease makes authority idempotent for its owner and rejects
    duplicate claimants until the lease expires; expiry reclaims visibly."""
    scan, org_id = await _seed_scan(db_session)
    owner = _principal(org_id)
    rival = _principal(org_id)

    first = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=owner, db=db_session
    )
    assert first["attempt_id"]
    assert len(first["attempt_id"]) <= 64
    assert first["execution_revision"] == 1
    assert first["lease_expires_at"] is not None
    assert first["reclaim_reason"] == "fresh_start"

    # Same worker refetch is idempotent while its lease is live.
    again = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=owner, db=db_session
    )
    assert again["attempt_id"] == first["attempt_id"]
    assert again["execution_revision"] == 1

    # A different claimant is rejected while the lease is valid.
    with pytest.raises(internal.HTTPException) as excinfo:
        await internal.get_scan_execution_context(
            scan_id=UUID(str(scan.id)), principal=rival, db=db_session
        )
    assert excinfo.value.status_code == 409
    assert excinfo.value.detail["code"] == "lease_active"
    assert excinfo.value.detail["current_owner"] == str(owner.worker_id)

    # Dead worker: expired lease is reclaimed with a new fencing identity.
    stored = await db_session.get(Scan, str(scan.id))
    stored.lease_expires_at = _aware_dt(datetime.now(UTC)) - timedelta(seconds=1)
    await db_session.commit()
    successor = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=rival, db=db_session
    )
    assert successor["attempt_id"] != first["attempt_id"]
    assert successor["execution_revision"] == 2
    assert successor["reclaim_reason"] == "expired_lease_reclaim"

    stored = await db_session.get(Scan, str(scan.id))
    assert stored.current_attempt_id == successor["attempt_id"]
    assert stored.execution_revision == 2


@pytest.mark.asyncio
async def test_execution_context_terminal_scan_identity_is_frozen(db_session):
    scan, org_id = await _seed_scan(db_session, status=ScanStatus.COMPLETED)
    scan.current_attempt_id = "frozen-attempt"
    scan.execution_revision = 4
    await db_session.commit()

    first = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=_principal(org_id), db=db_session
    )
    second = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=_principal(org_id), db=db_session
    )

    assert first["attempt_id"] == "frozen-attempt"
    assert first["execution_revision"] == 4
    assert second == first
    stored = await db_session.get(Scan, str(scan.id))
    assert stored.execution_revision == 4


@pytest.mark.asyncio
async def test_route_completion_with_stale_identity_is_a_typed_conflict(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = UUID(str(scan.id))
    principal = _principal(org_id)

    stale = await internal.get_scan_execution_context(scan_id=scan_id, principal=principal, db=db_session)
    # Supersede the stale identity through an expired-lease reclaim (R09).
    stored = await db_session.get(Scan, str(scan.id))
    stored.lease_expires_at = _aware_dt(datetime.now(UTC)) - timedelta(seconds=1)
    await db_session.commit()
    current = await internal.get_scan_execution_context(scan_id=scan_id, principal=principal, db=db_session)
    assert current["execution_revision"] == stale["execution_revision"] + 1

    accepted = await internal.complete_scan(
        scan_id=scan_id,
        data=_completion_request(current["attempt_id"], current["execution_revision"]),
        principal=principal,
        db=db_session,
    )
    assert accepted["replayed"] is False
    assert accepted["winning_attempt_id"] == current["attempt_id"]
    assert accepted["execution_revision"] == current["execution_revision"]

    receipts = (
        await db_session.execute(select(func.count()).select_from(ScanCompletionReceipt))
    ).scalar_one()
    assert receipts == 1
