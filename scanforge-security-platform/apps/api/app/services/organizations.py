from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MemberRole
from app.db.models import Organization, OrganizationMember, User
from app.schemas.organizations import OrganizationCreate, OrganizationUpdate
from app.services.audit_logs import AuditLogService


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_available_slug(self, slug: str) -> str:
        existing = await self.get_by_slug(slug)
        if not existing:
            return slug

        suffix = 2
        while True:
            candidate = f"{slug}-{suffix}"
            existing = await self.get_by_slug(candidate)
            if not existing:
                return candidate
            suffix += 1

    async def create(
        self,
        data: OrganizationCreate,
        user_id: UUID,
    ) -> tuple[Organization, OrganizationMember]:
        user_result = await self.db.execute(
            select(User).where(User.id == str(user_id), User.is_active.is_(True))
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("Authenticated user record not found")

        org = Organization(
            name=data.name,
            slug=await self.get_available_slug(data.slug),
            created_by_user_id=str(user_id),
        )
        self.db.add(org)
        await self.db.flush()

        member = OrganizationMember(
            organization_id=str(org.id),
            user_id=str(user_id),
            role=MemberRole.OWNER.value,
        )
        self.db.add(member)
        AuditLogService(self.db).record(
            actor_user_id=user_id,
            action="organization_created",
            target_type="organization",
            target_id=org.id,
            organization_id=org.id,
            metadata_json={"slug": org.slug, "name": org.name},
        )
        await self.db.commit()
        await self.db.refresh(org)
        return org, member

    async def get_by_id(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> Organization | None:
        if not await self.is_member(org_id, user_id):
            return None

        result = await self.db.execute(select(Organization).where(Organization.id == str(org_id)))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(select(Organization).where(Organization.slug == slug))
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
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.user_id == str(user_id), User.is_active.is_(True))
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .join(User, User.id == OrganizationMember.user_id)
            .where(OrganizationMember.user_id == str(user_id), User.is_active.is_(True))
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
        user_id: UUID | None = None,
    ) -> Organization | None:
        if user_id is not None:
            if not await self.user_has_permission(org_id, user_id, ["owner", "admin"]):
                return None
            org = await self.get_by_id(org_id, user_id)
        else:
            org = await self.db.get(Organization, str(org_id))
        if not org:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)

        AuditLogService(self.db).record(
            actor_user_id=user_id,
            action="organization_updated",
            target_type="organization",
            target_id=org.id,
            organization_id=org.id,
            metadata_json={"updated_fields": sorted(update_data.keys())},
        )
        await self.db.commit()
        await self.db.refresh(org)
        return org

    async def delete(self, org_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is not None:
            if not await self.user_has_permission(org_id, user_id, ["owner"]):
                return False
            org = await self.get_by_id(org_id, user_id)
        else:
            org = await self.db.get(Organization, str(org_id))
        if not org:
            return False

        await self.db.delete(org)
        await self.db.commit()
        return True

    async def is_member(self, org_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_member_role(
        self,
        org_id: UUID,
        user_id: UUID,
    ) -> str | None:
        result = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None
        return getattr(member.role, "value", member.role)

    async def user_has_permission(
        self,
        org_id: UUID,
        user_id: UUID,
        required_roles: list[str],
    ) -> bool:
        role = await self.get_member_role(org_id, user_id)
        if not role:
            return False
        return role in set(required_roles)
