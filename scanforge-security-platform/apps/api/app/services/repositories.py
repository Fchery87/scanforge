from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, OrganizationMember, Project, Repository, RepositoryIntegration
from app.schemas.repositories import RepositoryConnect, RepositoryUpdate


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def connect(
        self,
        project_id: UUID,
        data: RepositoryConnect,
        _user_id: UUID,
    ) -> Repository:
        repo = Repository(
            project_id=project_id,
            provider=data.provider,
            external_repo_id=data.external_repo_id,
            owner_name=data.owner_name,
            repo_name=data.repo_name,
            full_name=data.full_name,
            default_branch=data.default_branch,
            clone_url=data.clone_url,
            html_url=data.html_url,
            is_active=True,
        )
        self.db.add(repo)
        await self.db.flush()

        if data.provider == "github" and data.installation_id:
            integration = RepositoryIntegration(
                repository_id=repo.id,
                installation_id=data.installation_id,
                provider_account_id=data.provider_account_id,
            )
            self.db.add(integration)

        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def get_by_id(
        self,
        repo_id: UUID,
        user_id: UUID,
    ) -> Repository | None:
        result = await self.db.execute(
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

    async def get_by_provider_and_full_name(
        self,
        provider: str,
        full_name: str,
    ) -> Repository | None:
        result = await self.db.execute(
            select(Repository).where(
                Repository.provider == provider,
                Repository.full_name == full_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_project(
        self,
        project_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        is_active: bool | None = None,
    ) -> tuple[list[Repository], int]:
        base_query = (
            select(Repository)
            .join(Project, Repository.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(
                Repository.project_id == project_id,
                OrganizationMember.user_id == user_id,
            )
        )

        if is_active is not None:
            base_query = base_query.where(Repository.is_active == is_active)

        count_result = await self.db.execute(
            select(func.count(Repository.id))
            .where(Repository.project_id == project_id)
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            base_query
            .order_by(Repository.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        repos = list(result.scalars().all())

        return repos, total

    async def update(
        self,
        repo_id: UUID,
        data: RepositoryUpdate,
    ) -> Repository | None:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(repo, field, value)

        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def disconnect(self, repo_id: UUID) -> bool:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            return False

        repo.is_active = False
        await self.db.commit()
        return True

    async def get_integration(
        self,
        repo_id: UUID,
    ) -> RepositoryIntegration | None:
        result = await self.db.execute(
            select(RepositoryIntegration).where(
                RepositoryIntegration.repository_id == repo_id
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, repo_id: UUID) -> bool:
        repo = await self.db.get(Repository, repo_id)
        if not repo:
            return False

        await self.db.delete(repo)
        await self.db.commit()
        return True
