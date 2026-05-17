from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.route_auth import get_project_in_org_or_404
from app.db.models.finding import Finding
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user

router = APIRouter()


@router.get("/organizations/{org_id}/projects/{project_id}/findings/trend")
async def get_findings_trend(
    org_id: UUID,
    project_id: UUID,
    days: int = 30,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_project_in_org_or_404(db, project_id=project_id, org_id=org_id, user_id=current_user.user_id)

    now = datetime.now(UTC)
    start = now - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Finding.first_seen_at, Date).label("date"),
            func.count().label("count"),
        )
        .where(Finding.project_id == project_id, Finding.first_seen_at >= start)
        .group_by(cast(Finding.first_seen_at, Date))
        .order_by(cast(Finding.first_seen_at, Date))
    )
    rows = result.all()

    data = []
    for i in range(days):
        d = (start + timedelta(days=i)).date()
        count = next((r.count for r in rows if r.date == d), 0)
        data.append({"date": d.isoformat(), "count": count})

    return {"data": data, "days": days}
