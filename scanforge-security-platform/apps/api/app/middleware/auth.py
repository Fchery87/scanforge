from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import auth_subject_to_user_id
from app.core.security import AuthenticationError, JWKSClient, get_jwks_client, verify_token
from app.db.session import get_db
from app.services.organizations import OrganizationService
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


def _record_audit_context(request: Request | None, context: UserContext) -> UserContext:
    if request is not None and hasattr(request, "state"):
        request.state.audit_user_id = str(context.user_id)
        request.state.audit_org_id = context.org_id
    return context


async def get_current_user(
    request: Request = None,  # type: ignore[assignment]
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
        user = await UserService(db).get_or_create_from_token(payload)
        if not getattr(user, "is_active", True):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        context = UserContext(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            org_id=payload.get("org_id"),
        )
        if context.org_id:
            try:
                org_id = UUID(context.org_id)
            except ValueError:
                context.org_id = None
            else:
                context.role = await OrganizationService(db).get_member_role(
                    org_id, context.user_id
                ) or "viewer"
        return _record_audit_context(request, context)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    request: Request = None,  # type: ignore[assignment]
    credentials: HTTPAuthorizationCredentials = Depends(security),
    _jwks_client: JWKSClient = Depends(get_jwks_client),
    db: AsyncSession = Depends(get_db),
) -> UserContext | None:
    if credentials is None:
        return None

    try:
        return await get_current_user(
            request=request, credentials=credentials, _jwks_client=_jwks_client, db=db
        )
    except HTTPException as exc:
        if exc.status_code not in (401, 403):
            raise
        return None
