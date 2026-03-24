from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.finding import Finding
from app.db.models.project import Project
from app.db.models.scan import Scan
from app.db.session import get_db

router = APIRouter()


class OrgStatsResponse(BaseModel):
    project_count: int = 0
    open_findings: int = 0
    critical_findings: int = 0
    scans_today: int = 0
    scans_this_week: int = 0


@router.get("/organizations/{org_id}/stats", response_model=OrgStatsResponse)
async def get_org_stats(org_id: UUID, db: AsyncSession = Depends(get_db)):
    project_count = (
        await db.execute(
            select(func.count())
            .select_from(Project)
            .where(Project.organization_id == org_id, Project.is_active.is_(True))
        )
    ).scalar_one()

    project_ids_result = await db.execute(
        select(Project.id).where(Project.organization_id == org_id)
    )
    project_ids = [r[0] for r in project_ids_result.all()]

    if not project_ids:
        return OrgStatsResponse(project_count=project_count)

    open_findings = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(Finding.project_id.in_(project_ids), Finding.status == "open")
        )
    ).scalar_one()

    critical_findings = (
        await db.execute(
            select(func.count())
            .select_from(Finding)
            .where(
                Finding.project_id.in_(project_ids),
                Finding.status == "open",
                Finding.severity == "critical",
            )
        )
    ).scalar_one()

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    scans_today = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(Scan.project_id.in_(project_ids), Scan.created_at >= today_start)
        )
    ).scalar_one()

    week_start = today_start - timedelta(days=today_start.weekday())
    scans_this_week = (
        await db.execute(
            select(func.count())
            .select_from(Scan)
            .where(Scan.project_id.in_(project_ids), Scan.created_at >= week_start)
        )
    ).scalar_one()

    return OrgStatsResponse(
        project_count=project_count,
        open_findings=open_findings,
        critical_findings=critical_findings,
        scans_today=scans_today,
        scans_this_week=scans_this_week,
    )
