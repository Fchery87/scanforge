from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ScanStatus
from app.db.models import Finding, OrganizationIntegration, Project, Repository, Scan
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.middleware.service_auth import require_service_auth
from app.schemas.notifications import NotificationCreate
from app.schemas.scans import ScanStatusUpdate
from app.services.findings import FindingService
from app.services.notifications import NotificationService
from app.services.onboarding import build_onboarding_checklist

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(require_service_auth)])


@router.post("/notifications")
async def create_notification(
    data: NotificationCreate,
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


@router.patch("/scans/{scan_id}/status")
async def update_scan_status_internal(
    scan_id: UUID,
    data: ScanStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    scan = await db.get(Scan, str(scan_id))
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    if data.status:
        scan.status = ScanStatus(data.status)
    if data.error_message is not None:
        scan.error_message = data.error_message
    if data.summary_json is not None:
        scan.summary_json = data.summary_json

    await db.commit()
    await db.refresh(scan)
    return scan


class FindingItem(BaseModel):
    rule_id: str
    severity: str
    category: str
    title: str
    description: str | None = None
    file_path: str | None = None
    line_number: int | None = None


class PersistFindingsRequest(BaseModel):
    findings: list[FindingItem]


@router.post("/scans/{scan_id}/findings")
async def persist_scan_findings(
    scan_id: UUID,
    data: PersistFindingsRequest,
    db: AsyncSession = Depends(get_db),
):
    if not data.findings:
        return {"inserted": 0}

    result = await db.execute(select(Scan.repository_id, Scan.project_id).where(Scan.id == str(scan_id)))
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    repo_id, proj_id = row

    service = FindingService(db)
    findings_dicts = [f.model_dump() for f in data.findings]
    new_count, updated_count = await service.upsert_from_scan(
        scan_id=scan_id,
        repository_id=UUID(repo_id),
        project_id=UUID(proj_id),
        normalized_findings=findings_dicts,
    )

    return {"inserted": new_count, "updated": updated_count}


@router.get("/repositories/{repo_id}/clone-url")
async def get_repository_clone_url(
    repo_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return an authenticated clone URL for the worker to use."""
    repo = await db.get(Repository, str(repo_id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Get the org's GitHub integration
    project = await db.get(Project, str(repo.project_id))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(OrganizationIntegration).where(OrganizationIntegration.organization_id == project.organization_id)
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="No GitHub integration for this org")

    # Get an installation access token
    from app.services.github import GitHubService

    gh = GitHubService(db)
    token = await gh._get_installation_token(integration.installation_id)

    # Build authenticated clone URL: https://x-access-token:<token>@github.com/owner/repo.git
    clone_url = repo.clone_url or f"https://github.com/{repo.full_name}.git"
    authed_url = clone_url.replace("https://", f"https://x-access-token:{token}@")

    return {"clone_url": authed_url}


@router.get("/onboarding")
async def get_onboarding_checklist(
    org_id: str | None = None,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    has_github = False
    if org_id:
        github_result = await db.execute(select(exists().where(OrganizationIntegration.organization_id == org_id)))
        has_github = github_result.scalar()

    has_projects = False
    has_repositories = False
    has_scans = False
    has_findings = False

    if org_id:
        project_result = await db.execute(select(exists().where(Project.organization_id == org_id)))
        has_projects = project_result.scalar()

        repo_result = await db.execute(
            select(
                exists().where(Repository.project_id.in_(select(Project.id).where(Project.organization_id == org_id)))
            )
        )
        has_repositories = repo_result.scalar()

        scan_result = await db.execute(
            select(exists().where(Scan.project_id.in_(select(Project.id).where(Project.organization_id == org_id))))
        )
        has_scans = scan_result.scalar()

        finding_result = await db.execute(
            select(exists().where(Finding.project_id.in_(select(Project.id).where(Project.organization_id == org_id))))
        )
        has_findings = finding_result.scalar()

    return build_onboarding_checklist(
        user_id=current_user.user_id,
        org_id=org_id,
        has_github=has_github,
        has_projects=has_projects,
        has_repositories=has_repositories,
        has_scans=has_scans,
        has_findings=has_findings,
    )
