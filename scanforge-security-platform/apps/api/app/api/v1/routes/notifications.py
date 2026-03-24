
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.notifications import NotificationMarkRead, NotificationResponse
from app.services.notifications import NotificationService

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    pagination: PaginationParams = Depends(),
    unread_only: bool = Query(False, alias="unreadOnly"),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    notifications, total = await service.list_for_user(
        current_user.user_id,
        skip=pagination.skip,
        limit=pagination.limit,
        unread_only=unread_only,
    )

    return PaginatedResponse(
        items=notifications,
        total=total,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.get("/unread-count")
async def get_unread_count(
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.user_id)
    return {"unread_count": count}


@router.post("/mark-read")
async def mark_notifications_read(
    data: NotificationMarkRead,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.mark_read(data.notification_ids, current_user.user_id)
    return {"marked_read": count}


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = NotificationService(db)
    count = await service.mark_all_read(current_user.user_id)
    return {"marked_read": count}
