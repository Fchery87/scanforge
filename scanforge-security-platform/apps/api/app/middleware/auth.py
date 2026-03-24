from uuid import UUID, uuid5

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import AuthenticationError, JWKSClient, get_jwks_client, verify_token

security = HTTPBearer(auto_error=False)


class UserContext(BaseModel):
    sub: str
    email: str | None = None
    name: str | None = None
    role: str | None = "viewer"
    org_id: str | None = None
    _user_id: UUID | None = None

    @property
    def user_id(self) -> UUID:
        if self._user_id is not None:
            return self._user_id
        try:
            user_uuid = UUID(self.sub)
        except ValueError:
            namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
            user_uuid = uuid5(namespace, self.sub)
        self._user_id = user_uuid
        return user_uuid


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _jwks_client: JWKSClient = Depends(get_jwks_client),
) -> UserContext:
    # In development mode, allow bypass with mock user if no credentials provided
    if credentials is None:
        if settings.APP_ENV != "production":
            return UserContext(
                sub="dev-user-00000000-0000-0000-0000-000000000000",
                email="dev@localhost",
                name="Dev User",
                role="admin",
                org_id=None,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await verify_token(credentials.credentials)

        return UserContext(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            role=payload.get("role", "viewer"),
            org_id=payload.get("org_id"),
        )
    except AuthenticationError as e:
        # In development mode, fallback to mock user on auth errors
        if settings.APP_ENV != "production":
            return UserContext(
                sub="dev-user-00000000-0000-0000-0000-000000000000",
                email="dev@localhost",
                name="Dev User",
                role="admin",
                org_id=None,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserContext | None:
    if credentials is None:
        return None

    try:
        payload = await verify_token(credentials.credentials)
        return UserContext(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            role=payload.get("role", "viewer"),
            org_id=payload.get("org_id"),
        )
    except AuthenticationError:
        return None
