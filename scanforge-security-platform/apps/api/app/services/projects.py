from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Finding, Organization, OrganizationMember, Project, Repository, Scan
from app.schemas.projects import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        org_id: UUID,
        data: ProjectCreate,
        user_id: UUID,
    ) -> Project:
        project = Project(
            organization_id=org_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            default_branch=data.default_branch,
            created_by_user_id=user_id,
            is_active=True,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_by_id(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> Project | None:
        result = await self.db.execute(
            select(Project)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Project.id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_slug(
        self,
        org_id: UUID,
        slug: str,
    ) -> Project | None:
        result = await self.db.execute(
            select(Project).where(
                Project.organization_id == org_id,
                Project.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_org(
        self,
        org_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[Project], int]:
        base_query = (
            select(Project)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Project.organization_id == org_id,
                OrganizationMember.user_id == user_id,
            )
        )

        if is_active is not None:
            base_query = base_query.where(Project.is_active == is_active)

        count_result = await self.db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
        total = count_result.scalar_one()

        result = await self.db.execute(base_query.order_by(Project.created_at.desc()).offset(skip).limit(limit))
        projects = list(result.scalars().all())

        return projects, total

    async def update(
        self,
        project_id: UUID,
        data: ProjectUpdate,
        user_id: UUID | None = None,
    ) -> Project | None:
        if user_id is not None:
            project = await self.get_by_id(project_id, user_id)
        else:
            project = await self.db.get(Project, project_id)
        if not project:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)

        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def delete(self, project_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is not None:
            project = await self.get_by_id(project_id, user_id)
        else:
            project = await self.db.get(Project, project_id)
        if not project:
            return False

        project.is_active = False
        await self.db.commit()
        return True

    async def get_project_stats(
        self,
        project_id: UUID,
    ) -> dict:
        repo_count = (
            await self.db.scalar(select(func.count(Repository.id)).where(Repository.project_id == project_id)) or 0
        )

        scan_count = await self.db.scalar(select(func.count(Scan.id)).where(Scan.project_id == project_id)) or 0

        open_findings = (
            await self.db.scalar(
                select(func.count(Finding.id)).where(
                    Finding.project_id == project_id,
                    Finding.status == "open",
                )
            )
            or 0
        )

        critical_findings = (
            await self.db.scalar(
                select(func.count(Finding.id)).where(
                    Finding.project_id == project_id,
                    Finding.status == "open",
                    Finding.severity == "critical",
                )
            )
            or 0
        )

        return {
            "repo_count": repo_count,
            "scan_count": scan_count,
            "open_findings_count": open_findings,
            "critical_findings_count": critical_findings,
        }

    async def user_has_access(
        self,
        project_id: UUID,
        user_id: UUID,
    ) -> bool:
        result = await self.db.execute(
            select(Project)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Project.id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None
