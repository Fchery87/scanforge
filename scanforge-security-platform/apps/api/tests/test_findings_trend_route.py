from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.routes import findings_trend
from app.db.session import get_db
from app.main import app
from app.middleware.auth import UserContext, get_current_user


@pytest.mark.asyncio
async def test_assembled_router_reaches_findings_trend_before_finding_id(monkeypatch):
    org_id = uuid4()
    project_id = uuid4()
    current_user = UserContext(sub="auth0|trend-user", email="trend@example.com", role="developer")
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))

    async def override_current_user():
        return current_user

    async def override_db():
        yield db

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(
        findings_trend,
        "get_project_in_org_or_404",
        AsyncMock(return_value=SimpleNamespace(id=project_id, organization_id=org_id)),
    )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/organizations/{org_id}/projects/{project_id}/findings/trend?days=1"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["days"] == 1
    assert len(body["data"]) == 1
    assert body["data"][0]["count"] == 0
