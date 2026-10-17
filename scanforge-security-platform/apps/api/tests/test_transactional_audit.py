from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.models import AuditLog, Finding, FindingEvent, Organization, OrganizationMember, Project, Repository, User
from app.schemas.organizations import OrganizationCreate
from app.services.audit_logs import AuditLogService
from app.services.findings import FindingService
from app.services.organizations import OrganizationService


from sqlalchemy.types import CHAR, TypeDecorator


@compiles(PGUUID, "sqlite")
def _pg_uuid_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "CHAR(36)"


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(64)"


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

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


@pytest.fixture
async def db_session():
    _downcast_postgres_uuid_columns()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_organization_creation_writes_audit_log_in_same_transaction(db_session):
    user = User(
        id=str(uuid4()),
        auth_provider_user_id="sub-owner-1",
        email="owner@example.com",
        name="Owner",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    org, member = await OrganizationService(db_session).create(
        OrganizationCreate(name="Acme Sec", slug="acme-sec"),
        user.id,
    )
    logs = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.organization_id == str(org.id),
                AuditLog.action == "organization_created",
            )
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].actor_user_id == str(user.id)
    assert logs[0].target_id == str(org.id)
    assert member.role == "owner"


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_domain_mutation(db_session, monkeypatch):
    user_id = uuid4()
    org_id = uuid4()
    project_id = uuid4()
    repo_id = uuid4()
    finding_id = uuid4()

    db_session.add_all(
        [
            User(
                id=str(user_id),
                auth_provider_user_id="sub-rev-1",
                email="reviewer@example.com",
                name="Reviewer",
                is_active=True,
            ),
            Organization(
                id=str(org_id),
                name="Org",
                slug="org",
                created_by_user_id=str(user_id),
            ),
            OrganizationMember(
                id=str(uuid4()),
                organization_id=str(org_id),
                user_id=str(user_id),
                role="security_reviewer",
            ),
            Project(
                id=str(project_id),
                organization_id=str(org_id),
                name="Proj",
                slug="proj",
                created_by_user_id=str(user_id),
            ),
            Repository(
                id=str(repo_id),
                project_id=str(project_id),
                provider="github",
                owner_name="acme",
                repo_name="api",
                full_name="acme/api",
                default_branch="main",
            ),
            Finding(
                id=str(finding_id),
                project_id=str(project_id),
                repository_id=str(repo_id),
                category="vulnerability",
                severity="high",
                status="open",
                title="CVE-2026-0001",
                canonical_fingerprint="fp-atomic-audit",
                primary_scanner="trivy",
            ),
        ]
    )
    await db_session.commit()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("injected audit persistence failure")

    monkeypatch.setattr(AuditLogService, "record", _boom)

    with pytest.raises(RuntimeError, match="injected audit persistence failure"):
        await FindingService(db_session).suppress(
            finding_id,
            user_id,
            "false positive",
            organization_id=org_id,
            project_id=project_id,
        )

    await db_session.rollback()
    persisted = await db_session.get(Finding, str(finding_id))
    assert persisted is not None
    assert persisted.status == "open"
    events = (
        await db_session.execute(
            select(FindingEvent).where(FindingEvent.finding_id == str(finding_id))
        )
    ).scalars().all()
    assert events == []


@pytest.mark.asyncio
async def test_project_audit_query_returns_only_that_projects_events(db_session):
    user_id = uuid4()
    org_id = uuid4()
    proj_a = uuid4()
    proj_b = uuid4()
    repo_a = uuid4()
    repo_b = uuid4()
    finding_a = uuid4()
    finding_b = uuid4()

    db_session.add_all(
        [
            User(
                id=str(user_id),
                auth_provider_user_id="sub-audit-proj",
                email="audit@example.com",
                name="Audit",
                is_active=True,
            ),
            Organization(id=str(org_id), name="Org", slug="org-audit", created_by_user_id=str(user_id)),
            OrganizationMember(
                id=str(uuid4()),
                organization_id=str(org_id),
                user_id=str(user_id),
                role="security_reviewer",
            ),
            Project(
                id=str(proj_a),
                organization_id=str(org_id),
                name="PA",
                slug="pa",
                created_by_user_id=str(user_id),
            ),
            Project(
                id=str(proj_b),
                organization_id=str(org_id),
                name="PB",
                slug="pb",
                created_by_user_id=str(user_id),
            ),
            Repository(
                id=str(repo_a),
                project_id=str(proj_a),
                provider="github",
                owner_name="o",
                repo_name="ra",
                full_name="o/ra",
            ),
            Repository(
                id=str(repo_b),
                project_id=str(proj_b),
                provider="github",
                owner_name="o",
                repo_name="rb",
                full_name="o/rb",
            ),
            Finding(
                id=str(finding_a),
                project_id=str(proj_a),
                repository_id=str(repo_a),
                category="vulnerability",
                severity="high",
                status="open",
                title="FA",
                canonical_fingerprint="fp-fa",
                primary_scanner="trivy",
            ),
            Finding(
                id=str(finding_b),
                project_id=str(proj_b),
                repository_id=str(repo_b),
                category="vulnerability",
                severity="high",
                status="open",
                title="FB",
                canonical_fingerprint="fp-fb",
                primary_scanner="trivy",
            ),
        ]
    )
    await db_session.commit()

    finding_service = FindingService(db_session)
    await finding_service.suppress(
        finding_a,
        user_id,
        "fp in A",
        project_id=proj_a,
        organization_id=org_id,
    )
    await finding_service.suppress(
        finding_b,
        user_id,
        "fp in B",
        project_id=proj_b,
        organization_id=org_id,
    )

    audit_service = AuditLogService(db_session)
    proj_a_logs, proj_a_total = await audit_service.list_for_project(proj_a, user_id)
    assert proj_a_total == 1
    assert len(proj_a_logs) == 1
    assert proj_a_logs[0].target_id == str(finding_a)


@pytest.mark.asyncio
async def test_audit_log_context_is_request_local_across_concurrent_coroutines():
    import asyncio
    from app.middleware.audit import audit_context

    results: dict[str, tuple[str | None, str | None]] = {}

    async def worker(name: str, user_id: str, org_id: str):
        audit_context.clear()
        audit_context.set(user_id=user_id, org_id=org_id)
        await asyncio.sleep(0.01)
        results[name] = (audit_context.user_id, audit_context.org_id)

    await asyncio.gather(
        worker("req_a", "user-a", "org-a"),
        worker("req_b", "user-b", "org-b"),
    )
    assert results["req_a"] == ("user-a", "org-a")
    assert results["req_b"] == ("user-b", "org-b")


