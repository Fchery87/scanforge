from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import auth_subject_to_user_id
from app.core.security import AuthenticationError, JWKSClient, get_jwks_client, verify_token
from app.db.session import get_db
from app.services.users import UserService

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
        self._user_id = auth_subject_to_user_id(self.sub)
        return self._user_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _jwks_client: JWKSClient = Depends(get_jwks_client),
    db: AsyncSession = Depends(get_db),
) -> UserContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = await verify_token(credentials.credentials, _jwks_client)
        await UserService(db).get_or_create_from_token(payload)

        return UserContext(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            org_id=payload.get("org_id"),
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _jwks_client: JWKSClient = Depends(get_jwks_client),
) -> UserContext | None:
    if credentials is None:
        return None

    try:
        payload = await verify_token(credentials.credentials, _jwks_client)
        return UserContext(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            org_id=payload.get("org_id"),
        )
    except AuthenticationError:
        return None
