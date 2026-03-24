from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class TokenPayload(BaseModel):
    sub: str
    email: EmailStr | None = None
    name: str | None = None
    role: str = "viewer"
    org_id: str | None = None
    exp: int | None = None
    iat: int | None = None


class UserCreate(BaseModel):
    auth_provider_user_id: str
    email: EmailStr
    name: str | None = None
    avatar_url: str | None = None


class UserResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    auth_provider_user_id: str
    email: str
    name: str | None = None
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserInDB(UserResponse):
    pass
