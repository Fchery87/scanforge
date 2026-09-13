"""Route-level coverage for server-issued scan attempt identity.

Execution-context is the only place a completion identity is minted.  Each
fetch for a non-terminal scan issues a fresh attempt and bumps the revision;
terminal scans return their frozen identity unchanged.
"""
from uuid import UUID, uuid4

import pytest
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
    """Accepts both str and UUID binds for PostgreSQL UUID columns on SQLite."""

    impl = CHAR
    cache_ok = True

    def bind_processor(self, _dialect):
        def process(value):
            if value is None:
                return None
            return value if isinstance(value, str) else value.hex

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
async def test_execution_context_issues_and_persists_fresh_attempt_identity(db_session):
    scan, org_id = await _seed_scan(db_session)

    first = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=_principal(org_id), db=db_session
    )
    second = await internal.get_scan_execution_context(
        scan_id=UUID(str(scan.id)), principal=_principal(org_id), db=db_session
    )

    assert first["attempt_id"]
    assert len(first["attempt_id"]) <= 64
    assert first["execution_revision"] == 1
    assert second["attempt_id"] != first["attempt_id"]
    assert second["execution_revision"] == 2

    stored = await db_session.get(Scan, str(scan.id))
    assert stored.current_attempt_id == second["attempt_id"]
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
    current = await internal.get_scan_execution_context(scan_id=scan_id, principal=principal, db=db_session)

    with pytest.raises(internal.HTTPException) as excinfo:
        await internal.complete_scan(
            scan_id=scan_id,
            data=_completion_request(stale["attempt_id"], stale["execution_revision"]),
            principal=principal,
            db=db_session,
        )
    assert excinfo.value.status_code == 409
    assert "superseded" in str(excinfo.value.detail)

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
