from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    OrganizationMember,
    Project,
)


class AuditLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        actor_user_id: UUID | None,
        action: str,
        target_type: str,
        target_id: UUID | None = None,
        organization_id: UUID | None = None,
        metadata_json: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            organization_id=str(organization_id) if organization_id else None,
            actor_user_id=str(actor_user_id) if actor_user_id else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id else None,
            metadata_json=metadata_json,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def list_for_organization(
        self,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        is_member = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
            )
        )
        if not is_member.scalar_one_or_none():
            return [], 0

        base_query = select(AuditLog).where(AuditLog.organization_id == str(org_id))

        if action:
            base_query = base_query.where(AuditLog.action == action)
        if actor_user_id:
            base_query = base_query.where(AuditLog.actor_user_id == str(actor_user_id))

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )

        return list(result.scalars().all()), total

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        project = await self.db.get(Project, str(project_id))
        if not project:
            return [], 0

        is_member = await self.db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == str(user_id),
            )
        )
        if not is_member.scalar_one_or_none():
            return [], 0

        base_query = select(AuditLog).where(
            AuditLog.organization_id == project.organization_id
        )

        if action:
            base_query = base_query.where(AuditLog.action == action)

        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )

        return list(result.scalars().all()), total
