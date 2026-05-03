from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404, get_repository_in_project_or_404
from app.clients.r2 import R2Client
from app.core.config import settings
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.scans import (
    ScanCancel,
    ScanCreate,
    ScanDetailResponse,
    ScanResponse,
)
from app.services.organizations import OrganizationService
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scans import ScanService

router = APIRouter()


def _build_scan_artifact_download_url(org_id: UUID, project_id: UUID, scan_id: UUID, run_id: UUID) -> str:
    return f"/api/v1/organizations/{org_id}/projects/{project_id}/scans/{scan_id}/scanner-runs/{run_id}/download"


def _apply_scan_download_urls(scan, *, org_id: UUID, project_id: UUID) -> ScanDetailResponse:
    payload = ScanDetailResponse.model_validate(scan)
    for run in payload.scanner_runs:
        run.artifact_download_url = (
            _build_scan_artifact_download_url(org_id, project_id, payload.id, run.id) if run.artifact_uri else None
        )
        run.artifact_uri = None
        if isinstance(run.metadata_json, dict):
            run.metadata_json = {key: value for key, value in run.metadata_json.items() if not key.endswith("_uri")}
    return payload


def _get_r2_client() -> R2Client:
    return R2Client(
        endpoint=settings.R2_ENDPOINT,
        bucket=settings.R2_BUCKET,
        access_key_id=settings.R2_ACCESS_KEY_ID,
        secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )


@router.post("/", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    org_id: UUID,
    project_id: UUID,
    data: ScanCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "developer"]
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Developer, admin, or owner role required to trigger scans")

    await get_repository_in_project_or_404(
        db,
        repo_id=data.repository_id,
        project_id=project_id,
        user_id=current_user.user_id,
    )

    try:
        scan = await ScanLifecycleService(db).create_manual_scan(
            org_id=org_id,
            data=data,
            user_id=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return scan


@router.get("/", response_model=PaginatedResponse[ScanResponse])
async def list_scans(
    org_id: UUID,
    project_id: UUID,
    pagination: PaginationParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

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
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    return _apply_scan_download_urls(scan, org_id=org_id, project_id=project_id)


@router.get("/{scan_id}/scanner-runs/{run_id}/download")
async def download_scan_artifact(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    run_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    run = next((item for item in scan.scanner_runs if item.id == run_id), None)
    if not run or not run.artifact_uri:
        raise HTTPException(status_code=404, detail="Artifact not found")

    return RedirectResponse(url=_get_r2_client().generate_presigned_url(run.artifact_uri))


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    data: ScanCancel,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "developer"]
    )
    if not has_permission:
        raise HTTPException(status_code=403, detail="Developer, admin, or owner role required to cancel scans")

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        canceled = await scan_service.cancel(scan_id, data.reason, user_id=current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return canceled


@router.delete("/{scan_id}", response_model=ScanResponse)
async def delete_scan(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["owner", "admin"])
    if not has_permission:
        raise HTTPException(status_code=403, detail="Only owners and admins can delete scans")

    scan_service = ScanService(db)

    try:
        deleted = await scan_service.delete(scan_id, current_user.user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not deleted or deleted.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    return deleted
