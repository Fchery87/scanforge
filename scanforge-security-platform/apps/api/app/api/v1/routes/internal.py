import base64
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.r2 import R2Client
from app.core.config import settings
from app.db.enums import ScanStatus
from app.db.models import OrganizationIntegration, Project, Repository, Scan
from app.db.models.scan import ScannerRun
from app.db.session import get_db
from app.middleware.service_auth import (
    WorkerPrincipal,
    require_scheduler_auth,
    require_service_auth,
)
from app.schemas.canonical_findings import CanonicalFindingCandidate
from app.schemas.notifications import NotificationCreate
from app.schemas.scan_completion import ScanCompletionRequest
from app.schemas.scans import ScanStatusUpdate
from app.services.findings import FindingService
from app.services.github import GitHubService
from app.services.notifications import NotificationService
from app.services.scan_completion import ScanCompletionConflict, ScanCompletionService
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scan_schedules import ScanScheduleService

logger = logging.getLogger(__name__)

SCAN_TYPE_SCANNERS = {
    "full": ["trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"],
    "diff": ["gitleaks", "semgrep", "checkov"],
    "dependencies": ["trivy", "osv", "syft", "grype"],
    "secrets": ["gitleaks"],
}

router = APIRouter(prefix="/internal", tags=["internal"])


def require_capability(capability: str):
    async def dependency(
        principal: WorkerPrincipal = Depends(require_service_auth),
    ) -> WorkerPrincipal:
        if capability not in principal.capabilities:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Worker capability required",
            )
        return principal

    return dependency


