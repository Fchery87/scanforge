from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.repositories import (
    RepositoryConnect,
    RepositoryResponse,
    RepositoryUpdate,
    RepositoryWithIntegration,
)
from app.services.organizations import OrganizationService
from app.services.repositories import RepositoryService

router = APIRouter()


@router.post("/", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def connect_repository(
    org_id: UUID,
    project_id: UUID,
    data: RepositoryConnect,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["owner", "admin"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can connect repositories",
        )

    service = RepositoryService(db)

    existing = await service.get_by_provider_and_full_name(data.provider, data.full_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected",
        )

    return await service.connect(project_id, data, current_user.user_id)


@router.get("/", response_model=PaginatedResponse[RepositoryResponse])
async def list_repositories(
    org_id: UUID,
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    is_active: bool | None = None,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    service = RepositoryService(db)
    repos, total = await service.list_for_project(
        project_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        is_active=is_active,
    )

    return PaginatedResponse(
        items=repos,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{repo_id}", response_model=RepositoryWithIntegration)
async def get_repository(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    service = RepositoryService(db)
    repo = await service.get_by_id(repo_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    integration = await service.get_integration(repo_id)

    return RepositoryWithIntegration(
        **repo.__dict__,
        has_github_app=integration is not None,
        installation_id=integration.installation_id if integration else None,
    )


@router.patch("/{repo_id}", response_model=RepositoryResponse)
async def update_repository(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    data: RepositoryUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["owner", "admin"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can update repositories",
        )

    service = RepositoryService(db)
    repo = await service.get_by_id(repo_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    return await service.update(repo_id, data, user_id=current_user.user_id)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_repository(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["owner", "admin"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can disconnect repositories",
        )

    service = RepositoryService(db)
    repo = await service.get_by_id(repo_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found")

    await service.disconnect(repo_id, user_id=current_user.user_id)
