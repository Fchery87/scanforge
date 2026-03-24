from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.exports import ExportCreate, ExportResponse
from app.services.exports import ExportService
from app.services.projects import ProjectService

router = APIRouter()


@router.post("/", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
async def create_export(
    project_id: UUID,
    data: ExportCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = ExportService(db)
    try:
        export = await service.create(project_id, data, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return export


@router.get("/", response_model=PaginatedResponse[ExportResponse])
async def list_exports(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = ExportService(db)
    exports, total = await service.list_for_project(
        project_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )

    return PaginatedResponse(
        items=exports,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    project_id: UUID,
    export_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = ExportService(db)
    export = await service.get_by_id(export_id, current_user.user_id)
    if not export or export.project_id != str(project_id):
        raise HTTPException(status_code=404, detail="Export not found")

    return export


@router.get("/{export_id}/download")
async def download_export(
    project_id: UUID,
    export_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExportService(db)
    export = await service.get_by_id(export_id, current_user.user_id)
    if not export or export.project_id != str(project_id):
        raise HTTPException(status_code=404, detail="Export not found")

    if export.status != "completed" or not export.storage_uri:
        raise HTTPException(status_code=400, detail="Export not ready for download")

    return RedirectResponse(url=export.storage_uri)
