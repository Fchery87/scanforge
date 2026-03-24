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
