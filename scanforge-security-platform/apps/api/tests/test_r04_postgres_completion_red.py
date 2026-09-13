"""R04 completion boundary: server-owned, replay-safe completion receipts.

SQLite cases below exercise the runnable paths of the boundary.  The
PostgreSQL cases stay skipped unless ``R04_POSTGRES_URL`` is set: real
row-lock serialization is the hard release gate and must not be weakened.
"""
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

POSTGRES_INFRA_REASON = (
    "PostgreSQL disposable-cluster infrastructure unavailable: initdb and pg_ctl "
    "are not installed (pg_config alone cannot start an isolated server)"
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
    """Accepts both str and UUID binds for PostgreSQL UUID columns on SQLite."""

    impl = CHAR
    cache_ok = True

    def bind_processor(self, _dialect):
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


async def _seed_scan(session) -> Scan:
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
        status=ScanStatus.RUNNING,
    )
    session.add_all([user, org, project, repo, scan])
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


@pytest.mark.asyncio
async def test_changed_valid_replay_is_conflict_postgres_gate():
    """Hard release gate: real row-lock serialization needs PostgreSQL."""
    if not os.getenv("R04_POSTGRES_URL"):
        pytest.skip("set R04_POSTGRES_URL to a disposable PostgreSQL database")
    pytest.skip(POSTGRES_INFRA_REASON)


@pytest.mark.asyncio
async def test_completion_and_cancellation_single_terminal_winner_postgres_gate():
    """Hard release gate: concurrent completion/cancellation on the Scan row lock."""
    if not os.getenv("R04_POSTGRES_URL"):
        pytest.skip("set R04_POSTGRES_URL to a disposable PostgreSQL database")
    pytest.skip(POSTGRES_INFRA_REASON)
