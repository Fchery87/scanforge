import base64
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.r2 import R2Client
from app.core.config import settings
from app.db.enums import ScanStatus
from app.db.models import OrganizationIntegration, Project, Repository, Scan, ScanCompletionReceipt
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
from app.services.github import GitHubService
from app.services.github_checks import GitHubCheckPublisher
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


async def lock_live_scan(scan_id, principal, db):
    await require_scan_access(scan_id, principal, db)
    scan = await db.scalar(
        select(Scan).where(Scan.id == str(scan_id)).with_for_update().execution_options(populate_existing=True)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status in {ScanStatus.COMPLETED, ScanStatus.CANCELED}:
        raise HTTPException(status_code=409, detail="Terminal scan evidence cannot be changed")
    return scan


class ExecutionProgress(BaseModel):
    attempt_id: UUID
    execution_revision: int = Field(ge=1)


def require_current_attempt(scan, data):
    if str(scan.current_attempt_id) != str(data.attempt_id) or scan.execution_revision != data.execution_revision:
        raise HTTPException(status_code=409, detail="Execution attempt superseded")


class ScanProgressUpdate(ScanStatusUpdate, ExecutionProgress):
    pass


class ArtifactUploadRequest(ExecutionProgress):
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
    scan = await lock_live_scan(scan_id, principal, db)
    require_current_attempt(scan, data)
    if data.scanner_name == "gitleaks" or data.scanner_name not in SCAN_TYPE_SCANNERS.get(scan.scan_type or "full", []):
        raise HTTPException(status_code=409, detail="Scanner artifacts are outside this scan's allowed coverage")
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
        f"scan-artifacts/{principal.organization_id}/{scan.id}/"
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
        "upload_url": client.generate_presigned_upload_url(key, data.content_type, immutable=True),
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
    try:
        return await service.create(
            user_id=data.user_id,
            organization_id=_principal.organization_id,
            notification_type=data.notification_type,
            title=data.title,
            body=data.body,
            link=data.link,
            metadata_json=data.metadata_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/scans/{scan_id}/complete")
async def complete_scan(
    scan_id: UUID,
    data: ScanCompletionRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    try:
        result = await ScanCompletionService(db).complete(
            scan_id,
            principal.organization_id,
            data,
        )
        if getattr(scan, "trigger_type", None) == "pull_request":
            await GitHubCheckPublisher(db).publish(scan_id)
        return result
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScanCompletionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.patch("/scans/{scan_id}/status")
async def update_scan_status_internal(
    scan_id: UUID,
    data: ScanProgressUpdate,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    scan = await lock_live_scan(scan_id, principal, db)
    require_current_attempt(scan, data)
    if data.status not in {None, "running", "failed"}:
        raise HTTPException(status_code=409, detail="Use the atomic completion endpoint for terminal evidence")
    if data.summary_json and set(data.summary_json).intersection({
        "scanner_health", "coverage_complete", "coverage_comparable", "artifact_uris", "seen_fingerprints",
    }):
        raise HTTPException(status_code=409, detail="Progress cannot change completion evidence")

    if data.status:
        scan.status = ScanStatus(data.status)
    if data.error_message is not None:
        scan.error_message = data.error_message
    if data.summary_json is not None:
        scan.summary_json = data.summary_json

    if getattr(scan, "trigger_type", None) == "pull_request":
        scan.github_check_pending = True
    await db.commit()
    await db.refresh(scan)
    if getattr(scan, "trigger_type", None) == "pull_request":
        await GitHubCheckPublisher(db).publish(scan_id)
    return scan


class CreateScannerRunRequest(ExecutionProgress):
    scanner_name: str
    scanner_version: str | None = None


class UpdateScannerRunRequest(ExecutionProgress):
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
    scan = await lock_live_scan(scan_id, principal, db)
    require_current_attempt(scan, data)
    if data.scanner_name not in SCAN_TYPE_SCANNERS.get(scan.scan_type or "full", []):
        raise HTTPException(status_code=409, detail="Scanner is outside this scan's coverage")
    existing = await db.scalar(select(ScannerRun).where(
        ScannerRun.scan_id == str(scan_id), ScannerRun.scanner_name == data.scanner_name,
    ))
    if existing is not None:
        existing.status = ScanStatus.RUNNING
        await db.commit()
        return {"id": existing.id, "scanner_name": existing.scanner_name, "status": existing.status.value}

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
    scan = await lock_live_scan(UUID(str(run.scan_id)), principal, db)
    require_current_attempt(scan, data)
    if data.artifact_uri is not None or data.metadata_json is not None:
        raise HTTPException(status_code=409, detail="Artifacts and provenance require atomic completion")
    if data.status not in {None, "running", "completed", "failed"}:
        raise HTTPException(status_code=409, detail="Invalid scanner progress state")
    if run.scanner_name not in SCAN_TYPE_SCANNERS.get(scan.scan_type or "full", []):
        raise HTTPException(status_code=409, detail="Scanner is outside this scan's coverage")

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
    await require_scan_access(scan_id, principal, db)
    raise HTTPException(status_code=409, detail="Findings require atomic completion")


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
        "base_commit_sha": getattr(scan, "base_commit_sha", None),
        "head_commit_sha": getattr(scan, "head_commit_sha", None),
        "status": scan.status.value,
        "user_id": str(scan.requested_by_user_id) if scan.requested_by_user_id else None,
        "attempt_id": scan.current_attempt_id,
        "execution_revision": scan.execution_revision,
    }


@router.post("/scans/{scan_id}/claim")
async def claim_scan_execution(
    scan_id: UUID,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    await require_scan_access(scan_id, principal, db)
    scan = await db.scalar(
        select(Scan).where(Scan.id == str(scan_id)).with_for_update().execution_options(populate_existing=True)
    )
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.status == ScanStatus.COMPLETED:
        receipt = await db.scalar(select(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == str(scan_id)))
        if receipt is None:
            raise HTTPException(status_code=409, detail="Completed scan has no durable completion receipt")
        await db.commit()
        return await get_scan_execution_context(scan_id=scan_id, principal=principal, db=db)
    if scan.status == ScanStatus.CANCELED:
        await db.commit()
        return await get_scan_execution_context(scan_id=scan_id, principal=principal, db=db)
    scan.current_attempt_id = str(uuid4())
    scan.execution_revision = int(scan.execution_revision or 0) + 1
    scan.status = ScanStatus.RUNNING
    await db.commit()
    return await get_scan_execution_context(scan_id=scan_id, principal=principal, db=db)


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


@router.post("/github-checks/retry")
async def retry_github_checks(
    _scheduler: None = Depends(require_scheduler_auth),
    db: AsyncSession = Depends(get_db),
):
    return {"published": await GitHubCheckPublisher(db).retry_pending(limit=20)}
