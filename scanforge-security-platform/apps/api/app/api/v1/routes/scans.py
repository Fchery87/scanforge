from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.scans import (
    ScanCancel,
    ScanCreate,
    ScanDetailResponse,
    ScanResponse,
)
from app.services.projects import ProjectService
from app.services.repositories import RepositoryService
from app.services.scans import ScanService

router = APIRouter()


@router.post("/", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    project_id: UUID,
    data: ScanCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    repo_service = RepositoryService(db)
    repo = await repo_service.get_by_id(data.repository_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(status_code=404, detail="Repository not found in this project")

    scan_service = ScanService(db)
    try:
        scan, _, _ = await scan_service.create(
            data.repository_id, data, current_user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return scan


@router.get("/", response_model=PaginatedResponse[ScanResponse])
async def list_scans(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    scan_service = ScanService(db)
    scans, total = await scan_service.list_for_project(
        project_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        status_filter=status_filter,
    )

    return PaginatedResponse(
        items=scans,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/{scan_id}", response_model=ScanDetailResponse)
async def get_scan(
    project_id: UUID,
    scan_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    runs = await scan_service.get_scanner_runs(scan_id)

    return ScanDetailResponse(
        **scan.__dict__,
        scanner_runs=runs,
    )


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan(
    project_id: UUID,
    scan_id: UUID,
    data: ScanCancel,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        canceled = await scan_service.cancel(scan_id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return canceled
