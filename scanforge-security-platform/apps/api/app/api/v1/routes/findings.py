from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.findings import (
    FindingBulkAction,
    FindingDetailResponse,
    FindingResolve,
    FindingResponse,
    FindingStats,
    FindingSuppress,
)
from app.services.findings import FindingService
from app.services.projects import ProjectService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[FindingResponse])
async def list_findings(
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    severity: str | None = Query(None, alias="severity"),
    category: str | None = Query(None, alias="category"),
    status_filter: str | None = Query(None, alias="status"),
    scanner: str | None = Query(None, alias="scanner"),
    repository_id: UUID | None = Query(None, alias="repositoryId"),
    search: str | None = Query(None, alias="search"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    findings, total = await service.list_for_project(
        project_id,
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        severity=severity,
        category=category,
        status=status_filter,
        scanner=scanner,
        repository_id=repository_id,
        search=search,
    )

    return PaginatedResponse(
        items=findings,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/stats", response_model=FindingStats)
async def get_finding_stats(
    project_id: UUID,
    repository_id: UUID | None = Query(None, alias="repositoryId"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    return await service.get_stats(project_id, current_user.user_id, repository_id=repository_id)


@router.get("/{finding_id}", response_model=FindingDetailResponse)
async def get_finding(
    project_id: UUID,
    finding_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    finding = await service.get_by_id(finding_id, current_user.user_id)
    if not finding or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    return FindingDetailResponse.model_validate(finding)


@router.post("/{finding_id}/suppress", response_model=FindingResponse)
async def suppress_finding(
    project_id: UUID,
    finding_id: UUID,
    data: FindingSuppress,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    finding = await service.suppress(finding_id, current_user.user_id, data.reason, data.rule_id)
    if not finding or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    return finding


@router.post("/{finding_id}/resolve", response_model=FindingResponse)
async def resolve_finding(
    project_id: UUID,
    finding_id: UUID,
    data: FindingResolve,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    finding = await service.resolve(
        finding_id, current_user.user_id, data.fixed_version, data.reason
    )
    if not finding or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    return finding


@router.post("/{finding_id}/reopen", response_model=FindingResponse)
async def reopen_finding(
    project_id: UUID,
    finding_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    finding = await service.reopen(finding_id, current_user.user_id)
    if not finding or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    return finding


@router.get("/{finding_id}/events")
async def get_finding_events(
    project_id: UUID,
    finding_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)
    finding = await service.get_by_id(finding_id, current_user.user_id)
    if not finding or finding.project_id != project_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    return await service.get_events(finding_id, current_user.user_id)


@router.post("/bulk", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_finding_action(
    project_id: UUID,
    data: FindingBulkAction,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    service = FindingService(db)

    if data.action == "suppress":
        await service.bulk_suppress(data.finding_ids, current_user.user_id, data.reason)
    elif data.action == "resolve":
        await service.bulk_resolve(data.finding_ids, current_user.user_id)

