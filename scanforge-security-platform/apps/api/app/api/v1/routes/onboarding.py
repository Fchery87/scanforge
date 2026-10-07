from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.organization import OrganizationIntegration
from app.db.models.project import Project
from app.db.models.repository import Repository
from app.db.models.scan import Scan
from app.db.models.scan_schedule import ScanSchedule
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.services.onboarding import build_onboarding_checklist
from app.services.organizations import OrganizationService

router = APIRouter()


class OnboardingStepResponse(BaseModel):
    id: str
    label: str
    description: str
    completed: bool
    action_url: str | None


class OnboardingChecklistResponse(BaseModel):
    user_id: str
    organization_id: str | None
    steps: list[OnboardingStepResponse]
    completion_percentage: int
    is_complete: bool


def serialize_checklist(checklist) -> OnboardingChecklistResponse:
    return OnboardingChecklistResponse(
        user_id=checklist.user_id,
        organization_id=checklist.organization_id,
        steps=[
            OnboardingStepResponse(
                id=step.id,
                label=step.label,
                description=step.description,
                completed=step.completed,
                action_url=step.action_url,
            )
            for step in checklist.steps
        ],
        completion_percentage=checklist.completion_percentage(),
        is_complete=checklist.is_complete(),
    )


async def _exists(db: AsyncSession, statement) -> bool:
    count = (await db.execute(select(func.count()).select_from(statement.subquery()))).scalar_one()
    return count > 0


@router.get("/onboarding", response_model=OnboardingChecklistResponse)
async def get_onboarding(
    org_id: UUID | None = Query(default=None),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if org_id is not None and not await OrganizationService(db).is_member(org_id, current_user.user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")

    projects = select(Project.id).where(Project.organization_id == org_id) if org_id else None
    has_projects = await _exists(db, projects) if projects is not None else False
    repositories = select(Repository.id).where(Repository.project_id.in_(projects)) if projects is not None else None
    has_repositories = await _exists(db, repositories) if repositories is not None else False

    checklist = build_onboarding_checklist(
        user_id=str(current_user.user_id),
        org_id=str(org_id) if org_id else None,
        has_github=await _exists(
            db, select(OrganizationIntegration.id).where(OrganizationIntegration.organization_id == org_id)
        ) if org_id else False,
        has_projects=has_projects,
        has_repositories=has_repositories,
        has_scans=await _exists(db, select(Scan.id).where(Scan.project_id.in_(projects))) if projects is not None else False,
        has_findings=await _exists(db, select(Finding.id).where(Finding.project_id.in_(projects))) if projects is not None else False,
        has_schedules=await _exists(
            db,
            select(ScanSchedule.id).where(ScanSchedule.repository_id.in_(repositories)),
        ) if repositories is not None else False,
    )
    return serialize_checklist(checklist)
