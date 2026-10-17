from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import get_current_user


@pytest.mark.asyncio
async def test_repository_connect_returns_403_for_viewer_member(monkeypatch):
    from app.api.v1 import route_auth
    from app.api.v1.routes import repositories

    org_id = uuid4()
    project_id = uuid4()
    user_id = uuid4()

    async def override_current_user():
        return SimpleNamespace(user_id=user_id, role="viewer")

    app.dependency_overrides[get_current_user] = override_current_user

    monkeypatch.setattr(
        route_auth,
        "get_project_in_org_for_user",
        AsyncMock(return_value=SimpleNamespace(id=project_id, organization_id=org_id)),
    )
    monkeypatch.setattr(
        repositories,
        "OrganizationService",
        lambda db: SimpleNamespace(user_has_permission=AsyncMock(return_value=False)),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/v1/organizations/{org_id}/projects/{project_id}/repositories/",
            json={
                "provider": "github",
                "owner_name": "scanforge",
                "repo_name": "platform",
                "full_name": "scanforge/platform",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["detail"] == "Only owners and admins can connect repositories"


@pytest.mark.asyncio
async def test_deactivated_user_with_valid_token_is_rejected_at_auth_boundary(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import HTTPException
    from app.middleware import auth as auth_module

    async def fake_verify_token(_token: str, _jwks_client=None):
        return {"sub": "auth0|deactivated-user", "email": "disabled@example.com"}

    class DeactivatedUserService:
        def __init__(self, _db):
            pass

        async def get_or_create_from_token(self, _payload):
            return SimpleNamespace(id=str(uuid4()), is_active=False)

    monkeypatch.setattr(auth_module, "verify_token", fake_verify_token)
    monkeypatch.setattr(auth_module, "UserService", DeactivatedUserService)

    with pytest.raises(HTTPException) as exc_info:
        await auth_module.get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-jwt"),
            _jwks_client=object(),
            db=None,
        )

    assert exc_info.value.status_code == 403
    assert "deactivated" in exc_info.value.detail.lower()

