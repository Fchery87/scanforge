import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.middleware import auth as auth_module
from app.middleware.auth import get_current_user


@pytest.mark.asyncio
@pytest.mark.parametrize("authenticate", [auth_module.get_current_user, auth_module.get_optional_user])
@pytest.mark.parametrize("member_role", ["developer", None])
async def test_get_current_user_uses_membership_role_not_token_claim(monkeypatch, authenticate, member_role):
    async def fake_verify_token(_token: str, _jwks_client=None):
        return {"sub": "auth0|member", "org_id": "00000000-0000-0000-0000-000000000001", "role": "owner"}

    class DummyUserService:
        def __init__(self, _db):
            pass

        async def get_or_create_from_token(self, _payload):
            return type("User", (), {"is_active": True})()

    class DummyOrganizations:
        def __init__(self, _db):
            pass

        async def get_member_role(self, _org_id, _user_id):
            assert str(_org_id) == "00000000-0000-0000-0000-000000000001"
            assert _user_id == auth_module.auth_subject_to_user_id("auth0|member")
            return member_role

    monkeypatch.setattr(auth_module, "verify_token", fake_verify_token)
    monkeypatch.setattr(auth_module, "UserService", DummyUserService)
    monkeypatch.setattr(
        "app.services.organizations.OrganizationService.get_member_role",
        DummyOrganizations.get_member_role,
    )

    result = await authenticate(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid"),
        _jwks_client=None,
        db=None,
    )

    assert result.role == (member_role or "viewer")
    assert result.org_id == ("00000000-0000-0000-0000-000000000001" if member_role else None)


@pytest.mark.asyncio
async def test_get_current_user_requires_credentials():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=None, _jwks_client=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token_instead_of_fabricating_user(monkeypatch):
    async def fake_verify_token(_token: str, _jwks_client=None):
        raise auth_module.AuthenticationError("Invalid token")

    monkeypatch.setattr(auth_module, "verify_token", fake_verify_token)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid")

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=credentials, _jwks_client=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_passes_jwks_client_to_verifier(monkeypatch):
    captured = {}

    async def fake_verify_token(_token: str, jwks_client=None):
        captured["jwks_client"] = jwks_client
        return {"sub": "auth0|user-123"}

    class DummyUserService:
        def __init__(self, _db):
            pass

        async def get_or_create_from_token(self, _payload):
            return None

    monkeypatch.setattr(auth_module, "verify_token", fake_verify_token)
    monkeypatch.setattr(auth_module, "UserService", DummyUserService)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid")
    jwks_client = object()

    user = await get_current_user(
        credentials=credentials,
        _jwks_client=jwks_client,
        db=None,
    )

    assert user.sub == "auth0|user-123"
    assert captured["jwks_client"] is jwks_client
