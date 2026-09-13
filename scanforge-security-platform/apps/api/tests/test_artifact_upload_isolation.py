"""R07 artifact isolation: a worker principal can never mint upload URLs
outside its own organization, and every presigned key is built server-side
from the authenticated scan's project organization.

SQLite cases exercise the runnable paths. PostgreSQL cases run when
R04_POSTGRES_URL points at a disposable cluster: the org-scoped access
join is the real tenant boundary and must be exercised on production
semantics, not only SQLite.
"""
import asyncio
import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.api.v1.routes.internal import ArtifactUploadRequest, create_artifact_upload_url
from app.db.base import Base
from app.db.enums import RepoProvider, ScanStatus
from app.db.models import Organization, Project, Repository, Scan, User
from app.middleware.service_auth import WorkerPrincipal


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
    """Bind both str and UUID for PostgreSQL UUID columns on SQLite only."""

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
            return str(value)

        return process


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_downcast_postgres_uuid_columns()


def _postgres_url() -> str | None:
    return os.getenv("R04_POSTGRES_URL")


async def _make_engine(request, backend: str):
    if backend == "postgres":
        engine = create_async_engine(_postgres_url())
    else:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    request.addfinalizer(lambda: asyncio.run(engine.dispose()))
    return engine


@pytest.fixture(params=["sqlite", "postgres"])
async def db_session(request):
    backend = request.param
    if backend == "postgres" and not _postgres_url():
        pytest.skip("set R04_POSTGRES_URL to a disposable PostgreSQL cluster")
    engine = await _make_engine(request, backend)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session, backend


async def seed_scan(session, backend: str = "sqlite") -> tuple[str, str, str]:
    """Two organizations; the scan lives under org_a. Returns ids.

    Bind values must match each backend's result type exactly: asyncpg
    returns uuid.UUID objects while SQLite returns the stored dashed
    text, and SQLAlchemy's insertmanyvalues sentinel check compares
    parameters against returned rows.
    """
    def uid():
        return uuid.uuid4() if backend == "postgres" else str(uuid.uuid4())

    user_id, org_a_id, org_b_id = uid(), uid(), uid()
    project_id, repository_id, scan_id = uid(), uid(), uid()

    session.add(
        User(
            id=user_id,
            auth_provider_user_id=f"prov-{uuid.uuid4().hex[:12]}",
            email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
            name="Owner",
            is_active=True,
        )
    )
    await session.flush()
    session.add_all(
        [
            Organization(
                id=org_a_id,
                name="Org A",
                slug=f"org-a-{uuid.uuid4().hex[:8]}",
                created_by_user_id=user_id,
            ),
            Organization(
                id=org_b_id,
                name="Org B",
                slug=f"org-b-{uuid.uuid4().hex[:8]}",
                created_by_user_id=user_id,
            ),
        ]
    )
    session.add(
        Project(
            id=project_id,
            organization_id=org_a_id,
            name="Proj",
            slug=f"proj-{uuid.uuid4().hex[:8]}",
            is_active=True,
            created_by_user_id=user_id,
        )
    )
    session.add(
        Repository(
            id=repository_id,
            project_id=project_id,
            provider=RepoProvider.GITHUB,
            owner_name="octocat",
            repo_name=f"hello-{uuid.uuid4().hex[:8]}",
            full_name=f"octocat/hello-{uuid.uuid4().hex[:8]}",
            is_active=True,
        )
    )
    session.add(
        Scan(
            id=scan_id,
            project_id=project_id,
            repository_id=repository_id,
            trigger_type="manual",
            scan_type="full",
            status=ScanStatus.QUEUED,
        )
    )
    await session.commit()
    return str(org_a_id), str(org_b_id), str(scan_id)


def principal_for(organization_id: uuid.UUID) -> WorkerPrincipal:
    return WorkerPrincipal(
        worker_id=uuid.uuid4(),
        organization_id=organization_id,
        capabilities=frozenset({"artifacts:write"}),
    )


class _StubR2Client:
    def __init__(self, **_kwargs) -> None:
        pass

    def generate_presigned_upload_url(self, key: str, content_type: str) -> str:
        return f"https://signed.example/{key}?ct={content_type}"


@pytest.mark.asyncio
async def test_worker_cannot_mint_upload_url_for_other_organization_scan(db_session, monkeypatch):
    session, backend = db_session
    _org_a, org_b, scan_id = await seed_scan(session, backend)
    monkeypatch.setattr("app.api.v1.routes.internal.R2Client", _StubR2Client)

    foreign_principal = principal_for(org_b)
    request = ArtifactUploadRequest(scanner_name="trivy", filename="results.json", size_bytes=10)
    with pytest.raises(HTTPException) as excinfo:
        await create_artifact_upload_url(uuid.UUID(scan_id), request, foreign_principal, session)

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_upload_url_key_is_scoped_to_authenticated_organization_and_scan(db_session, monkeypatch):
    session, backend = db_session
    org_a, _org_b, scan_id = await seed_scan(session, backend)
    monkeypatch.setattr("app.api.v1.routes.internal.R2Client", _StubR2Client)

    principal = principal_for(org_a)
    request = ArtifactUploadRequest(scanner_name="trivy", filename="results.json", size_bytes=10)
    response = await create_artifact_upload_url(uuid.UUID(scan_id), request, principal, session)

    assert response["key"] == f"scan-artifacts/{org_a}/{scan_id}/trivy/results.json"
    assert response["upload_url"].startswith(f"https://signed.example/scan-artifacts/{org_a}/{scan_id}/")


@pytest.mark.asyncio
async def test_upload_url_rejects_path_traversal_components(db_session):
    session, backend = db_session
    org_a, _org_b, scan_id = await seed_scan(session, backend)
    principal = principal_for(org_a)
    for filename in ("../escape.json", "sub/dir.json", "back\\slash.json"):
        request = ArtifactUploadRequest(scanner_name="trivy", filename=filename, size_bytes=10)
        with pytest.raises(HTTPException) as excinfo:
            await create_artifact_upload_url(uuid.UUID(scan_id), request, principal, session)
        assert excinfo.value.status_code == 400
