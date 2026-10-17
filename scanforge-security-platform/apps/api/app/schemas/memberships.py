from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

MEMBER_ROLES = ["owner", "admin", "security_reviewer", "developer", "viewer"]


class MemberInvite(BaseModel):
    email: EmailStr
    role: str = Field(..., pattern="^(admin|security_reviewer|developer|viewer)$")


class MemberUpdateRole(BaseModel):
    role: str = Field(..., pattern="^(admin|security_reviewer|developer|viewer)$")


class MemberRemove(BaseModel):
    user_id: UUID


class InvitationAccept(BaseModel):
    token: str = Field(..., min_length=16)


class OwnershipTransferRequest(BaseModel):
    new_owner_user_id: UUID


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

