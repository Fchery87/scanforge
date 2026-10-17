from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, OrganizationMember, Project, Repository, User

READ_ROLES: list[str] = ["owner", "admin", "security_reviewer", "developer", "viewer"]
SCAN_EXECUTION_ROLES: list[str] = ["owner", "admin", "security_reviewer", "developer"]
FINDING_MUTATION_ROLES: list[str] = ["owner", "admin", "security_reviewer"]
ORG_ADMIN_ROLES: list[str] = ["owner", "admin"]
OWNER_ONLY_ROLES: list[str] = ["owner"]


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
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            Repository.id == str(repo_id),
            OrganizationMember.user_id == str(user_id),
            User.is_active.is_(True),
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
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            Project.id == str(project_id),
            Project.organization_id == str(org_id),
            OrganizationMember.user_id == str(user_id),
            User.is_active.is_(True),
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
        .join(User, User.id == OrganizationMember.user_id)
        .where(
            Repository.id == str(repo_id),
            Repository.project_id == str(project_id),
            OrganizationMember.user_id == str(user_id),
            User.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
