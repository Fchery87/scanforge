import base64
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.strict_contract_route import StrictCompletionRoute
from app.clients.r2 import R2Client
from app.core.beta_capabilities import is_beta_capability_enabled
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
from app.services.evidence_contract import EvidenceContractError
from app.services.findings import FindingService
from app.services.github import GitHubService
from app.services.notifications import NotificationAuthorizationError, NotificationService
from app.services.scan_completion import ScanCompletionConflict, ScanCompletionService
from app.services.scan_lease import LEASE_SECONDS, RENEWAL_SECONDS, LeaseConflict, ScanLeaseService
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scan_schedules import ScanScheduleService
from app.services.scans import ScanAuthorizationError, ScanService

logger = logging.getLogger(__name__)

SCAN_TYPE_SCANNERS = {
    "full": ["trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"],
    "diff": ["gitleaks", "semgrep", "checkov"],
    "dependencies": ["trivy", "osv", "syft", "grype"],
    "secrets": ["gitleaks"],
}

router = APIRouter(prefix="/internal", tags=["internal"], route_class=StrictCompletionRoute)

# Scans in a terminal state own a frozen completion identity; fetching
# execution-context for them never mints a new attempt.
TERMINAL_SCAN_STATUSES = frozenset({ScanStatus.CANCELED, ScanStatus.COMPLETED})


@dataclass(frozen=True)
class ExecutionAttemptIdentity:
    attempt_id: str
    execution_revision: int
    worker_incarnation_id: str


async def require_execution_attempt_identity(
    attempt_id: str = Header(alias="X-Scan-Attempt-Id"),
    execution_revision: int = Header(alias="X-Scan-Execution-Revision"),
    worker_incarnation_id: str = Header(alias="X-Scan-Worker-Incarnation-Id"),
) -> ExecutionAttemptIdentity:
    return ExecutionAttemptIdentity(
        attempt_id=attempt_id,
        execution_revision=execution_revision,
        worker_incarnation_id=worker_incarnation_id,
    )


def assert_live_execution_authority(
    scan: Scan,
    principal: WorkerPrincipal,
    attempt: ExecutionAttemptIdentity,
) -> None:
    if (
        scan.current_attempt_id != attempt.attempt_id
        or scan.execution_revision != attempt.execution_revision
        or scan.worker_incarnation_id != attempt.worker_incarnation_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_attempt", "message": "Execution attempt was superseded"},
        )
    if scan.lease_owner != str(principal.worker_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_worker", "message": "Worker principal does not own this attempt"},
        )
    lease_expires_at = scan.lease_expires_at
    if lease_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "lease_missing", "message": "Execution lease is missing"},
        )
    if lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    if lease_expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "lease_expired", "message": "Execution lease has expired"},
        )


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


class HeartbeatRequest(BaseModel):
    attempt_id: str
    execution_revision: int
    worker_incarnation_id: str


