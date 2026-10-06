from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification, OrganizationMember, User


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        body: str | None = None,
        link: str | None = None,
        metadata_json: dict | None = None,
        *,
        organization_id: UUID,
    ) -> Notification:
        membership = await self.db.execute(
            select(OrganizationMember)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                OrganizationMember.organization_id == str(organization_id),
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
            )
        )
        if membership.scalar_one_or_none() is None:
            raise ValueError("Notification recipient not found in this organization")

        metadata = dict(metadata_json or {})
        effective_link = link if link is not None else metadata.get("link")
        if effective_link is not None:
            if (
                not isinstance(effective_link, str)
                or not effective_link.startswith("/dashboard/")
                or "\\" in effective_link
                or any(character < " " for character in effective_link)
            ):
                raise ValueError("Notification link must be a relative dashboard path")
            metadata["link"] = effective_link
        notification = Notification(
            user_id=str(user_id),
            organization_id=str(organization_id),
            notification_type=notification_type,
            title=title,
            body=body,
            metadata_json=metadata or None,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        return notification

    async def list_for_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        base_query = select(Notification).where(Notification.user_id == str(user_id))

        if unread_only:
            base_query = base_query.where(Notification.is_read.is_(False))

        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        result = await self.db.execute(base_query.order_by(Notification.created_at.desc()).offset(skip).limit(limit))

        return list(result.scalars().all()), total

    async def get_unread_count(self, user_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == str(user_id),
                Notification.is_read.is_(False),
            )
        )
        return result.scalar_one() or 0

    async def mark_read(
        self,
        notification_ids: list[UUID],
        user_id: UUID,
    ) -> int:
        count = 0
        for nid in notification_ids:
            notif = await self.db.get(Notification, str(nid))
            if notif and notif.user_id == str(user_id) and not notif.is_read:
                notif.is_read = True
                count += 1

        if count > 0:
            await self.db.commit()
        return count

    async def mark_all_read(self, user_id: UUID) -> int:
        result = await self.db.execute(
            select(Notification).where(
                Notification.user_id == str(user_id),
                Notification.is_read.is_(False),
            )
        )
        notifications = result.scalars().all()
        for notif in notifications:
            notif.is_read = True

        await self.db.commit()
        return len(notifications)
