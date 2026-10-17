from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import route_auth
from app.api.v1.routes import (
    audit_logs,
    exports,
    findings,
    findings_trend,
    github,
    organizations,
    projects,
    repositories,
    scan_schedules,
    scans,
    scorecard,
)
from app.schemas.exports import ExportCreate
from app.schemas.findings import FindingSuppress
from app.schemas.projects import ProjectCreate
from app.schemas.repositories import RepositoryConnect
from app.schemas.scans import ScanCreate


def _current_user(role: str = "viewer") -> SimpleNamespace:
    return SimpleNamespace(user_id=uuid4(), role=role)


def _patch_project_access(monkeypatch, project):
    monkeypatch.setattr(route_auth, "get_project_in_org_for_user", AsyncMock(return_value=project))


def _patch_repository_access(monkeypatch, repo):
    monkeypatch.setattr(route_auth, "get_repository_in_project_for_user", AsyncMock(return_value=repo))


@pytest.mark.asyncio
async def test_delete_organization_requires_org_permission_not_token_role(monkeypatch):
    org_id = uuid4()
    current_user = _current_user(role="owner")

    org_service = SimpleNamespace(user_has_permission=AsyncMock(return_value=False))
    monkeypatch.setattr(organizations, "OrganizationService", lambda db: org_service)

    with pytest.raises(HTTPException) as exc_info:
        await organizations.delete_organization(org_id=org_id, current_user=current_user, db=object())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only owners can delete organizations"
    org_service.user_has_permission.assert_awaited_once_with(org_id, current_user.user_id, ["owner"])


