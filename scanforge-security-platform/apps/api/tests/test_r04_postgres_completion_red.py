"""R04 completion boundary: server-owned, replay-safe completion receipts.

SQLite cases below exercise the runnable paths of the boundary.  The
PostgreSQL cases stay skipped unless ``R04_POSTGRES_URL`` is set: real
row-lock serialization is the hard release gate and must not be weakened.
"""
import asyncio
import os
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
from app.db.models import Organization, Project, Repository, Scan, ScannerRun, User
from app.db.models.scan import ScanCompletionReceipt
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services import scan_completion as scan_completion_module
from app.services.scan_completion import (
    CompletionPayloadConflict,
    CompletionSuperseded,
    ScanCompletionConflict,
    ScanCompletionService,
    canonical_evidence_digest,
)
from app.services.scans import ScanService



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
            return value if isinstance(value, str) else value.hex

        return process


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


# Deterministic regardless of mapper-configuration order: SQLAlchemy copies FK
# target types into referencing columns at first mapper-configuration time, so
# this downcast must run before ANY ORM use in the suite, not just before our
# tests.  Module import (collection) always precedes every test execution.
_downcast_postgres_uuid_columns()


def completion_request(**overrides) -> ScanCompletionRequest:
    values = {
        "winning_attempt_id": uuid4(),
        "execution_revision": 1,
        "findings": [],
        "scanner_runs": [ScannerRunCompletion(scanner_name="trivy", status="completed", exit_code=0)],
        "summary_json": {
            "seen_fingerprints": [],
            "scanner_health": {
                "expected": ["trivy"],
                "completed": ["trivy"],
                "failed": [],
                "missing": [],
                "complete": True,
            },
        },
    }
    values.update(overrides)
    return ScanCompletionRequest(**values)


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


async def _seed_scan(session, *, repo_suffix: str = "") -> Scan:
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
        repo_name=f"r{repo_suffix}",
        full_name=f"o/r{repo_suffix}",
    )
    scan = Scan(
        id=str(scan_id),
        project_id=str(project_id),
        repository_id=str(repo_id),
        trigger_type="manual",
        scan_type="full",
        status=ScanStatus.RUNNING,
    )
    # Real PostgreSQL enforces bare-FK insert order while SQLAlchemy only
    # orders flush output along relationship() edges, so seed parents
    # explicitly in dependency order.
    session.add(user)
    await session.flush()
    session.add(org)
    await session.flush()
    session.add(project)
    await session.flush()
    session.add(repo)
    await session.flush()
    session.add(scan)
    await session.flush()
    await session.commit()
    return scan, org_id


