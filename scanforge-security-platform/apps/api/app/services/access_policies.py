from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, OrganizationMember, Project, Repository


async def get_repository_for_user(
    db: AsyncSession,
    repo_id: UUID,
    user_id: UUID,
) -> Repository | None:
    result = await db.execute(
        select(Repository)
        .join(Project, Repository.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Repository.id == repo_id,
            OrganizationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_project_in_org_for_user(
    db: AsyncSession,
    *,
    project_id: UUID,
    org_id: UUID,
    user_id: UUID,
) -> Project | None:
    result = await db.execute(
        select(Project)
        .join(Organization, Project.organization_id == Organization.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Project.id == project_id,
            Project.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_repository_in_project_for_user(
    db: AsyncSession,
    *,
    repo_id: UUID,
    project_id: UUID,
    user_id: UUID,
) -> Repository | None:
    result = await db.execute(
        select(Repository)
        .join(Project, Repository.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(
            Repository.id == repo_id,
            Repository.project_id == project_id,
            OrganizationMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()