@pytest.mark.asyncio
async def test_create_project_rejects_mismatched_org_id_in_body(monkeypatch):
    path_org_id = uuid4()
    body_org_id = uuid4()
    current_user = _current_user(role="admin")

    monkeypatch.setattr(projects, "OrganizationService", lambda db: SimpleNamespace(user_has_permission=AsyncMock()))

    with pytest.raises(HTTPException) as exc_info:
        await projects.create_project(
            org_id=path_org_id,
            data=ProjectCreate(name="Project Atlas", slug="project-atlas", organization_id=body_org_id),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 400
    assert "must match" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_project_rejects_project_outside_org_path(monkeypatch):
    org_id = uuid4()
    other_org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user()

    project_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=project_id, organization_id=other_org_id))
    )
    monkeypatch.setattr(projects, "ProjectService", lambda db: project_service)

    with pytest.raises(HTTPException) as exc_info:
        await projects.get_project(org_id=org_id, project_id=project_id, current_user=current_user, db=object())

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_connect_repository_requires_admin_or_owner(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user(role="viewer")
    project = SimpleNamespace(id=project_id, organization_id=org_id)

    _patch_project_access(monkeypatch, project)
    org_service = SimpleNamespace(user_has_permission=AsyncMock(return_value=False))
    monkeypatch.setattr(repositories, "OrganizationService", lambda db: org_service)

    with pytest.raises(HTTPException) as exc_info:
        await repositories.connect_repository(
            org_id=org_id,
            project_id=project_id,
            data=RepositoryConnect(
                provider="github",
                owner_name="scanforge",
                repo_name="platform",
                full_name="scanforge/platform",
            ),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only owners and admins can connect repositories"
    org_service.user_has_permission.assert_awaited_once_with(org_id, current_user.user_id, ["owner", "admin"])


@pytest.mark.asyncio
async def test_create_scan_requires_developer_or_higher(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    current_user = _current_user(role="viewer")
    project = SimpleNamespace(id=project_id, organization_id=org_id)

    _patch_project_access(monkeypatch, project)
    org_service = SimpleNamespace(user_has_permission=AsyncMock(return_value=False))
    monkeypatch.setattr(scans, "OrganizationService", lambda db: org_service)

    with pytest.raises(HTTPException) as exc_info:
        await scans.create_scan(
            org_id=org_id,
            project_id=project_id,
            data=ScanCreate(repository_id=repository_id),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Developer, security reviewer, admin, or owner role required to trigger scans"
    org_service.user_has_permission.assert_awaited_once_with(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer", "developer"]
    )


@pytest.mark.asyncio
async def test_scorecard_rejects_project_outside_org_path(monkeypatch):
    org_id = uuid4()
    other_org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user()
    project = SimpleNamespace(id=project_id, organization_id=other_org_id)

    _patch_project_access(monkeypatch, None)

    with pytest.raises(HTTPException) as exc_info:
        await scorecard.get_project_scorecard(
            org_id=org_id, project_id=project_id, current_user=current_user, db=object()
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_findings_trend_rejects_project_outside_org_path(monkeypatch):
    org_id = uuid4()
    other_org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user()
    project = SimpleNamespace(id=project_id, organization_id=other_org_id)

    _patch_project_access(monkeypatch, None)

    with pytest.raises(HTTPException) as exc_info:
        await findings_trend.get_findings_trend(
            org_id=org_id, project_id=project_id, current_user=current_user, db=object()
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_create_export_requires_security_reviewer_or_higher(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user(role="developer")
    project = SimpleNamespace(id=project_id, organization_id=org_id)

    monkeypatch.setattr(exports, "require_beta_capability", lambda *_args, **_kwargs: None)
    _patch_project_access(monkeypatch, project)
    org_service = SimpleNamespace(user_has_permission=AsyncMock(return_value=False))
    monkeypatch.setattr(exports, "OrganizationService", lambda db: org_service)

    with pytest.raises(HTTPException) as exc_info:
        await exports.create_export(
            org_id=org_id,
            project_id=project_id,
            data=ExportCreate(export_type="findings", format="csv"),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Security reviewer, admin, or owner role required to create exports"
    org_service.user_has_permission.assert_awaited_once_with(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer"]
    )


@pytest.mark.asyncio
async def test_download_export_rejects_project_outside_org_path(monkeypatch):
    org_id = uuid4()
    other_org_id = uuid4()
    project_id = uuid4()
    export_id = uuid4()
    current_user = _current_user()
    project = SimpleNamespace(id=project_id, organization_id=other_org_id)

    monkeypatch.setattr(exports, "require_beta_capability", lambda *_args, **_kwargs: None)
    _patch_project_access(monkeypatch, None)

    with pytest.raises(HTTPException) as exc_info:
        await exports.download_export(
            org_id=org_id,
            project_id=project_id,
            export_id=export_id,
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_suppress_finding_requires_security_reviewer_or_higher(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    finding_id = uuid4()
    current_user = _current_user(role="developer")
    project = SimpleNamespace(id=project_id, organization_id=org_id)

    monkeypatch.setattr(findings, "get_project_in_org_for_user", AsyncMock(return_value=project))
    org_service = SimpleNamespace(user_has_permission=AsyncMock(return_value=False))
    monkeypatch.setattr(findings, "OrganizationService", lambda db: org_service)

    with pytest.raises(HTTPException) as exc_info:
        await findings.suppress_finding(
            org_id=org_id,
            project_id=project_id,
            finding_id=finding_id,
            data=FindingSuppress(reason="accepted false positive"),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Security reviewer, admin, or owner role required to modify findings"
    org_service.user_has_permission.assert_awaited_once_with(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer"]
    )


@pytest.mark.asyncio
async def test_project_audit_logs_reject_project_outside_org_path(monkeypatch):
    org_id = uuid4()
    other_org_id = uuid4()
    project_id = uuid4()
    current_user = _current_user()
    project = SimpleNamespace(id=project_id, organization_id=other_org_id)

    _patch_project_access(monkeypatch, None)

    with pytest.raises(HTTPException) as exc_info:
        await audit_logs.list_audit_logs_project(
            org_id=org_id,
            project_id=project_id,
            current_user=current_user,
            pagination=SimpleNamespace(skip=0, limit=50),
            action=None,
            db=object(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_update_schedule_rejects_schedule_outside_repo_path(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repo_id = uuid4()
    other_repo_id = uuid4()
    schedule_id = uuid4()
    current_user = _current_user()
    repo = SimpleNamespace(id=repo_id, project_id=project_id)
    schedule = SimpleNamespace(id=schedule_id, repository_id=other_repo_id)

    monkeypatch.setattr(scan_schedules, "require_beta_capability", lambda *_args, **_kwargs: None)
    _patch_project_access(monkeypatch, SimpleNamespace(id=project_id, organization_id=org_id))
    _patch_repository_access(monkeypatch, repo)
    monkeypatch.setattr(
        scan_schedules,
        "ScanScheduleService",
        lambda db: SimpleNamespace(get_by_id=AsyncMock(return_value=schedule), update=AsyncMock()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await scan_schedules.update_schedule(
            org_id=org_id,
            project_id=project_id,
            repo_id=repo_id,
            schedule_id=schedule_id,
            data=scan_schedules.ScanScheduleUpdate(),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Schedule not found in this repository"


@pytest.mark.asyncio
async def test_github_oauth_callback_rejects_invalid_state_uuid(monkeypatch):
    current_user = _current_user(role="admin")
    monkeypatch.setattr(github.settings, "CORS_ORIGINS", "https://app.scanforge.dev")

    with pytest.raises(HTTPException) as exc_info:
        await github.github_oauth_callback(
            data=github.GitHubOAuthCallbackRequest(code="oauth-code", state="not-a-uuid"),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid OAuth state"


@pytest.mark.asyncio
async def test_delete_schedule_rejects_schedule_outside_repo_path(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repo_id = uuid4()
    other_repo_id = uuid4()
    schedule_id = uuid4()
    current_user = _current_user()
    repo = SimpleNamespace(id=repo_id, project_id=project_id)
    schedule = SimpleNamespace(id=schedule_id, repository_id=other_repo_id)

    monkeypatch.setattr(scan_schedules, "require_beta_capability", lambda *_args, **_kwargs: None)
    _patch_project_access(monkeypatch, SimpleNamespace(id=project_id, organization_id=org_id))
    _patch_repository_access(monkeypatch, repo)
    monkeypatch.setattr(
        scan_schedules,
        "ScanScheduleService",
        lambda db: SimpleNamespace(get_by_id=AsyncMock(return_value=schedule), delete=AsyncMock()),
    )

    with pytest.raises(HTTPException) as exc_info:
        await scan_schedules.delete_schedule(
            org_id=org_id,
            project_id=project_id,
            repo_id=repo_id,
            schedule_id=schedule_id,
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Schedule not found in this repository"


from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PGUUID
from sqlalchemy.ext.compiler import compiles
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


def _downcast_postgres_uuid_columns(metadata) -> None:
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


@pytest.mark.asyncio
async def test_privileged_org_a_viewer_org_b_cannot_mutate_org_b_finding_before_denial():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.db.models  # noqa: F401
    from app.db.base import Base
    from app.db.models import Finding, FindingEvent, Organization, OrganizationMember, Project, Repository, User
    from app.services.findings import FindingAuthorizationError, FindingService

    _downcast_postgres_uuid_columns(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    user_id = uuid4()
    org_a = uuid4()
    proj_a = uuid4()
    org_b = uuid4()
    proj_b = uuid4()
    repo_b = uuid4()
    finding_b = uuid4()

    async with session_factory() as db:
        db.add_all(
            [
                User(
                    id=str(user_id),
                    auth_provider_user_id="sub-cross-org",
                    email="attacker@example.com",
                    name="Attacker",
                    is_active=True,
                ),
                Organization(id=str(org_a), name="Org A", slug="org-a", created_by_user_id=str(user_id)),
                Organization(id=str(org_b), name="Org B", slug="org-b", created_by_user_id=str(user_id)),
                OrganizationMember(
                    id=str(uuid4()),
                    organization_id=str(org_a),
                    user_id=str(user_id),
                    role="security_reviewer",
                ),
                OrganizationMember(
                    id=str(uuid4()),
                    organization_id=str(org_b),
                    user_id=str(user_id),
                    role="viewer",
                ),
                Project(
                    id=str(proj_a),
                    organization_id=str(org_a),
                    name="Proj A",
                    slug="proj-a",
                    created_by_user_id=str(user_id),
                ),
                Project(
                    id=str(proj_b),
                    organization_id=str(org_b),
                    name="Proj B",
                    slug="proj-b",
                    created_by_user_id=str(user_id),
                ),
                Repository(
                    id=str(repo_b),
                    project_id=str(proj_b),
                    provider="github",
                    owner_name="org-b",
                    repo_name="repo-b",
                    full_name="org-b/repo-b",
                ),
                Finding(
                    id=str(finding_b),
                    project_id=str(proj_b),
                    repository_id=str(repo_b),
                    category="vulnerability",
                    severity="critical",
                    status="open",
                    title="Org B Critical Finding",
                    canonical_fingerprint="fp-org-b",
                    primary_scanner="trivy",
                ),
            ]
        )
        await db.commit()

        # Route-level attempt using Org A / Proj A URL path with Finding B ID:
        with pytest.raises(HTTPException) as route_exc:
            await findings.suppress_finding(
                org_id=org_a,
                project_id=proj_a,
                finding_id=finding_b,
                data=FindingSuppress(reason="cross-tenant suppress attempt"),
                current_user=SimpleNamespace(user_id=user_id, role="security_reviewer"),
                db=db,
            )
        assert route_exc.value.status_code == 404

        # Direct service-level attempt by viewer in Org B:
        with pytest.raises(FindingAuthorizationError):
            await FindingService(db).suppress(
                finding_b,
                user_id,
                "viewer direct suppress attempt",
            )

        # Verify Finding B was NEVER mutated in database!
        persisted = await db.get(Finding, str(finding_b))
        assert persisted is not None
        assert persisted.status == "open"
        from sqlalchemy import select

        events = (
            await db.execute(select(FindingEvent).where(FindingEvent.finding_id == str(finding_b)))
        ).scalars().all()
        assert events == []

    await engine.dispose()


@pytest.mark.asyncio
async def test_bulk_finding_mutation_rolls_back_all_when_any_item_is_outside_scope():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.db.models  # noqa: F401
    from app.db.base import Base
    from app.db.models import Finding, Organization, OrganizationMember, Project, Repository, User
    from app.services.findings import FindingService

    _downcast_postgres_uuid_columns(Base.metadata)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    user_id = uuid4()
    org_id = uuid4()
    proj_1 = uuid4()
    proj_2 = uuid4()
    repo_1 = uuid4()
    repo_2 = uuid4()
    f1 = uuid4()
    f2 = uuid4()

    async with session_factory() as db:
        db.add_all(
            [
                User(
                    id=str(user_id),
                    auth_provider_user_id="sub-bulk-rev",
                    email="rev@example.com",
                    name="Rev",
                    is_active=True,
                ),
                Organization(id=str(org_id), name="Org", slug="org", created_by_user_id=str(user_id)),
                OrganizationMember(
                    id=str(uuid4()),
                    organization_id=str(org_id),
                    user_id=str(user_id),
                    role="security_reviewer",
                ),
                Project(
                    id=str(proj_1),
                    organization_id=str(org_id),
                    name="P1",
                    slug="p1",
                    created_by_user_id=str(user_id),
                ),
                Project(
                    id=str(proj_2),
                    organization_id=str(org_id),
                    name="P2",
                    slug="p2",
                    created_by_user_id=str(user_id),
                ),
                Repository(
                    id=str(repo_1),
                    project_id=str(proj_1),
                    provider="github",
                    owner_name="o",
                    repo_name="r1",
                    full_name="o/r1",
                ),
                Repository(
                    id=str(repo_2),
                    project_id=str(proj_2),
                    provider="github",
                    owner_name="o",
                    repo_name="r2",
                    full_name="o/r2",
                ),
                Finding(
                    id=str(f1),
                    project_id=str(proj_1),
                    repository_id=str(repo_1),
                    category="vulnerability",
                    severity="high",
                    status="open",
                    title="F1",
                    canonical_fingerprint="fp-f1",
                    primary_scanner="trivy",
                ),
                Finding(
                    id=str(f2),
                    project_id=str(proj_2),
                    repository_id=str(repo_2),
                    category="vulnerability",
                    severity="high",
                    status="open",
                    title="F2",
                    canonical_fingerprint="fp-f2",
                    primary_scanner="trivy",
                ),
            ]
        )
        await db.commit()

        with pytest.raises(ValueError, match="not found in the authorized scope"):
            await FindingService(db).bulk_suppress(
                [f1, f2],
                user_id,
                "bulk suppress",
                project_id=proj_1,
                organization_id=org_id,
            )

        p1_finding = await db.get(Finding, str(f1))
        p2_finding = await db.get(Finding, str(f2))
        assert p1_finding is not None and p1_finding.status == "open"
        assert p2_finding is not None and p2_finding.status == "open"

    await engine.dispose()