async def _count(session, model):
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_first_completion_writes_server_owned_receipt(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request()

    response = await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    assert response["replayed"] is False
    assert response["status"] == "completed"
    assert response["winning_attempt_id"] == str(data.winning_attempt_id)
    assert response["execution_revision"] == 1
    assert response["evidence_digest"] == canonical_evidence_digest(data)
    assert response["scanner_runs_complete"] is True

    receipt = (
        await db_session.execute(select(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == str(scan.id)))
    ).scalar_one()
    assert receipt.winning_attempt_id == str(data.winning_attempt_id)
    assert receipt.execution_revision == 1
    assert receipt.evidence_digest == canonical_evidence_digest(data)
    assert receipt.terminal_status == ScanStatus.COMPLETED.value
    assert receipt.scanner_runs_complete is True
    assert receipt.inserted_findings == 0
    assert receipt.updated_findings == 0


@pytest.mark.asyncio
async def test_identical_replay_returns_stored_receipt_without_reinserting(db_session, monkeypatch):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request()
    service = ScanCompletionService(db_session)
    first = await service.complete(scan_id, org_id, data)

    runs_before = await _count(db_session, ScannerRun)

    def _no_findings(*_args, **_kwargs):
        raise AssertionError("replay must not re-run finding writes")

    monkeypatch.setattr(scan_completion_module, "FindingService", _no_findings)
    replay = await service.complete(
        scan_id,
        org_id,
        completion_request(winning_attempt_id=data.winning_attempt_id, execution_revision=1),
    )

    assert replay["replayed"] is True
    assert replay["inserted_findings"] == first["inserted_findings"]
    assert replay["updated_findings"] == first["updated_findings"]
    assert replay["evidence_digest"] == first["evidence_digest"]
    assert replay["winning_attempt_id"] == first["winning_attempt_id"]
    assert await _count(db_session, ScannerRun) == runs_before == 1


@pytest.mark.asyncio
async def test_changed_valid_replay_is_conflict_and_does_not_mutate(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    service = ScanCompletionService(db_session)
    data = completion_request()
    await service.complete(scan_id, org_id, data)

    changed = completion_request(
        winning_attempt_id=data.winning_attempt_id,
        execution_revision=1,
        summary_json={
            "seen_fingerprints": [],
            "scanner_health": {
                "expected": ["trivy"],
                "completed": ["trivy"],
                "failed": [],
                "missing": [],
                "complete": True,
            },
            "extra": "changed",
        },
    )
    with pytest.raises(CompletionPayloadConflict) as excinfo:
        await service.complete(scan_id, org_id, changed)
    assert excinfo.value.code == "completion_payload_conflict"

    await db_session.rollback()
    assert await _count(db_session, ScannerRun) == 1
    assert await _count(db_session, ScanCompletionReceipt) == 1
    refreshed = await db_session.get(Scan, scan_id)
    assert "extra" not in (refreshed.summary_json or {})


@pytest.mark.asyncio
async def test_superseded_attempt_or_revision_is_typed_error(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    service = ScanCompletionService(db_session)
    winner = completion_request(execution_revision=2)
    await service.complete(scan_id, org_id, winner)

    with pytest.raises(CompletionSuperseded) as new_attempt:
        await service.complete(scan_id, org_id, completion_request(execution_revision=2))
    assert new_attempt.value.code == "completion_superseded"

    with pytest.raises(CompletionSuperseded) as stale_revision:
        await service.complete(
            scan_id,
            org_id,
            completion_request(
                winning_attempt_id=winner.winning_attempt_id, execution_revision=1
            ),
        )
    assert stale_revision.value.code == "completion_superseded"

    await db_session.rollback()
    assert await _count(db_session, ScanCompletionReceipt) == 1


@pytest.mark.asyncio
async def test_failure_after_evidence_writes_rolls_back_everything(db_session, monkeypatch):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    data = completion_request()

    class _ExplodingFindings:
        def __init__(self, _db):
            pass

        async def upsert_from_scan(self, **_kwargs):
            raise RuntimeError("injected failure")

        async def mark_not_observed_after_scan(self, **_kwargs):
            raise AssertionError("must not run after failure")

    monkeypatch.setattr(scan_completion_module, "FindingService", _ExplodingFindings)

    with pytest.raises(RuntimeError, match="injected failure"):
        await ScanCompletionService(db_session).complete(scan_id, org_id, data)

    await db_session.rollback()
    assert await _count(db_session, ScannerRun) == 0
    assert await _count(db_session, ScanCompletionReceipt) == 0
    refreshed = await db_session.get(Scan, scan_id)
    assert refreshed.status == ScanStatus.RUNNING
    assert refreshed.summary_json is None


@pytest.mark.asyncio
async def test_cancellation_before_completion_is_the_terminal_winner(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    await ScanService(db_session).cancel(scan_id)

    with pytest.raises(ScanCompletionConflict):
        await ScanCompletionService(db_session).complete(scan_id, org_id, completion_request())

    await db_session.rollback()
    assert (await db_session.get(Scan, scan_id)).status == ScanStatus.CANCELED
    assert await _count(db_session, ScanCompletionReceipt) == 0


@pytest.mark.asyncio
async def test_completion_before_cancellation_is_the_terminal_winner(db_session):
    scan, org_id = await _seed_scan(db_session)
    scan_id = str(scan.id)
    await ScanCompletionService(db_session).complete(scan_id, org_id, completion_request())

    with pytest.raises(ValueError, match="cancel"):
        await ScanService(db_session).cancel(scan_id)

    await db_session.rollback()
    assert (await db_session.get(Scan, scan_id)).status == ScanStatus.COMPLETED


def test_r04_service_import_and_fixture_path_probe():
    """Runnable probe: imports the boundary and constructs its DB fixture path."""
    assert ScanCompletionService is not None
    assert ScanCompletionRequest is not None
    if not os.getenv("R04_POSTGRES_URL"):
        pytest.skip("set R04_POSTGRES_URL to exercise the PostgreSQL fixture path")
    engine = create_async_engine(os.environ["R04_POSTGRES_URL"])
    try:
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


@pytest.fixture
async def postgres_sessionmaker():
    """Sessions against the disposable PostgreSQL cluster behind R04_POSTGRES_URL.

    The schema is the one created by ``alembic upgrade head`` on that cluster,
    not ``Base.metadata.create_all``, so the gate exercises the real DDL.
    """
    url = os.getenv("R04_POSTGRES_URL")
    if not url:
        pytest.skip("set R04_POSTGRES_URL to a disposable PostgreSQL database")
    engine = create_async_engine(url, pool_size=8, max_overflow=0)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    try:
        yield maker
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_changed_valid_replay_is_conflict_postgres_gate(postgres_sessionmaker):
    """Hard release gate: replay conflict under real PostgreSQL row locks."""
    maker = postgres_sessionmaker
    async with maker() as session:
        scan, org_id = await _seed_scan(session)
        scan_id = str(scan.id)
        data = completion_request()
        first = await ScanCompletionService(session).complete(scan_id, org_id, data)
        assert first["replayed"] is False

    async with maker() as session:
        changed = completion_request(
            winning_attempt_id=data.winning_attempt_id,
            execution_revision=1,
            summary_json={
                "seen_fingerprints": [],
                "scanner_health": {
                    "expected": ["trivy"],
                    "completed": ["trivy"],
                    "failed": [],
                    "missing": [],
                    "complete": True,
                },
                "extra": "changed",
            },
        )
        with pytest.raises(CompletionPayloadConflict) as excinfo:
            await ScanCompletionService(session).complete(scan_id, org_id, changed)
        assert excinfo.value.code == "completion_payload_conflict"

    async with maker() as session:
        assert await _count(session, ScannerRun) == 1
        assert await _count(session, ScanCompletionReceipt) == 1
        refreshed = await session.get(Scan, scan_id)
        assert "extra" not in (refreshed.summary_json or {})


@pytest.mark.asyncio
async def test_completion_and_cancellation_single_terminal_winner_postgres_gate(postgres_sessionmaker):
    """Hard release gate: concurrent completion/cancellation on the Scan row lock.

    Both operations are issued concurrently on separate connections, so
    PostgreSQL must serialize them on the Scan row and exactly one terminal
    outcome may win -- every race, not just a lucky ordering.
    """
    maker = postgres_sessionmaker
    for _race in range(8):
        async with maker() as session:
            scan, org_id = await _seed_scan(session, repo_suffix=str(_race))
            scan_id = str(scan.id)
        data = completion_request()
        outcomes: dict = {}

        async def _attempt_completion():
            async with maker() as session:
                try:
                    outcomes["completion"] = await ScanCompletionService(session).complete(
                        scan_id, org_id, data
                    )
                except ScanCompletionConflict as exc:
                    outcomes["completion"] = exc

        async def _attempt_cancellation():
            async with maker() as session:
                try:
                    await ScanService(session).cancel(scan_id)
                    outcomes["cancellation"] = "canceled"
                except ValueError as exc:
                    outcomes["cancellation"] = exc

        await asyncio.gather(_attempt_completion(), _attempt_cancellation())

        async with maker() as session:
            refreshed = await session.get(Scan, scan_id)
            receipts = (
                await session.execute(
                    select(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == scan_id)
                )
            ).scalars().all()
            assert refreshed.status in (ScanStatus.COMPLETED, ScanStatus.CANCELED)
            if refreshed.status == ScanStatus.COMPLETED:
                assert len(receipts) == 1
                assert outcomes["completion"]["replayed"] is False
                assert isinstance(outcomes["cancellation"], ValueError)
            else:
                assert len(receipts) == 0
                assert outcomes["cancellation"] == "canceled"
                assert isinstance(outcomes["completion"], ScanCompletionConflict)
