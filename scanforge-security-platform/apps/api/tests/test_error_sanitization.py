from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes import github, scans
from app.core.error_messages import GENERIC_EXTERNAL_SERVICE_ERROR, GENERIC_QUEUE_ERROR, safe_error_message


def test_safe_error_message_redacts_sensitive_terms():
    assert safe_error_message("GitHub token exchange failed") != "GitHub token exchange failed"


@pytest.mark.asyncio
async def test_github_repository_errors_are_sanitized(monkeypatch):
    org_id = uuid4()
    current_user = SimpleNamespace(user_id=uuid4())
    org_service = SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=org_id)))
    gh_service = SimpleNamespace(
        get_integration=AsyncMock(return_value=SimpleNamespace(installation_id="123")),
        list_repositories=AsyncMock(side_effect=RuntimeError("GitHub token expired")),
    )

    monkeypatch.setattr(github, "OrganizationService", lambda db: org_service)
    monkeypatch.setattr(github, "GitHubService", lambda db: gh_service)

    with pytest.raises(HTTPException) as exc_info:
        await github.list_github_repositories(org_id=org_id, current_user=current_user, db=object())

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == GENERIC_EXTERNAL_SERVICE_ERROR


@pytest.mark.asyncio
async def test_scan_enqueue_failure_stores_generic_error(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    current_user = SimpleNamespace(user_id=uuid4())
    scan = SimpleNamespace(
        id=uuid4(),
        repository_id=repository_id,
        project_id=project_id,
        branch_name="main",
        commit_sha="deadbeef",
        status="queued",
        error_message=None,
    )
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())

    monkeypatch.setattr(scans, "get_project_in_org_or_404", AsyncMock())
    monkeypatch.setattr(scans, "get_repository_in_project_or_404", AsyncMock())
    monkeypatch.setattr(
        scans,
        "OrganizationService",
        lambda _db: SimpleNamespace(user_has_permission=AsyncMock(return_value=True)),
    )
    scan.status = "failed"
    scan.error_message = GENERIC_QUEUE_ERROR
    lifecycle = SimpleNamespace(create_manual_scan=AsyncMock(return_value=scan))
    monkeypatch.setattr(scans, "ScanLifecycleService", lambda _db: lifecycle)

    response = await scans.create_scan(
        org_id=org_id,
        project_id=project_id,
        data=SimpleNamespace(repository_id=repository_id, scan_type="full"),
        current_user=current_user,
        db=db,
    )

    assert response.error_message == GENERIC_QUEUE_ERROR
    assert response.status == "failed"


_INTERNAL_MARKERS = (
    "Traceback",
    "RuntimeError",
    "ValueError",
    "SELECT",
    "INSERT",
    "/home/",
    ".py:",
    "sqlalchemy",
    "asyncpg",
)


def _assert_no_internal_details(detail: str) -> None:
    for marker in _INTERNAL_MARKERS:
        assert marker.lower() not in str(detail).lower(), f"Response leaks internal detail: {marker!r}"


@pytest.mark.asyncio
async def test_github_oauth_callback_errors_are_sanitized(monkeypatch):
    org_id = uuid4()
    current_user = SimpleNamespace(user_id=uuid4())
    org_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=org_id)),
        user_has_permission=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(github, "OrganizationService", lambda db: org_service)
    monkeypatch.setattr(github, "verify_github_state", lambda *_a, **_kw: None)
    monkeypatch.setattr(github, "_extract_org_id_from_state_or_400", lambda _state: org_id)
    monkeypatch.setattr(
        github,
        "GitHubService",
        lambda db: SimpleNamespace(handle_oauth_callback=AsyncMock(side_effect=RuntimeError("token exchange failed: /home/user/secret.key"))),
    )

    with pytest.raises(HTTPException) as exc_info:
        await github.github_oauth_callback(
            data=SimpleNamespace(code="abc", state="state"),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 502
    _assert_no_internal_details(exc_info.value.detail)


@pytest.mark.asyncio
async def test_github_install_callback_errors_are_sanitized(monkeypatch):
    org_id = uuid4()
    current_user = SimpleNamespace(user_id=uuid4())
    org_service = SimpleNamespace(
        get_by_id=AsyncMock(return_value=SimpleNamespace(id=org_id)),
        user_has_permission=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(github, "OrganizationService", lambda db: org_service)
    monkeypatch.setattr(github, "verify_github_state", lambda *_a, **_kw: None)
    monkeypatch.setattr(github, "_extract_org_id_from_state_or_400", lambda _state: org_id)
    monkeypatch.setattr(
        github,
        "GitHubService",
        lambda db: SimpleNamespace(save_integration=AsyncMock(side_effect=RuntimeError("DB connection refused: SELECT * FROM integrations"))),
    )

    with pytest.raises(HTTPException) as exc_info:
        await github.github_install_callback(
            data=SimpleNamespace(installation_id="999", state="state"),
            current_user=current_user,
            db=object(),
        )

    assert exc_info.value.status_code == 502
    _assert_no_internal_details(exc_info.value.detail)
