from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.scan import Scan
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.services.projects import ProjectService

router = APIRouter()


class ScorecardResponse(BaseModel):
    project_id: str
    overall_score: float = 100.0
    security_score: float = 100.0
    secrets_score: float = 100.0
    dependency_score: float = 100.0
    grade: str = "A+"
    open_critical: int = 0
    open_high: int = 0
    open_medium: int = 0
    open_low: int = 0
    open_total: int = 0
    fixed_30d: int = 0
    new_this_week: int = 0
    scan_count: int = 0
    last_scan_at: str | None = None


def _grade(score: float) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


@router.get(
    "/organizations/{org_id}/projects/{project_id}/scorecard",
    response_model=ScorecardResponse,
)
async def get_project_scorecard(
    org_id: UUID,
    project_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project_service = ProjectService(db)
    has_access = await project_service.user_has_access(project_id, current_user.user_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="No access to this project")

    now = datetime.now(UTC)

    sev_counts = {}
    for sev in ("critical", "high", "medium", "low"):
        count = (
            await db.execute(
                select(func.count())
                .select_from(Finding)
                .where(
                    Finding.project_id == project_id,
                    Finding.status == "open",
                    Finding.severity == sev,
                )
            )
        ).scalar_one_or_none() or 0
        sev_counts[sev] = count

    open_total = sum(sev_counts.values())

    penalty = (
        sev_counts["critical"] * 25
        + sev_counts["high"] * 10
        + sev_counts["medium"] * 3
        + sev_counts["low"] * 0.5
    )
    security_score = round(max(0, 100 - penalty), 1)

    open_secrets = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.project_id == project_id,
                Finding.status == "open",
                Finding.category == "secret",
            )
        )
    ).scalar_one_or_none() or 0
    secrets_score = round(max(0, 100 - min(open_secrets * 20, 100)), 1)

    open_deps = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.project_id == project_id,
                Finding.status == "open",
                Finding.category.in_(["vulnerability", "dependency_outdated"]),
            )
        )
    ).scalar_one_or_none() or 0
    dep_penalty = min(open_deps * 5, 100)
    dependency_score = round(max(0, 100 - dep_penalty), 1)

    overall = round(security_score * 0.5 + secrets_score * 0.3 + dependency_score * 0.2, 1)

    thirty_days_ago = now - timedelta(days=30)
    fixed_30d = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.project_id == project_id,
                Finding.status == "fixed",
                Finding.updated_at >= thirty_days_ago,
            )
        )
    ).scalar_one_or_none() or 0

    week_ago = now - timedelta(days=7)
    new_this_week = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(Finding.project_id == project_id, Finding.first_seen_at >= week_ago)
        )
    ).scalar_one_or_none() or 0

    scan_count = (
        await db.execute(
            select(func.count()).select_from(Scan).where(Scan.project_id == project_id)
        )
    ).scalar_one_or_none() or 0
    last_scan = (
        await db.execute(
            select(Scan.created_at)
            .where(Scan.project_id == project_id)
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return ScorecardResponse(
        project_id=str(project_id),
        overall_score=overall,
        security_score=security_score,
        secrets_score=secrets_score,
        dependency_score=dependency_score,
        grade=_grade(overall),
        open_critical=sev_counts["critical"],
        open_high=sev_counts["high"],
        open_medium=sev_counts["medium"],
        open_low=sev_counts["low"],
        open_total=open_total,
        fixed_30d=fixed_30d,
        new_this_week=new_this_week,
        scan_count=scan_count,
        last_scan_at=last_scan.isoformat() if last_scan else None,
    )
