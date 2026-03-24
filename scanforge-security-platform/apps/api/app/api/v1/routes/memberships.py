from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.memberships import MemberInvite, MemberUpdateRole
from app.services.memberships import MembershipService
from app.services.organizations import OrganizationService

router = APIRouter()


class MemberResponse(BaseModel):
    id: UUID
    organization_id: UUID
    user_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime
    user_email: str | None = None
    user_name: str | None = None


@router.get("/{org_id}/members", response_model=PaginatedResponse[MemberResponse])
async def list_members(
    org_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer", "developer", "viewer"]
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    service = MembershipService(db)
    members, total = await service.list_members(
        org_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )

    member_responses = []
    for m in members:
        member_responses.append(MemberResponse(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at,
            updated_at=m.updated_at,
            user_email=m.user.email if m.user else None,
            user_name=m.user.name if m.user else None,
        ))

    return PaginatedResponse(
        items=member_responses,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/{org_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: UUID,
    data: MemberInvite,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can invite members",
        )

    service = MembershipService(db)
    member = await service.invite_by_email(org_id, current_user.user_id, data)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found. They must sign in first.",
        )

    return {"message": "Member added successfully", "member_id": str(member.id)}


@router.patch("/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    data: MemberUpdateRole,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update member roles",
        )

    service = MembershipService(db)
    try:
        member = await service.update_role(org_id, user_id, data.role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    return {"message": "Role updated successfully"}


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can remove members",
        )

    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove yourself. Ask another owner to do this.",
        )

    service = MembershipService(db)
    try:
        removed = await service.remove_member(org_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
