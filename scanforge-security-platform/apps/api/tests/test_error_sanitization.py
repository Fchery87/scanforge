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
    monkeypatch.setattr(
        scans, "ScanService", lambda _db: SimpleNamespace(create=AsyncMock(return_value=(scan, None, None)))
    )

    class FailingQueueClient:
        def __init__(self, redis_url: str, redis_token: str):
            pass

        async def enqueue(self, job_type: str, payload: dict):
            raise RuntimeError("Authorization header contained invalid token")

    import sys
    import types

    queue_module = types.ModuleType("app.clients.queue")
    queue_module.QueueClient = FailingQueueClient
    monkeypatch.setitem(sys.modules, "app.clients.queue", queue_module)

    response = await scans.create_scan(
        org_id=org_id,
        project_id=project_id,
        data=SimpleNamespace(repository_id=repository_id, scan_type="full"),
        current_user=current_user,
        db=db,
    )

    assert response.error_message == GENERIC_QUEUE_ERROR
    assert response.status == "failed"
