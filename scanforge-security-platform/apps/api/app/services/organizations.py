from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import MemberRole
from app.db.models import Organization, OrganizationMember, User
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        data: OrganizationCreate,
        user_id: UUID,
    ) -> tuple[Organization, OrganizationMember]:
        # Ensure user exists (auto-create in development mode if needed)
        user_result = await self.db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user and settings.APP_ENV != "production":
            # Auto-create dev user
            user = User(
                id=user_id,
                auth_provider_user_id=str(user_id),
                email="dev@localhost",
                name="Dev User",
            )
            self.db.add(user)
            await self.db.flush()

        org = Organization(
            name=data.name,
            slug=data.slug,
            created_by_user_id=user_id,
        )
        self.db.add(org)
        await self.db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user_id,
            role=MemberRole.OWNER.value,
        )
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(org)
        return org, member

    async def get_by_id(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> Organization | None:
        membership = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        if not membership.scalar_one_or_none():
            return None

        result = await self.db.execute(
            select(Organization)
            .where(Organization.id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Organization], int]:
        count_result = await self.db.execute(
            select(func.count(Organization.id))
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.name)
            .offset(skip)
            .limit(limit)
        )
        orgs = list(result.scalars().all())

        return orgs, total

    async def update(
        self,
        org_id: UUID,
        data: OrganizationUpdate,
    ) -> Organization | None:
        org = await self.db.get(Organization, org_id)
        if not org:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)

        await self.db.commit()
        await self.db.refresh(org)
        return org

    async def delete(self, org_id: UUID) -> bool:
        org = await self.db.get(Organization, org_id)
        if not org:
            return False

        await self.db.delete(org)
        await self.db.commit()
        return True

    async def is_member(self, org_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_member_role(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> str | None:
        result = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        return member.role if member else None

    async def user_has_permission(
        self,
        org_id: UUID,
        user_id: UUID,
        required_roles: list[str],
    ) -> bool:
        role = await self.get_member_role(org_id, user_id)
        if not role:
            return False
        if role in ("owner", "admin"):
            return True
        return role in required_roles
