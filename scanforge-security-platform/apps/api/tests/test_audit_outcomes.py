from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware import audit

from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.routes import organizations, scan_schedules, suppression_rules
from app.core.identity import auth_subject_to_user_id
from app.db.models import AuditLog, Organization, OrganizationMember, User
from app.db.session import get_db
from app.middleware import auth
from app.services.audit_logs import AuditLogService
from test_transactional_audit import db_session  # noqa: F401


@pytest.fixture
async def audit_app(db_session, monkeypatch):
    user_id = str(auth_subject_to_user_id("audit-asgi-user"))
    org_id = str(uuid4())
    db_session.add(User(id=user_id, auth_provider_user_id="audit-asgi-user",
                        email="audit@example.com", is_active=True))
    await db_session.commit()
    db_session.add(Organization(id=org_id, name="Audit", slug="audit", created_by_user_id=user_id))
    await db_session.commit()
    db_session.add(OrganizationMember(organization_id=org_id, user_id=user_id, role="viewer"))
    await db_session.commit()
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(audit, "AsyncSessionLocal", factory)

    async def database():
        async with factory() as session:
            yield session

    async def verify_token(*_args):
        return {"sub": "audit-asgi-user", "email": "audit@example.com"}

    monkeypatch.setattr(auth, "verify_token", verify_token)
    app = FastAPI()
    app.add_middleware(audit.AuditMiddleware)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[auth.get_jwks_client] = lambda: None
    app.include_router(organizations.router, prefix="/api/v1/organizations")
    app.include_router(suppression_rules.router, prefix="/api/v1")
    app.include_router(scan_schedules.router, prefix=(
        "/api/v1/organizations/{org_id}/projects/{project_id}/repositories/{repo_id}/schedules"
    ))
    return app, org_id, user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", ["suppression-rules", "schedules"])
@pytest.mark.parametrize("authenticated", [False, True])
async def test_asgi_collection_failures_persist_nullable_actor_and_target(
    audit_app, db_session, resource, authenticated,
):
    app, org_id, user_id = audit_app
    path = f"/api/v1/organizations/{org_id}"
    if resource == "schedules":
        path += f"/projects/{uuid4()}/repositories/{uuid4()}"
    path += f"/{resource}" + ("/" if resource == "schedules" else "")
    headers = {"Authorization": "Bearer fixture"} if authenticated else {}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post(path, json={}, headers=headers)
    assert response.status_code == (422 if authenticated else 401)
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_user_id == (user_id if authenticated else None)
    assert row.metadata_json["status_code"] == response.status_code
    assert row.target_type == {"schedules": "schedule", "suppression-rules": "suppression_rule"}[resource]
    assert row.target_id is None
    assert row.organization_id == (org_id if authenticated else None)


@pytest.mark.asyncio
@pytest.mark.parametrize("member", [True, False])
async def test_asgi_denied_mutation_only_attributes_verified_membership(audit_app, db_session, member):
    app, org_id, user_id = audit_app
    requested_org = org_id if member else str(uuid4())
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.patch(f"/api/v1/organizations/{requested_org}",
                                      json={"name": "Denied"}, headers={"Authorization": "Bearer fixture"})
    assert response.status_code == 403
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].actor_user_id == user_id
    assert rows[0].organization_id == (org_id if member else None)
    assert rows[0].metadata_json["status_code"] == 403


@pytest.mark.asyncio
async def test_asgi_transactional_success_has_one_persisted_audit(audit_app, db_session):
    app, _, user_id = audit_app
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/v1/organizations/", json={"name": "Created", "slug": "created"},
                                     headers={"Authorization": "Bearer fixture"})
    assert response.status_code == 201
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].action == "organization_created"
    assert rows[0].actor_user_id == user_id
    assert rows[0].target_id == response.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("peer", "expected"), [("203.0.113.9", "203.0.113.9"), ("127.0.0.1", "198.51.100.8")])
async def test_asgi_audit_uses_trusted_client_ip(audit_app, db_session, monkeypatch, peer, expected):
    app, org_id, _ = audit_app
    monkeypatch.setattr(audit.settings, "TRUSTED_PROXY_IPS", "127.0.0.1")
    async with AsyncClient(transport=ASGITransport(app, client=(peer, 1234)), base_url="http://test") as client:
        response = await client.patch(f"/api/v1/organizations/{org_id}", json={},
                                      headers={"X-Forwarded-For": "192.0.2.66, 198.51.100.8"})
    assert response.status_code == 401
    row = (await db_session.execute(select(AuditLog))).scalar_one()
    assert row.ip_address == expected


@pytest.mark.asyncio
async def test_asgi_invalid_path_does_not_persist_raw_secrets(audit_app, db_session):
    app, _, _ = audit_app
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.patch("/api/v1/organizations/SECRET_PATH_TOKEN?token=SECRET_QUERY_TOKEN",
                                      json={}, headers={"Authorization": "Bearer fixture"})
    assert response.status_code == 422
    row = (await db_session.execute(select(AuditLog))).scalar_one()
    assert row.target_id is None
    assert "SECRET" not in str(row.metadata_json)
    assert row.metadata_json["path"] == "/{org_id}"


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 403])
async def test_asgi_rolled_back_audit_does_not_suppress_outcome(audit_app, db_session, status):
    app, _, _ = audit_app

    @app.post("/api/v1/organizations/rollback")
    async def rollback(db=Depends(get_db)):
        await AuditLogService(db).create(None, "rolled_back", "organization", commit=False)
        await db.rollback()
        # A later unrelated commit must not mark the discarded audit as durable.
        await db.commit()
        if status == 403:
            raise HTTPException(403)
        return {}

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/v1/organizations/rollback")
    assert response.status_code == status
    row = (await db_session.execute(select(AuditLog))).scalar_one()
    assert row.action == "create"
    assert row.metadata_json["status_code"] == status


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
