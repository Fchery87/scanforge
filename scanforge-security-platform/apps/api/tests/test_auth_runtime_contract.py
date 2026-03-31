import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.middleware import auth as auth_module
from app.middleware.auth import get_current_user


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