async def require_scan_access(
    scan_id: UUID,
    principal: WorkerPrincipal,
    db: AsyncSession,
) -> tuple[Scan, Project]:
    result = await db.execute(
        select(Scan, Project)
        .join(Project, Project.id == Scan.project_id)
        .where(
            Scan.id == str(scan_id),
            Project.organization_id == str(principal.organization_id),
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return row.Scan, row.Project


class ArtifactUploadRequest(BaseModel):
    scanner_name: str
    filename: str
    content_type: str = "application/json"
    size_bytes: int


@router.post("/scans/{scan_id}/artifacts/upload-url")
async def create_artifact_upload_url(
    scan_id: UUID,
    data: ArtifactUploadRequest,
    principal: WorkerPrincipal = Depends(require_capability("artifacts:write")),
    db: AsyncSession = Depends(get_db),
):
    scan, project = await require_scan_access(scan_id, principal, db)
    if data.size_bytes < 0 or data.size_bytes > 50 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Artifact too large")
    if not _valid_artifact_component(data.scanner_name) or not _valid_artifact_component(data.filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid artifact path")
    if data.content_type not in {
        "application/json",
        "application/sarif+json",
        "application/vnd.cyclonedx+json",
        "text/plain",
    }:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported artifact type")

    key = (
        f"scan-artifacts/{project.organization_id}/{scan.id}/"
        f"{data.scanner_name}/{data.filename}"
    )
    client = R2Client(
        endpoint=settings.R2_ENDPOINT,
        bucket=settings.R2_BUCKET,
        access_key_id=settings.R2_ACCESS_KEY_ID,
        secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    )
    return {
        "key": key,
        "upload_url": client.generate_presigned_upload_url(key, data.content_type),
    }


def _valid_artifact_component(value: str) -> bool:
    return (
        bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


@router.post("/notifications")
async def create_notification(
    data: NotificationCreate,
    _principal: WorkerPrincipal = Depends(require_capability("notifications:write")),
    db: AsyncSession = Depends(get_db),
):
    if not data.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id required")

    service = NotificationService(db)
    return await service.create(
        user_id=data.user_id,
        notification_type=data.notification_type,
        title=data.title,
        body=data.body,
        link=data.link,
        metadata_json=data.metadata_json,
    )


@router.post("/scans/{scan_id}/complete")
async def complete_scan(
    scan_id: UUID,
    data: ScanCompletionRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    await require_scan_access(scan_id, principal, db)
    try:
        return await ScanCompletionService(db).complete(
            scan_id,
            principal.organization_id,
            data,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScanCompletionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/scans/{scan_id}/status")
async def update_scan_status_internal(
    scan_id: UUID,
    data: ScanStatusUpdate,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    if scan.status in (ScanStatus.CANCELED, ScanStatus.COMPLETED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal scan state cannot be overwritten")
    if data.status == ScanStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Use the atomic completion endpoint")

    if data.status:
        scan.status = ScanStatus(data.status)
    if data.error_message is not None:
        scan.error_message = data.error_message
    if data.summary_json is not None:
        scan.summary_json = data.summary_json

    await db.commit()
    await db.refresh(scan)
    return scan


class CreateScannerRunRequest(BaseModel):
    scanner_name: str
    scanner_version: str | None = None


class UpdateScannerRunRequest(BaseModel):
    status: str | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    error_message: str | None = None
    artifact_uri: str | None = None
    metadata_json: dict | None = None


@router.post("/scans/{scan_id}/scanner-runs")
async def create_scanner_run(
    scan_id: UUID,
    data: CreateScannerRunRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    await require_scan_access(scan_id, principal, db)

    run = ScannerRun(
        scan_id=str(scan_id),
        scanner_name=data.scanner_name,
        scanner_version=data.scanner_version,
        status=ScanStatus.RUNNING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return {"id": run.id, "scanner_name": run.scanner_name, "status": run.status.value}


@router.patch("/scanner-runs/{run_id}")
async def update_scanner_run(
    run_id: UUID,
    data: UpdateScannerRunRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ScannerRun, str(run_id))
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanner run not found")
    await require_scan_access(UUID(str(run.scan_id)), principal, db)

    if data.status is not None:
        run.status = ScanStatus(data.status)
    if data.duration_ms is not None:
        run.duration_ms = data.duration_ms
    if data.exit_code is not None:
        run.exit_code = data.exit_code
    if data.error_message is not None:
        run.error_message = data.error_message
    if data.artifact_uri is not None:
        run.artifact_uri = data.artifact_uri
    if data.metadata_json is not None:
        run.metadata_json = data.metadata_json

    await db.commit()
    await db.refresh(run)
    return {"id": run.id, "status": run.status.value}


class PersistFindingsRequest(BaseModel):
    findings: list[CanonicalFindingCandidate]


@router.post("/scans/{scan_id}/findings")
async def persist_scan_findings(
    scan_id: UUID,
    data: PersistFindingsRequest,
    principal: WorkerPrincipal = Depends(require_capability("findings:write")),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    if not data.findings:
        return {"inserted": 0}

    service = FindingService(db)
    new_count, updated_count = await service.upsert_from_scan(
        scan_id=str(scan_id),
        repository_id=str(scan.repository_id),
        project_id=str(scan.project_id),
        normalized_findings=data.findings,
    )

    return {"inserted": new_count, "updated": updated_count}


def _valid_github_component(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"-", ".", "_"} for char in value)


@router.get("/repositories/{repo_id}/clone-url")
async def get_repository_clone_url(
    repo_id: UUID,
    principal: WorkerPrincipal = Depends(require_capability("repositories:clone")),
    db: AsyncSession = Depends(get_db),
):
    """Return an authenticated clone URL for the worker to use."""
    repo = await db.get(Repository, str(repo_id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    if (
        getattr(repo.provider, "value", repo.provider) != "github"
        or not _valid_github_component(repo.owner_name)
        or not _valid_github_component(repo.repo_name)
    ):
        raise HTTPException(status_code=404, detail="Repository not eligible for private beta scanning")
    project = await db.get(Project, str(repo.project_id))
    if not project or str(project.organization_id) != str(principal.organization_id):
        raise HTTPException(status_code=404, detail="Repository not found")

    result = await db.execute(
        select(OrganizationIntegration).where(OrganizationIntegration.organization_id == project.organization_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="No GitHub integration for this org")

    gh = GitHubService(db)
    if not await gh.repository_is_accessible(
        integration.installation_id,
        repo.owner_name,
        repo.repo_name,
    ):
        raise HTTPException(status_code=404, detail="Repository is not accessible to the GitHub installation")
    token = await gh._get_installation_token(integration.installation_id)

    clone_url = f"https://github.com/{repo.owner_name}/{repo.repo_name}.git"
    basic_auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()

    return {
        "clone_url": clone_url,
        "auth_header": f"Authorization: Basic {basic_auth}",
    }


@router.get("/scans/{scan_id}/execution-context")
async def get_scan_execution_context(
    scan_id: UUID,
    principal: WorkerPrincipal = Depends(require_capability("scans:read")),
    db: AsyncSession = Depends(get_db),
):
    scan, project = await require_scan_access(scan_id, principal, db)

    scan_type = getattr(scan, "scan_type", None) or "full"

    return {
        "scan_id": str(scan.id),
        "org_id": str(project.organization_id),
        "repository_id": str(scan.repository_id),
        "project_id": str(scan.project_id),
        "scan_type": scan_type,
        "expected_scanners": SCAN_TYPE_SCANNERS.get(scan_type, SCAN_TYPE_SCANNERS["full"]),
        "coverage_scope": {
            "branch": scan.branch_name,
            "commit_sha": scan.commit_sha,
            "scan_type": scan_type,
        },
        "branch": scan.branch_name,
        "commit_sha": scan.commit_sha,
        "status": scan.status.value,
        "user_id": str(scan.requested_by_user_id) if scan.requested_by_user_id else None,
    }


@router.post("/scan-schedules/run-due")
async def run_due_scan_schedules(
    _scheduler: None = Depends(require_scheduler_auth),
    db: AsyncSession = Depends(get_db),
):
    schedule_service = ScanScheduleService(db)
    lifecycle = ScanLifecycleService(db)
    due_schedules = await schedule_service.get_due_schedules(limit=50)
    queued = 0
    failed = 0

    for schedule in due_schedules:
        try:
            outcome = await lifecycle.create_scheduled_scan(schedule)
            if outcome.enqueued:
                await schedule_service.mark_run(schedule.id)
                queued += 1
            else:
                failed += 1
        except Exception:
            logger.error("Failed to create scheduled scan for schedule %s", schedule.id, exc_info=True)
            failed += 1

    return {"found": len(due_schedules), "queued": queued, "failed": failed}
