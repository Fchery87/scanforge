from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import OrganizationMember, User
from app.schemas.memberships import MemberInvite


class MembershipService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_member(
        self,
        org_id: UUID,
        user_id: UUID,
        role: str,
    ) -> OrganizationMember:
        existing = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("User is already a member")

        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def remove_member(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> bool:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return False

        if member.role == "owner":
            raise ValueError("Cannot remove the owner")

        await self.db.delete(member)
        await self.db.commit()
        return True

    async def update_role(
        self,
        org_id: UUID,
        user_id: UUID,
        new_role: str,
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None

        if member.role == "owner" and new_role != "owner":
            raise ValueError("Cannot change owner role")

        member.role = new_role
        await self.db.commit()
        await self.db.refresh(member)
        return member

    async def get_member(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_members(
        self,
        org_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[OrganizationMember], int]:
        count_result = await self.db.execute(
            select(func.count(OrganizationMember.id))
            .where(OrganizationMember.organization_id == org_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user))
            .where(OrganizationMember.organization_id == org_id)
            .order_by(OrganizationMember.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        members = list(result.scalars().all())

        return members, total

    async def invite_by_email(
        self,
        org_id: UUID,
        _inviter_user_id: UUID,
        data: MemberInvite,
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(User).where(User.email == data.email)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return await self.add_member(org_id, user.id, data.role)