@router.post("/scans/{scan_id}/artifacts/upload-url")
async def create_artifact_upload_url(
    scan_id: UUID,
    data: ArtifactUploadRequest,
    principal: WorkerPrincipal = Depends(require_capability("artifacts:write")),
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    try:
        scan_project = await ScanService(db).authorize_scan_access(
            scan_id,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    if scan_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    scan, project = scan_project
    assert_live_execution_authority(scan, principal, attempt)
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
    principal: WorkerPrincipal = Depends(require_capability("notifications:write")),
    db: AsyncSession = Depends(get_db),
):
    if not data.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id required")

    service = NotificationService(db)
    try:
        return await service.create(
            user_id=data.user_id,
            notification_type=data.notification_type,
            title=data.title,
            body=data.body,
            caller_organization_id=principal.organization_id,
            organization_id=principal.organization_id,
            link=data.link,
            metadata_json=data.metadata_json,
        )
    except NotificationAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.post("/scans/{scan_id}/complete")
async def complete_scan(
    scan_id: UUID,
    data: ScanCompletionRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    assert_live_execution_authority(
        scan,
        principal,
        ExecutionAttemptIdentity(
            attempt_id=str(data.winning_attempt_id),
            execution_revision=data.execution_revision,
            worker_incarnation_id=data.worker_incarnation_id or "",
        ),
    )
    try:
        return await ScanCompletionService(db).complete(
            scan_id,
            principal.organization_id,
            data,
            worker_principal_id=str(principal.worker_id),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScanCompletionConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EvidenceContractError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.patch("/scans/{scan_id}/status")
async def update_scan_status_internal(
    scan_id: UUID,
    data: ScanStatusUpdate,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    assert_live_execution_authority(scan, principal, attempt)
    if scan.status in (ScanStatus.CANCELED, ScanStatus.COMPLETED):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal scan state cannot be overwritten")
    if data.status == ScanStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Use the atomic completion endpoint")

    try:
        return await ScanService(db).update_status(
            scan_id,
            ScanStatus(data.status) if data.status else scan.status,
            error_message=data.error_message,
            summary_json=data.summary_json,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    assert_live_execution_authority(scan, principal, attempt)
    try:
        run = await ScanService(db).create_scanner_run(
            scan_id,
            data.scanner_name,
            data.scanner_version,
            status=ScanStatus.RUNNING,
            attempt_id=attempt.attempt_id,
            execution_revision=attempt.execution_revision,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return {"id": run.id, "scanner_name": run.scanner_name, "status": run.status.value}


@router.patch("/scanner-runs/{run_id}")
async def update_scanner_run(
    run_id: UUID,
    data: UpdateScannerRunRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    run = await db.get(ScannerRun, str(run_id))
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanner run not found")
    scan, _project = await require_scan_access(UUID(str(run.scan_id)), principal, db)
    assert_live_execution_authority(scan, principal, attempt)

    try:
        updated = await ScanService(db).update_scanner_run(
            run_id,
            ScanStatus(data.status) if data.status is not None else None,
            duration_ms=data.duration_ms,
            exit_code=data.exit_code,
            error_message=data.error_message,
            artifact_uri=data.artifact_uri,
            metadata_json=data.metadata_json,
            attempt_id=attempt.attempt_id,
            execution_revision=attempt.execution_revision,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scanner run not found")
    return {"id": updated.id, "status": updated.status.value}


class PersistFindingsRequest(BaseModel):
    findings: list[CanonicalFindingCandidate]


@router.post("/scans/{scan_id}/findings")
async def persist_scan_findings(
    scan_id: UUID,
    data: PersistFindingsRequest,
    principal: WorkerPrincipal = Depends(require_capability("findings:write")),
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    scan, _project = await require_scan_access(scan_id, principal, db)
    assert_live_execution_authority(scan, principal, attempt)
    if not data.findings:
        return {"inserted": 0}

    service = FindingService(db)
    try:
        new_count, updated_count = await service.upsert_from_scan(
            scan_id=str(scan_id),
            repository_id=str(scan.repository_id),
            project_id=str(scan.project_id),
            normalized_findings=data.findings,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    return {"inserted": new_count, "updated": updated_count}


def _valid_github_component(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"-", ".", "_"} for char in value)


@router.get("/repositories/{repo_id}/clone-url")
async def get_repository_clone_url(
    repo_id: UUID,
    principal: WorkerPrincipal = Depends(require_capability("repositories:clone")),
    attempt: ExecutionAttemptIdentity = Depends(require_execution_attempt_identity),
    db: AsyncSession = Depends(get_db),
):
    """Return an authenticated clone URL for the worker to use."""
    repo = (
        await db.execute(
            select(Repository)
            .where(Repository.id == str(repo_id))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not getattr(repo, "is_active", True) or getattr(repo, "lifecycle_state", "connected") != "connected":
        raise HTTPException(
            status_code=404,
            detail="Repository is not active or requires authorization revalidation",
        )

    if (
        getattr(repo.provider, "value", repo.provider) != "github"
        or not _valid_github_component(repo.owner_name)
        or not _valid_github_component(repo.repo_name)
    ):
        raise HTTPException(status_code=404, detail="Repository not eligible for private beta scanning")
    project = await db.get(Project, str(repo.project_id))
    if not project or str(project.organization_id) != str(principal.organization_id):
        raise HTTPException(status_code=404, detail="Repository not found")

    scan = (
        await db.execute(
            select(Scan).where(Scan.repository_id == str(repo.id), Scan.current_attempt_id == attempt.attempt_id)
        )
    ).scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=409, detail={"code": "stale_attempt"})
    assert_live_execution_authority(scan, principal, attempt)

    result = await db.execute(
        select(OrganizationIntegration).where(OrganizationIntegration.organization_id == project.organization_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="No GitHub integration for this org")

    repo_integration_result = await db.execute(
        select(RepositoryIntegration).where(RepositoryIntegration.repository_id == str(repo.id))
    )
    repo_integration = repo_integration_result.scalar_one_or_none()
    if (
        repo_integration is not None
        and repo_integration.installation_id is not None
        and str(repo_integration.installation_id) != str(integration.installation_id)
    ):
        raise HTTPException(
            status_code=404,
            detail="Repository installation binding does not match organization integration",
        )

    gh = GitHubService(db)
    try:
        accessible = await gh.repository_is_accessible(
            integration.installation_id,
            repo.owner_name,
            repo.repo_name,
            expected_external_repo_id=getattr(repo, "external_repo_id", None),
        )
    except TypeError:
        accessible = await gh.repository_is_accessible(
            integration.installation_id,
            repo.owner_name,
            repo.repo_name,
        )
    if not accessible:
        raise HTTPException(status_code=404, detail="Repository is not accessible to the GitHub installation")
    token = await gh._get_installation_token(integration.installation_id)

    clone_url = f"https://github.com/{repo.owner_name}/{repo.repo_name}.git"
    basic_auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()

    return {
        "clone_url": clone_url,
        "auth_header": f"Authorization: Basic {basic_auth}",
        "external_repo_id": getattr(repo, "external_repo_id", None),
    }


@router.get("/scans/{scan_id}/execution-context")
async def get_scan_execution_context(
    scan_id: UUID,
    principal: WorkerPrincipal = Depends(require_capability("scans:read")),
    db: AsyncSession = Depends(get_db),
):
    # Service-boundary org check (merge follow-up): the R06 ScanAuthorizationError
    # pattern applies to execution-context too, not only to mutations.
    try:
        scan_project = await ScanService(db).authorize_scan_access(
            scan_id,
            caller_organization_id=principal.organization_id,
        )
    except ScanAuthorizationError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    if scan_project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    scan, project = scan_project

    scan_type = getattr(scan, "scan_type", None) or "full"

    # Server-issued attempt identity: every fetch for a non-terminal scan mints a
    # fresh attempt id and bumps execution_revision in one transaction, so only the
    # latest fetch carries an identity that can complete the scan.  Smallest sane
    # rule for terminal scans: the stored identity is returned frozen and never
    # bumped (attempt_id stays null when a scan ended before any attempt was issued).
    lease_owner = str(principal.worker_id)
    if scan.status not in TERMINAL_SCAN_STATUSES:
        # R09: attempt identity is granted together with a 120 s execution
        # lease.  A live lease rejects a duplicate claimant (409 lease_active);
        # an expired lease is reclaimed with a dead-worker visibility event.
        try:
            locked_scan, reclaim_reason = await ScanLeaseService(db).acquire(
                str(scan.id),
                terminal_statuses=TERMINAL_SCAN_STATUSES,
                worker_owner=lease_owner,
            )
        except LeaseConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": exc.reason,
                    "current_owner": exc.current_owner,
                    "remaining_seconds": exc.remaining_seconds,
                },
            ) from exc
    else:
        locked_scan = (
            await db.execute(select(Scan).where(Scan.id == str(scan.id)).with_for_update())
        ).scalar_one()
        reclaim_reason = "terminal"

    full_ref_name = getattr(scan, "full_ref_name", None) or (
        f"refs/heads/{scan.branch_name}" if scan.branch_name else None
    )
    branch_generation_number = int(getattr(scan, "branch_generation_number", 1) or 1)
    ancestry_status = getattr(scan, "ancestry_status", "unknown") or "unknown"
    expected_scanners = getattr(scan, "expected_scanners_json", None) or SCAN_TYPE_SCANNERS.get(
        scan_type, SCAN_TYPE_SCANNERS["full"]
    )

    return {
        "scan_id": str(scan.id),
        "org_id": str(project.organization_id),
        "repository_id": str(scan.repository_id),
        "project_id": str(scan.project_id),
        "scan_type": scan_type,
        "expected_scanners": expected_scanners,
        "coverage_scope": {
            "branch": scan.branch_name,
            "full_ref_name": full_ref_name,
            "branch_generation_number": branch_generation_number,
            "ancestry_status": ancestry_status,
            "commit_sha": scan.commit_sha,
            "scan_type": scan_type,
        },
        "branch": scan.branch_name,
        "full_ref_name": full_ref_name,
        "branch_generation_number": branch_generation_number,
        "ancestry_status": ancestry_status,
        "commit_sha": scan.commit_sha,
        "status": scan.status.value,
        "user_id": str(scan.requested_by_user_id) if scan.requested_by_user_id else None,
        "attempt_id": locked_scan.current_attempt_id,
        "execution_revision": locked_scan.execution_revision,
        "worker_incarnation_id": locked_scan.worker_incarnation_id,
        "lease_owner": locked_scan.lease_owner,
        "lease_expires_at": locked_scan.lease_expires_at.isoformat() if locked_scan.lease_expires_at else None,
        "reclaim_reason": reclaim_reason,
    }


@router.post("/scans/{scan_id}/heartbeat")
async def renew_scan_lease(
    scan_id: UUID,
    data: HeartbeatRequest,
    principal: WorkerPrincipal = Depends(require_capability("scans:write")),
    db: AsyncSession = Depends(get_db),
):
    """Renew the execution lease for the current attempt (R09).

    Candidate timings (R03 D1): 120 s lease, renewal every 30 s.  A stale
    attempt and an expired lease are both 409; an expired lease cannot be
    renewed, so the worker must stop and reclaim instead.
    """
    scan, _project = await require_scan_access(scan_id, principal, db)
    assert_live_execution_authority(
        scan,
        principal,
        ExecutionAttemptIdentity(
            attempt_id=data.attempt_id,
            execution_revision=data.execution_revision,
            worker_incarnation_id=data.worker_incarnation_id,
        ),
    )
    try:
        scan = await ScanLeaseService(db).renew(
            str(scan_id),
            attempt_id=data.attempt_id,
            execution_revision=data.execution_revision,
            worker_incarnation_id=data.worker_incarnation_id,
            worker_owner=str(principal.worker_id),
        )
    except LeaseConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": exc.reason,
                "current_owner": exc.current_owner,
                "remaining_seconds": exc.remaining_seconds,
            },
        ) from exc
    return {
        "scan_id": str(scan.id),
        "attempt_id": scan.current_attempt_id,
        "execution_revision": scan.execution_revision,
        "lease_expires_at": scan.lease_expires_at.isoformat() if scan.lease_expires_at else None,
        "last_heartbeat_at": scan.last_heartbeat_at.isoformat() if scan.last_heartbeat_at else None,
        "lease_seconds": LEASE_SECONDS,
        "renewal_seconds": RENEWAL_SECONDS,
    }


@router.post("/scan-schedules/run-due")
async def run_due_scan_schedules(
    _scheduler: None = Depends(require_scheduler_auth),
    db: AsyncSession = Depends(get_db),
):
    if not is_beta_capability_enabled("scan_schedules"):
        return {"found": 0, "queued": 0, "failed": 0, "disabled": True}

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
