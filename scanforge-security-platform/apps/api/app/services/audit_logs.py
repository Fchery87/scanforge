from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    Finding,
    OrganizationMember,
    Project,
    Repository,
    Scan,
    User,
)


class AuditLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def record(
        self,
        actor_user_id: UUID | str | None,
        action: str,
        target_type: str,
        target_id: UUID | str | None = None,
        *,
        organization_id: UUID | str | None = None,
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
        return log

    async def create(
        self,
        actor_user_id: UUID | str | None,
        action: str,
        target_type: str,
        target_id: UUID | str | None = None,
        *,
        organization_id: UUID | str | None = None,
        metadata_json: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = True,
    ) -> AuditLog:
        log = self.record(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            organization_id=organization_id,
            metadata_json=metadata_json,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if commit:
            await self.db.commit()
            await self.db.refresh(log)
        else:
            await self.db.flush()
        return log

    async def list_for_organization(
        self,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 50,
        *,
        action: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        is_member = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(org_id),
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
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
        *,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        project = await self.db.get(Project, str(project_id))
        if not project:
            return [], 0

        is_member = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == project.organization_id,
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
            )
        )
        if not is_member.scalar_one_or_none():
            return [], 0

        pid = str(project_id)
        repo_ids = select(Repository.id).where(Repository.project_id == pid)
        scan_ids = select(Scan.id).where(Scan.project_id == pid)
        finding_ids = select(Finding.id).where(Finding.project_id == pid)

        base_query = select(AuditLog).where(
            AuditLog.organization_id == project.organization_id,
            or_(
                and_(AuditLog.target_type == "project", AuditLog.target_id == pid),
                and_(AuditLog.target_type == "repository", AuditLog.target_id.in_(repo_ids)),
                and_(AuditLog.target_type == "scan", AuditLog.target_id.in_(scan_ids)),
                and_(AuditLog.target_type == "finding", AuditLog.target_id.in_(finding_ids)),
                AuditLog.target_id == pid,
            ),
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

