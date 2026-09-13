"""R09 execution lease: renew, duplicate-claim rejection, expired-lease reclaim.

SQLite cases exercise the runnable decision logic.  The PostgreSQL cases stay
skipped unless ``R09_POSTGRES_URL`` (or ``R04_POSTGRES_URL``) is set: real
row-lock serialization on the Scan row is the DB-behavior evidence gate.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.db.base import Base
from app.db.enums import ScanStatus
from app.db.models import Organization, Project, Repository, Scan, User
from app.services.scan_lease import (
    LEASE_SECONDS,
    RECLAIM_EXPIRED,
    RECLAIM_FRESH,
    LeaseConflict,
    ScanLeaseService,
)


@compiles(PGUUID, "sqlite")
def _pg_uuid_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(45)"


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
            if value is None:
                return None
            return value if isinstance(value, str) else value.hex

        return process


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_downcast_postgres_uuid_columns()

TERMINAL = frozenset({ScanStatus.CANCELED, ScanStatus.COMPLETED})


def _postgres_url() -> str | None:
    return os.environ.get("R09_POSTGRES_URL") or os.environ.get("R04_POSTGRES_URL")


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


@pytest.fixture
async def pg_session():
    url = _postgres_url()
    if not url:
        pytest.skip("set R09_POSTGRES_URL (or R04_POSTGRES_URL) to a disposable PostgreSQL database")
    engine = create_async_engine(url)
    assert engine.url.drivername == "postgresql+asyncpg"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _aware_dt(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def _seed_scan(session) -> Scan:
    user_id = uuid4()
    org_id, project_id, repo_id, scan_id = (uuid4() for _ in range(4))
    session.add(User(id=str(user_id), auth_provider_user_id=f"ap-{user_id}", email=f"{user_id}@example.com"))
    await session.flush()
    session.add(Organization(id=str(org_id), name="org", slug=f"org-{org_id}", created_by_user_id=str(user_id)))
    await session.flush()
    session.add(
        Project(
            id=str(project_id),
            organization_id=str(org_id),
            name="p",
            slug=f"p-{project_id}",
            created_by_user_id=str(user_id),
        )
    )
    await session.flush()
    session.add(
        Repository(
            id=str(repo_id),
            project_id=str(project_id),
            provider="github",
            owner_name="o",
            repo_name=f"r-{repo_id}",
            full_name=f"o/r-{repo_id}",
        )
    )
    await session.flush()
    scan = Scan(
        id=str(scan_id),
        project_id=str(project_id),
        repository_id=str(repo_id),
        trigger_type="manual",
        scan_type="full",
        status=ScanStatus.QUEUED,
    )
    session.add(scan)
    await session.flush()
    await session.commit()
    return await session.get(Scan, str(scan_id))


async def _acquire(session, scan, owner: str):
    return await ScanLeaseService(session).acquire(
        str(scan.id), terminal_statuses=TERMINAL, worker_owner=owner
    )


async def _renew(session, scan, owner: str, attempt_id: str, revision: int):
    return await ScanLeaseService(session).renew(
        str(scan.id), attempt_id=attempt_id, execution_revision=revision, worker_owner=owner
    )


async def _run_lease_recovery_scenarios(session):
    """Heartbeat renewal extends the lease; duplicate reclaim is rejected
    while the lease is valid; an expired lease is reclaimed with a
    dead-worker visibility reason and fencing identity."""
    scan = await _seed_scan(session)

    # Idle first claim: no previous owner, so this is not a dead worker.
    scan, reason = await _acquire(session, scan, "worker-a")
    assert reason == RECLAIM_FRESH
    assert scan.current_attempt_id
    assert scan.execution_revision == 1
    first_attempt, first_revision = scan.current_attempt_id, scan.execution_revision
    assert scan.lease_expires_at is not None
    base_expiry = scan.lease_expires_at

    # Heartbeat renewal extends the lease and stamps the heartbeat.
    before = _aware_dt(datetime.now(UTC))
    scan = await _renew(session, scan, "worker-a", first_attempt, first_revision)
    hb = _aware_dt(scan.last_heartbeat_at)
    exp = _aware_dt(scan.lease_expires_at)
    base = _aware_dt(base_expiry)
    assert hb >= before - timedelta(seconds=5)
    assert exp > base - timedelta(seconds=5)
    assert (exp - hb).total_seconds() == pytest.approx(LEASE_SECONDS, abs=5)

    # Duplicate reclaim rejected while the lease is valid.
    with pytest.raises(LeaseConflict) as excinfo:
        await _acquire(session, scan, "worker-b")
    assert excinfo.value.reason == "lease_active"
    assert excinfo.value.current_owner == "worker-a"
    await session.refresh(scan)
    assert scan.current_attempt_id == first_attempt
    assert scan.execution_revision == first_revision

    # Dead worker: lease expires without renewal, successor reclaims.
    scan.lease_expires_at = _aware_dt(datetime.now(UTC)) - timedelta(seconds=1)
    await session.commit()
    scan, reason = await _acquire(session, scan, "worker-b")
    assert reason == RECLAIM_EXPIRED
    assert scan.current_attempt_id != first_attempt
    assert scan.execution_revision == first_revision + 1
    assert scan.lease_owner == "worker-b"

    # Stale attempt cannot renew after the reclaim.
    with pytest.raises(LeaseConflict) as excinfo:
        await _renew(session, scan, "worker-a", first_attempt, first_revision)
    assert excinfo.value.reason == "stale_attempt"


async def test_lease_recovery_paths_sqlite(db_session):
    await _run_lease_recovery_scenarios(db_session)


async def test_lease_recovery_paths_postgres(pg_session):
    await _run_lease_recovery_scenarios(pg_session)


async def test_expired_lease_cannot_be_renewed(db_session):
    scan = await _seed_scan(db_session)
    scan, _reason = await _acquire(db_session, scan, "worker-a")
    attempt, revision = scan.current_attempt_id, scan.execution_revision
    scan.lease_expires_at = _aware_dt(datetime.now(UTC)) - timedelta(seconds=1)
    await db_session.commit()

    with pytest.raises(LeaseConflict) as excinfo:
        await _renew(db_session, scan, "worker-a", attempt, revision)
    assert excinfo.value.reason == "lease_expired"


async def test_heartbeat_with_wrong_revision_is_stale_attempt(db_session):
    scan = await _seed_scan(db_session)
    scan, _reason = await _acquire(db_session, scan, "worker-a")
    with pytest.raises(LeaseConflict) as excinfo:
        await _renew(db_session, scan, "worker-a", scan.current_attempt_id, scan.execution_revision + 5)
    assert excinfo.value.reason == "stale_attempt"


async def test_terminal_scan_never_mints_new_attempts(db_session):
    scan = await _seed_scan(db_session)
    scan.status = ScanStatus.COMPLETED
    await db_session.commit()
    scan, reason = await _acquire(db_session, scan, "worker-a")
    assert reason == RECLAIM_FRESH
    assert scan.current_attempt_id is None
    count = (await db_session.execute(select(func.count()).select_from(Scan))).scalar_one()
    assert count == 1
