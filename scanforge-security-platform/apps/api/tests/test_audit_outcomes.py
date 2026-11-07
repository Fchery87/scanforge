from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import audit


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 401, 403, 422, 500])
@pytest.mark.parametrize("resource", ["suppression-rules", "schedules"])
async def test_mutation_outcomes_are_audited(monkeypatch, status, resource):
    rows = []

    @asynccontextmanager
    async def session():
        yield None

    async def create(_self, **kwargs):
        rows.append(kwargs)

    monkeypatch.setattr(audit, "AsyncSessionLocal", session)
    monkeypatch.setattr(audit.AuditLogService, "create", create)
    request = Request({
        "type": "http", "method": "POST",
        "path": f"/api/v1/organizations/{uuid4()}/{resource}", "headers": [],
    })
    if status != 401:
        request.state.audit_user_id = str(uuid4())

    async def respond(_request):
        return Response(status_code=status)

    response = await audit.AuditMiddleware(None).dispatch(request, respond)
    assert response.status_code == status
    assert len(rows) == 1
    assert rows[0]["metadata_json"]["status_code"] == status
    if status == 401:
        assert rows[0]["actor_user_id"] is None


@pytest.mark.parametrize(
    ("resource", "expected"),
    [("suppression-rules", "suppression_rule"), ("schedules", "schedule")],
)
def test_audit_targets_deepest_resource(resource, expected):
    target = str(uuid4())
    path = f"/api/v1/organizations/{uuid4()}/{resource}/{target}"
    assert audit.AuditMiddleware(None)._extract_target(path) == {"type": expected, "id": target}


@pytest.mark.asyncio
async def test_transactional_success_is_not_duplicated(monkeypatch):
    def forbidden_session():
        pytest.fail("transactional audit must not be duplicated")

    monkeypatch.setattr(audit, "AsyncSessionLocal", forbidden_session)
    request = Request({"type": "http", "method": "PUT", "path": "/api/v1/organizations", "headers": []})
    request.state.audit_recorded_in_tx = True

    async def respond(_request):
        return Response(status_code=200)

    assert (await audit.AuditMiddleware(None).dispatch(request, respond)).status_code == 200


@pytest.mark.asyncio
async def test_audit_failure_warning_does_not_leak_exception(monkeypatch, caplog):
    @asynccontextmanager
    async def session():
        raise RuntimeError("SECRET_DATABASE_PAYLOAD")
        yield

    monkeypatch.setattr(audit, "AsyncSessionLocal", session)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/organizations", "headers": []})
    request.state.audit_user_id = str(uuid4())

    async def respond(_request):
        return Response(status_code=200)

    await audit.AuditMiddleware(None).dispatch(request, respond)
    assert "SECRET_DATABASE_PAYLOAD" not in caplog.text
    assert caplog.records[0].event == "audit_write_failed"
    assert caplog.records[0].exc_info is None
