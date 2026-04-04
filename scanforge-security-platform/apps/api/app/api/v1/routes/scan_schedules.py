from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404, get_repository_in_project_or_404
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.scan_schedules import (
    ScanScheduleCreate,
    ScanScheduleResponse,
    ScanScheduleUpdate,
)
from app.services.scan_schedules import ScanScheduleService

router = APIRouter()


@router.post("/", response_model=ScanScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    data: ScanScheduleCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    await get_repository_in_project_or_404(db, repo_id=repo_id, project_id=project_id, user_id=current_user.user_id)

    service = ScanScheduleService(db)
    try:
        schedule = await service.create(repo_id, data, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return schedule


@router.get("/", response_model=list[ScanScheduleResponse])
async def list_schedules(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    await get_repository_in_project_or_404(db, repo_id=repo_id, project_id=project_id, user_id=current_user.user_id)

    service = ScanScheduleService(db)
    return await service.list_for_repository(repo_id, current_user.user_id)


@router.patch("/{schedule_id}", response_model=ScanScheduleResponse)
async def update_schedule(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    schedule_id: UUID,
    data: ScanScheduleUpdate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    await get_repository_in_project_or_404(db, repo_id=repo_id, project_id=project_id, user_id=current_user.user_id)

    service = ScanScheduleService(db)
    existing = await service.get_by_id(schedule_id, current_user.user_id)
    if not existing or existing.repository_id != repo_id:
        raise HTTPException(status_code=404, detail="Schedule not found in this repository")

    updated = await service.update(schedule_id, data, user_id=current_user.user_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    org_id: UUID,
    project_id: UUID,
    repo_id: UUID,
    schedule_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    await get_repository_in_project_or_404(db, repo_id=repo_id, project_id=project_id, user_id=current_user.user_id)

    service = ScanScheduleService(db)
    existing = await service.get_by_id(schedule_id, current_user.user_id)
    if not existing or existing.repository_id != repo_id:
        raise HTTPException(status_code=404, detail="Schedule not found in this repository")

    deleted = await service.delete(schedule_id, user_id=current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
