import unittest.mock
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api.v1.routes import webhooks


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row


class _FakeDB:
    def __init__(self, *, repo, project, integration, flush_error=None, existing_delivery=None):
        self.repo = repo
        self.project = project
        self.integration = integration
        self.flush_error = flush_error
        self.existing_delivery = existing_delivery
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

    async def execute(self, _query):
        return _FakeResult(self.existing_delivery)

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
async def test_github_webhook_duplicate_delivery_replays_original_scan(monkeypatch):
    """Same delivery twice must not create a second scan: D6 requires the original
    business response on identical replay."""
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    original_scan_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id, project_id=project_id, full_name="scanforge/platform", external_repo_id="42"
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")
    existing_delivery = SimpleNamespace(
        delivery_id="delivery-1",
        event_type="push",
        scan_id=original_scan_id,
        response_json={"status": "queued", "scan_id": str(original_scan_id)},
    )
    db = _FakeDB(
        repo=repo,
        project=project,
        integration=integration,
        flush_error=IntegrityError("duplicate", params={}, orig=Exception("duplicate")),
        existing_delivery=existing_delivery,
    )
    request = _FakeRequest(
        {
            "ref": "refs/heads/main",
            "after": "deadbeef",
            "repository": {"full_name": "scanforge/platform", "id": 42},
            "installation": {"id": 99},
        }
    )
    scan_service = SimpleNamespace(create=AsyncMock())
    scan_factory = unittest.mock.Mock(return_value=scan_service)

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "ScanService", scan_factory)

    response = await webhooks.github_webhook(
        org_id=org_id, project_id=project_id, repository_id=repository_id, request=request, db=db
    )

    assert response == {"status": "queued", "scan_id": str(original_scan_id)}
    scan_factory.assert_not_called()
    assert db.rolled_back is True
    assert db.committed is False


@pytest.mark.asyncio
async def test_github_webhook_different_delivery_same_commit_replays_original_scan(monkeypatch):
    """Different delivery id, identical business event content (same commit+event):
    D6 -- "Return original business response on identical replay" -- so the original
    scan is replayed, not duplicated."""
    org_id = uuid4()
    project_id = uuid4()
    repository_id = uuid4()
    original_scan_id = uuid4()
    repo = SimpleNamespace(
        id=repository_id, project_id=project_id, full_name="scanforge/platform", external_repo_id="42"
    )
    project = SimpleNamespace(id=project_id, organization_id=org_id)
    integration = SimpleNamespace(installation_id="99")
    existing_delivery = SimpleNamespace(
        delivery_id="delivery-1",
        event_type="push",
        scan_id=original_scan_id,
        response_json={"status": "queued", "scan_id": str(original_scan_id)},
    )
    db = _FakeDB(
        repo=repo,
        project=project,
        integration=integration,
        flush_error=IntegrityError("duplicate", params={}, orig=Exception("duplicate")),
        existing_delivery=existing_delivery,
    )
    request = _FakeRequest(
        {
            "ref": "refs/heads/main",
            "after": "deadbeef",
            "repository": {"full_name": "scanforge/platform", "id": 42},
            "installation": {"id": 99},
        },
        delivery="delivery-2",
    )
    scan_service = SimpleNamespace(create=AsyncMock())
    scan_factory = unittest.mock.Mock(return_value=scan_service)

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "ScanService", scan_factory)

    response = await webhooks.github_webhook(
        org_id=org_id, project_id=project_id, repository_id=repository_id, request=request, db=db
    )

    assert response == {"status": "queued", "scan_id": str(original_scan_id)}
    scan_factory.assert_not_called()

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


@pytest.mark.asyncio
async def test_github_pull_request_webhook_queues_advisory_diff_scan(monkeypatch):
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
            "action": "synchronize",
            "pull_request": {
                "number": 17,
                "head": {"sha": "cafebabe", "ref": "feature/security"},
                "base": {"sha": "basebeef", "ref": "main"},
            },
            "repository": {"full_name": "scanforge/platform", "id": 42},
            "installation": {"id": 99},
        },
        event="pull_request",
    )
    fake_scan = SimpleNamespace(id=uuid4())
    lifecycle = SimpleNamespace(create_manual_scan=AsyncMock(return_value=fake_scan))
    audit_service = SimpleNamespace(create=AsyncMock())

    monkeypatch.setattr(webhooks, "verify_github_webhook_async", AsyncMock(return_value=True))
    monkeypatch.setattr(webhooks, "ScanLifecycleService", lambda _db: lifecycle)
    monkeypatch.setattr(webhooks, "AuditLogService", lambda _db: audit_service)

    response = await webhooks.github_webhook(
        org_id=org_id,
        project_id=project_id,
        repository_id=repository_id,
        request=request,
        db=db,
    )

    assert response == {
        "status": "queued",
        "scan_id": str(fake_scan.id),
        "advisory": {
            "scan_id": str(fake_scan.id),
            "state": "neutral",
            "blocking": False,
            "summary": "Advisory policy evaluation passed",
        },
    }
    lifecycle.create_manual_scan.assert_awaited_once()
    created_data = lifecycle.create_manual_scan.await_args.kwargs["data"]
    assert created_data.scan_type == "diff"
    assert created_data.trigger_type == "pull_request"
    assert created_data.pull_request_number == 17
    # R10 recorded base/head diff: base_sha persisted alongside commit_sha.
    assert created_data.base_sha == "basebeef"
    assert created_data.commit_sha == "cafebabe"
