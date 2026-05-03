from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

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
from app.api.v1 import route_auth
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
    assert exc_info.value.detail == "Developer, admin, or owner role required to trigger scans"
    org_service.user_has_permission.assert_awaited_once_with(
        org_id, current_user.user_id, ["owner", "admin", "developer"]
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
