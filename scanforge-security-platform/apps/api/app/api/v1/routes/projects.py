from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.repository import Repository
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.projects import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    ProjectWithStats,
)
from app.services.organizations import OrganizationService
from app.services.projects import ProjectService

router = APIRouter()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        data.organization_id, current_user.user_id, ["owner", "admin"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners and admins can create projects",
        )

    service = ProjectService(db)
    existing = await service.get_by_org_and_slug(data.organization_id, data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project with this slug already exists in the organization",
        )

    return await service.create(data.organization_id, data, current_user.user_id)


@router.get("/", response_model=PaginatedResponse[ProjectWithStats])
async def list_projects(
    org_id: UUID,
    pagination: PaginationParams = Depends(),
    is_active: bool | None = None,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer", "developer", "viewer"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    service = ProjectService(db)
    projects, total = await service.list_for_org(
        org_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        is_active=is_active,
    )

    enriched = []
    for project in projects:
        repo_count = (
            await db.execute(
                select(func.count())
                .select_from(Repository)
                .where(Repository.project_id == project.id)
            )
        ).scalar_one_or_none() or 0
        open_count = (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(Finding.project_id == project.id, Finding.status == "open")
            )
        ).scalar_one_or_none() or 0
        proj_dict = {
            **ProjectResponse.model_validate(project).model_dump(),
            "repo_count": repo_count,
            "open_findings_count": open_count,
        }
        enriched.append(proj_dict)

    return PaginatedResponse(
        items=enriched,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{project_id}", response_model=ProjectWithStats)
async def get_project(
    project_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get_by_id(project_id, current_user.user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stats = await service.get_project_stats(project_id)

    return ProjectWithStats(
        **project.__dict__,
        repo_count=stats["repo_count"],
        scan_count=stats["scan_count"],
        open_findings_count=stats["open_findings_count"],
        critical_findings_count=stats["critical_findings_count"],
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    data: ProjectUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get_by_id(project_id, current_user.user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.slug:
        existing = await service.get_by_org_and_slug(project.organization_id, data.slug)
        if existing and existing.id != project_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Project with this slug already exists",
            )

    return await service.update(project_id, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    project = await service.get_by_id(project_id, current_user.user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    await service.delete(project_id)
