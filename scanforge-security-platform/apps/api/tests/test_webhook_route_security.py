from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1.routes import webhooks


class _FakeDB:
    def __init__(self, *, repo, project, integration, flush_error=None):
        self.repo = repo
        self.project = project
        self.integration = integration
        self.flush_error = flush_error
        self.added = []
        self.rolled_back = False
        self.committed = False

    async def get(self, model, value):
        if model is webhooks.Repository:
            return self.repo
        if model is webhooks.Project:
            return self.project
        return None

    async def scalar(self, _query):
        return self.integration

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        if self.flush_error:
            raise self.flush_error

    async def rollback(self):
        self.rolled_back = True

    async def commit(self):
        self.committed = True


class _FakeRequest:
    def __init__(self, payload, *, event="push", delivery="delivery-1"):
        self._payload = payload
        self.headers = {
            "x-github-event": event,
            "x-github-delivery": delivery,
        }

    async def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_github_webhook_rejects_repository_mismatch(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id, project_id=project_id, full_name="scanforge/platform", external_repo_id="42"
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")
    db = _FakeDB(repo=repo, project=project, integration=integration)
    request = _FakeRequest(
        {
            "ref": "refs/heads/main",
            "after": "deadbeef",
            "repository": {"full_name": "other/repo", "id": 42},
            "installation": {"id": 99},
        }
    )

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.github_webhook(
            org_id=org_id, project_id=project_id, repository_id=repository_id, request=request, db=db
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Webhook repository mismatch"


@pytest.mark.asyncio
async def test_github_webhook_rejects_duplicate_delivery(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id, project_id=project_id, full_name="scanforge/platform", external_repo_id="42"
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")
    db = _FakeDB(
        repo=repo,
        project=project,
        integration=integration,
        flush_error=IntegrityError("duplicate", params={}, orig=Exception("duplicate")),
    )
    request = _FakeRequest(
        {
            "ref": "refs/heads/main",
            "after": "deadbeef",
            "repository": {"full_name": "scanforge/platform", "id": 42},
            "installation": {"id": 99},
        }
    )

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))

    with pytest.raises(HTTPException) as exc_info:
        await webhooks.github_webhook(
            org_id=org_id, project_id=project_id, repository_id=repository_id, request=request, db=db
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Duplicate webhook delivery"
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_github_webhook_queues_scan_for_matching_payload(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id, project_id=project_id, full_name="scanforge/platform", external_repo_id="42"
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")
    db = _FakeDB(repo=repo, project=project, integration=integration)
    request = _FakeRequest(
        {
            "ref": "refs/heads/main",
            "after": "deadbeef",
            "repository": {"full_name": "scanforge/platform", "id": 42},
            "installation": {"id": 99},
        }
    )
    fake_scan = SimpleNamespace(id=uuid4())
    scan_service = SimpleNamespace(create=AsyncMock(return_value=(fake_scan, repo, project)))
    audit_service = SimpleNamespace(create=AsyncMock())

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "ScanService", lambda _db: scan_service)
    monkeypatch.setattr(webhooks, "AuditLogService", lambda _db: audit_service)

    response = await webhooks.github_webhook(
        org_id=org_id,
        project_id=project_id,
        repository_id=repository_id,
        request=request,
        db=db,
    )

    assert response == {"status": "queued", "scan_id": str(fake_scan.id)}
    scan_service.create.assert_awaited_once()
