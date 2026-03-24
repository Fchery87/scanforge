from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.scan_schedules import (
    ScanScheduleCreate,
    ScanScheduleResponse,
    ScanScheduleUpdate,
)
from app.services.repositories import RepositoryService
from app.services.scan_schedules import ScanScheduleService

router = APIRouter()


@router.post(
    "/", response_model=ScanScheduleResponse, status_code=status.HTTP_201_CREATED
)
async def create_schedule(
    project_id: UUID,
    repo_id: UUID,
    data: ScanScheduleCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo_service = RepositoryService(db)
    repo = await repo_service.get_by_id(repo_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(
            status_code=404, detail="Repository not found in this project"
        )

    service = ScanScheduleService(db)
    try:
        schedule = await service.create(repo_id, data, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return schedule


@router.get("/", response_model=list[ScanScheduleResponse])
async def list_schedules(
    project_id: UUID,
    repo_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo_service = RepositoryService(db)
    repo = await repo_service.get_by_id(repo_id, current_user.user_id)
    if not repo or repo.project_id != project_id:
        raise HTTPException(
            status_code=404, detail="Repository not found in this project"
        )

    service = ScanScheduleService(db)
    return await service.list_for_repository(repo_id, current_user.user_id)


@router.patch("/{schedule_id}", response_model=ScanScheduleResponse)
async def update_schedule(
    project_id: UUID,
    repo_id: UUID,
    schedule_id: UUID,
    data: ScanScheduleUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanScheduleService(db)
    updated = await service.update(schedule_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    project_id: UUID,
    repo_id: UUID,
    schedule_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScanScheduleService(db)
    deleted = await service.delete(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
