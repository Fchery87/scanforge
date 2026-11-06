from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404, get_repository_in_project_or_404
from app.clients.r2 import R2Client
from app.core.beta_capabilities import assert_scan_request_supported
from app.core.config import settings
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.middleware.redis_rate_limit import per_route_limiter
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.scans import (
    CapabilityCoverageResponse,
    ScanCancel,
    ScanCreate,
    ScanDetailResponse,
    ScanResponse,
    ShadowCandidateLabelRequest,
    ShadowCandidateLabelResponse,
    ShadowClassificationResponse,
    ShadowReviewResponse,
)
from app.services.access_policies import FINDING_MUTATION_ROLES
from app.services.artifact_finalization import ArtifactFinalizationService
from app.services.evidence_contract import derive_capability_coverage
from app.services.organizations import OrganizationService
from app.services.pr_classification import ShadowClassificationService
from app.services.scan_dispatch import ScanCapacityExceededError
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scans import ScanService
from app.services.shadow_review_view import ShadowReviewViewService

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
    health = (payload.summary_json or {}).get("scanner_health")
    expected = health.get("expected") if isinstance(health, dict) else None
    payload.capability_coverage = [
        CapabilityCoverageResponse.model_validate(item)
        for item in derive_capability_coverage(payload.scanner_runs, expected_scanners=expected)
    ]
    return payload


def _get_r2_client() -> R2Client:
    return R2Client(
        endpoint=settings.R2_ENDPOINT,
        bucket=settings.R2_BUCKET,
        access_key_id=settings.R2_ACCESS_KEY_ID,
        secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )


@router.post(
    "/",
    response_model=ScanResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(per_route_limiter(20, 60, "scans:create"))],
)
async def create_scan(
    org_id: UUID,
    project_id: UUID,
    data: ScanCreate,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_scan_request_supported(data)
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer", "developer"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=403,
            detail="Developer, security reviewer, admin, or owner role required to trigger scans",
        )

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
    except ScanCapacityExceededError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)) from e
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
    *,
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

    payload = _apply_scan_download_urls(scan, org_id=org_id, project_id=project_id)
    if scan.trigger_type == "pull_request":
        payload.shadow_classification = ShadowClassificationResponse.model_validate(
            await ShadowClassificationService(db).classify(scan)
        )
    return payload


async def _get_shadow_pr_scan_or_404(db: AsyncSession, *, project_id: UUID, scan_id: UUID, user_id: UUID):
    scan = await ScanService(db).get_by_id(scan_id, user_id)
    if not scan or scan.project_id != project_id or scan.trigger_type != "pull_request":
        raise HTTPException(status_code=404, detail="Shadow review not found")
    return scan


@router.get("/{scan_id}/shadow-review", response_model=ShadowReviewResponse)
async def get_shadow_review(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Internal per-PR shadow results. Read-only; never published to GitHub."""
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    scan = await _get_shadow_pr_scan_or_404(db, project_id=project_id, scan_id=scan_id, user_id=current_user.user_id)
    return ShadowReviewResponse.model_validate(await ShadowReviewViewService(db).build(scan))


@router.put(
    "/{scan_id}/shadow-review/candidates/{candidate_id}/label",
    response_model=ShadowCandidateLabelResponse,
)
async def label_shadow_candidate(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    candidate_id: UUID,
    data: ShadowCandidateLabelRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record the caller's evaluation label. Never suppresses or changes any finding."""
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)
    if not await OrganizationService(db).user_has_permission(org_id, current_user.user_id, FINDING_MUTATION_ROLES):
        raise HTTPException(
            status_code=403, detail="Security reviewer, admin, or owner role required to label shadow results"
        )
    scan = await _get_shadow_pr_scan_or_404(db, project_id=project_id, scan_id=scan_id, user_id=current_user.user_id)
    try:
        row = await ShadowReviewViewService(db).set_label(
            org_id=org_id, scan=scan, candidate_id=candidate_id, actor_user_id=current_user.user_id, label=data.label
        )
    except LookupError:
        # The label's candidate or scan is not inside this tenant's corpus; nothing is recorded.
        await db.rollback()
        raise HTTPException(status_code=404, detail="Shadow candidate not found") from None
    if row is None:
        raise HTTPException(status_code=404, detail="Shadow candidate not found")
    return ShadowCandidateLabelResponse.model_validate(
        {
            "candidate_id": row.candidate_id,
            "label": row.label,
            "actor_user_id": row.actor_user_id,
            "labeled_at": row.updated_at or row.created_at,
        }
    )


@router.get("/{scan_id}/scanner-runs/{run_id}/download")
async def download_scan_artifact(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    run_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    *,
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

    # Only verified, unerased artifacts of this scan are signable; a stored
    # reference alone never authorizes a presigned URL.
    client = _get_r2_client()
    storage_uri = await ArtifactFinalizationService(db, client).downloadable_uri(
        str(scan_id), str(org_id), run.artifact_uri
    )
    if storage_uri is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return RedirectResponse(url=client.generate_presigned_url(storage_uri))


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan(
    org_id: UUID,
    project_id: UUID,
    scan_id: UUID,
    data: ScanCancel,
    current_user: UserContext = Depends(get_current_user),
    *,
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(
        org_id, current_user.user_id, ["owner", "admin", "security_reviewer", "developer"]
    )
    if not has_permission:
        raise HTTPException(
            status_code=403,
            detail="Developer, security reviewer, admin, or owner role required to cancel scans",
        )

    scan_service = ScanService(db)
    scan = await scan_service.get_by_id(scan_id, current_user.user_id)
    if not scan or scan.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    try:
        canceled = await scan_service.cancel(
            scan_id,
            data.reason,
            user_id=current_user.user_id,
            project_id=project_id,
        )
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
        deleted = await scan_service.delete(
            scan_id,
            current_user.user_id,
            project_id=project_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not deleted or deleted.project_id != project_id:
        raise HTTPException(status_code=404, detail="Scan not found")

    return deleted
