from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import audit


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 403, 422, 500])
@pytest.mark.parametrize("resource", ["suppression-rules", "schedules"])
async def test_mutation_outcomes_are_audited(monkeypatch, status, resource):
    rows = []

    @asynccontextmanager
    async def session():
        yield None

    async def create(self, **kwargs):
        rows.append(kwargs)

    monkeypatch.setattr(audit, "AsyncSessionLocal", session)
    monkeypatch.setattr(audit.AuditLogService, "create", create)
    request = Request({"type": "http", "method": "POST", "path": f"/api/v1/organizations/{uuid4()}/{resource}", "headers": []})
    request.state.audit_user_id = str(uuid4())

    async def respond(request):
        return Response(status_code=status)

    response = await audit.AuditMiddleware(None).dispatch(request, respond)
    assert response.status_code == status
    assert len(rows) == 1
    assert rows[0]["metadata_json"]["status_code"] == status


@pytest.mark.asyncio
async def test_audit_failure_warning_does_not_leak_exception(monkeypatch, caplog):
    @asynccontextmanager
    async def session():
        raise RuntimeError("SECRET_DATABASE_PAYLOAD")
        yield

    monkeypatch.setattr(audit, "AsyncSessionLocal", session)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/organizations", "headers": []})
    request.state.audit_user_id = str(uuid4())

    async def respond(request):
        return Response(status_code=200)

    await audit.AuditMiddleware(None).dispatch(request, respond)
    assert "SECRET_DATABASE_PAYLOAD" not in caplog.text
    assert caplog.records[0].event == "audit_write_failed"
    assert caplog.records[0].exc_info is None
