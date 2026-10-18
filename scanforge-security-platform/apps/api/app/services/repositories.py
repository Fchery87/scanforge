from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Organization,
    OrganizationIntegration,
    OrganizationMember,
    Project,
    Repository,
    RepositoryBranchGeneration,
    RepositoryIntegration,
)
from app.schemas.repositories import RepositoryConnect, RepositoryUpdate
from app.services.access_policies import get_repository_for_user
from app.services.github import GitHubInstallationAccessError
from app.services.repository_refs import RepositoryRefService, normalize_branch_and_full_ref


class RepositoryAuthorizationError(PermissionError):
    """Raised when a repository connection lacks verified installation or tenant authority."""

    code = "repository_authorization_denied"


class RepositoryConflictError(ValueError):
    """Raised when a repository is already bound to a project."""

    code = "repository_already_connected"


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_provider_and_external_id(
        self,
        provider: str,
        external_repo_id: str,
    ) -> Repository | None:
        result = await self.db.execute(
            select(Repository).where(
                Repository.provider == provider,
                Repository.external_repo_id == str(external_repo_id),
            )
        )
        return result.scalar_one_or_none()

    async def connect(  # noqa: PLR0912, PLR0915
        self,
        project_id: UUID,
        data: RepositoryConnect,
        _user_id: UUID,
        *,
        provider_verifier: Any | None = None,
        verify_provider_access: bool = False,
    ) -> Repository:
        project = await self.db.get(Project, project_id)
        if not project:
            raise ValueError("Project not found")

        org_integration_result = await self.db.execute(
            select(OrganizationIntegration).where(
                OrganizationIntegration.organization_id == project.organization_id
            )
        )
        org_integration = org_integration_result.scalar_one_or_none()

        effective_installation_id = data.installation_id
        effective_account_id = data.provider_account_id
        external_repo_id = data.external_repo_id
        owner_name = data.owner_name
        repo_name = data.repo_name
        full_name = data.full_name
        default_branch = data.default_branch
        clone_url = data.clone_url
        html_url = data.html_url

        if data.provider == "github":
            if data.installation_id:
                foreign_result = await self.db.execute(
                    select(OrganizationIntegration).where(
                        OrganizationIntegration.installation_id == str(data.installation_id)
                    )
                )
                for bound in foreign_result.scalars().all():
                    if str(bound.organization_id) != str(project.organization_id):
                        raise RepositoryAuthorizationError(
                            "GitHub installation is bound to another organization"
                        )

            if org_integration is not None:
                if (
                    data.installation_id
                    and str(data.installation_id) != str(org_integration.installation_id)
                ):
                    raise RepositoryAuthorizationError(
                        "Requested GitHub installation does not match the organization's verified integration"
                    )
                effective_installation_id = str(org_integration.installation_id)
                effective_account_id = effective_account_id or org_integration.account_login
            elif verify_provider_access or provider_verifier is not None or data.installation_id:
                raise RepositoryAuthorizationError(
                    "Organization must have a verified GitHub integration before connecting repositories"
                )

            if provider_verifier is not None:
                if not effective_installation_id:
                    raise RepositoryAuthorizationError(
                        "Verified GitHub installation is required to connect a repository"
                    )
                try:
                    verified_meta = await provider_verifier.get_installation_repository(
                        effective_installation_id,
                        external_repo_id=external_repo_id,
                        owner_name=owner_name,
                        repo_name=repo_name,
                        full_name=full_name,
                    )
                except GitHubInstallationAccessError as exc:
                    raise RepositoryAuthorizationError(str(exc)) from exc
                external_repo_id = str(verified_meta["external_repo_id"])
                owner_name = verified_meta["owner_name"]
                repo_name = verified_meta["repo_name"]
                full_name = verified_meta["full_name"]
                default_branch = verified_meta.get("default_branch") or default_branch
                clone_url = verified_meta.get("clone_url") or clone_url
                html_url = verified_meta.get("html_url") or html_url

        # Check immutable provider ID and full_name uniqueness only AFTER authority is verified
        if external_repo_id:
            existing_by_ext = await self.get_by_provider_and_external_id(
                data.provider,
                external_repo_id,
            )
            if existing_by_ext is not None:
                raise RepositoryConflictError("Repository already connected")

        existing_by_name = await self.get_by_provider_and_full_name(data.provider, full_name)
        if existing_by_name is not None:
            raise RepositoryConflictError("Repository already connected")

        repo = Repository(
            project_id=project_id,
            provider=data.provider,
            external_repo_id=str(external_repo_id) if external_repo_id else None,
            owner_name=owner_name,
            repo_name=repo_name,
            full_name=full_name,
            default_branch=default_branch,
            clone_url=clone_url or (f"https://github.com/{full_name}.git" if data.provider == "github" else None),
            html_url=html_url or (f"https://github.com/{full_name}" if data.provider == "github" else None),
            is_active=True,
            lifecycle_state="connected",
        )
        self.db.add(repo)
        await self.db.flush()

        if data.provider == "github" and effective_installation_id:
            integration = RepositoryIntegration(
                repository_id=repo.id,
                installation_id=str(effective_installation_id),
                provider_account_id=effective_account_id,
                access_metadata={"verified": True},
            )
            self.db.add(integration)

        if default_branch:
            branch_name, full_ref_name = normalize_branch_and_full_ref(default_branch)
            ref_service = RepositoryRefService(self.db)
            active_gen = await ref_service.get_active_generation(repo.id, full_ref_name)
            if active_gen is None:
                self.db.add(
                    RepositoryBranchGeneration(
                        repository_id=repo.id,
                        full_ref_name=full_ref_name,
                        branch_name=branch_name,
                        generation_number=1,
                        head_commit_sha=None,
                        ancestry_status="verified_initial",
                    )
                )

        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def reconcile_rename_or_transfer(
        self,
        *,
        external_repo_id: str,
        new_owner_name: str,
        new_repo_name: str,
        new_full_name: str | None = None,
        installation_id: str | None = None,
        default_branch: str | None = None,
        installation_accessible: bool = True,
    ) -> Repository | None:
        """Reconcile a GitHub repository rename or transfer by immutable `external_repo_id`.

        - Rename within the same verified installation/owner updates mutable names in place
          and preserves repository ID, project binding, and scan/finding history.
        - Transfer across owners or to an unverified/foreign installation marks the repository
          inactive (`lifecycle_state = "reauthorization_required"`), revokes execution authority,
          and never transfers history across organizations.
        """
        repo = await self.get_by_provider_and_external_id("github", external_repo_id)
        if repo is None:
            return None

        project = await self.db.get(Project, repo.project_id)
        org_integration = None
        if project is not None:
            res = await self.db.execute(
                select(OrganizationIntegration).where(
                    OrganizationIntegration.organization_id == project.organization_id
                )
            )
            org_integration = res.scalar_one_or_none()

        repo_integration = await self.get_integration(UUID(str(repo.id)))
        computed_full_name = new_full_name or f"{new_owner_name}/{new_repo_name}"

        same_installation = (
            org_integration is not None
            and (
                installation_id is None
                or str(installation_id) == str(org_integration.installation_id)
            )
            and (
                repo_integration is None
                or repo_integration.installation_id is None
                or str(repo_integration.installation_id) == str(org_integration.installation_id)
            )
        )
        same_owner = new_owner_name.lower() == repo.owner_name.lower() or (
            org_integration is not None
            and org_integration.account_login is not None
            and new_owner_name.lower() == org_integration.account_login.lower()
        )

        if installation_accessible and same_installation and same_owner:
            repo.owner_name = new_owner_name
            repo.repo_name = new_repo_name
            repo.full_name = computed_full_name
            repo.clone_url = f"https://github.com/{computed_full_name}.git"
            repo.html_url = f"https://github.com/{computed_full_name}"
            if default_branch:
                repo.default_branch = default_branch
            repo.is_active = True
            repo.lifecycle_state = "connected"
        else:
            repo.is_active = False
            repo.lifecycle_state = "reauthorization_required"
            if repo_integration is not None:
                meta = dict(repo_integration.access_metadata or {})
                meta.update(
                    {
                        "reauthorization_required": True,
                        "observed_owner_name": new_owner_name,
                        "observed_repo_name": new_repo_name,
                        "observed_full_name": computed_full_name,
                        "observed_installation_id": installation_id,
                    }
                )
                repo_integration.access_metadata = meta

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

        count_result = await self.db.execute(select(func.count()).select_from(base_query.order_by(None).subquery()))
        total = count_result.scalar_one()

        result = await self.db.execute(base_query.order_by(Repository.created_at.desc()).offset(skip).limit(limit))
        repos = list(result.scalars().all())

        return repos, total

    async def update(
        self,
        repo_id: UUID,
        data: RepositoryUpdate,
        user_id: UUID | None = None,
    ) -> Repository | None:
        if user_id is not None:
            repo = await get_repository_for_user(self.db, repo_id, user_id)
        else:
            repo = await self.db.get(Repository, repo_id)
        if not repo:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(repo, field, value)

        await self.db.commit()
        await self.db.refresh(repo)
        return repo

    async def disconnect(self, repo_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is not None:
            repo = await get_repository_for_user(self.db, repo_id, user_id)
        else:
            repo = await self.db.get(Repository, repo_id)
        if not repo:
            return False

        repo.is_active = False
        repo.lifecycle_state = "disconnected"
        await self.db.commit()
        return True

    async def get_integration(
        self,
        repo_id: UUID,
    ) -> RepositoryIntegration | None:
        result = await self.db.execute(
            select(RepositoryIntegration).where(RepositoryIntegration.repository_id == repo_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, repo_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is not None:
            repo = await get_repository_for_user(self.db, repo_id, user_id)
        else:
            repo = await self.db.get(Repository, repo_id)
        if not repo:
            return False

        await self.db.delete(repo)
        await self.db.commit()
        return True
