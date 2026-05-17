from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScanSchedule
from app.schemas.scan_schedules import ScanScheduleCreate, ScanScheduleUpdate
from app.services.access_policies import get_repository_for_user


class ScanScheduleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        repository_id: UUID,
        data: "ScanScheduleCreate",
        user_id: UUID,
    ) -> "ScanSchedule":
        repo = await get_repository_for_user(self.db, repository_id, user_id)
        if not repo:
            raise ValueError("Repository not found")

        schedule = ScanSchedule(
            repository_id=str(repository_id),
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
            scan_type=data.scan_type,
            is_active=data.is_active,
            created_by_user_id=str(user_id),
        )

        if data.schedule_type == "daily":
            schedule.next_run_at = datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
        elif data.schedule_type == "weekly":
            schedule.next_run_at = datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(
                days=7
            )

        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def list_for_repository(
        self,
        repository_id: UUID,
        user_id: UUID,
    ) -> list["ScanSchedule"]:
        repo = await get_repository_for_user(self.db, repository_id, user_id)
        if not repo:
            return []

        result = await self.db.execute(
            select(ScanSchedule)
            .where(ScanSchedule.repository_id == str(repository_id))
            .order_by(ScanSchedule.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        schedule_id: UUID,
        user_id: UUID,
    ) -> Optional["ScanSchedule"]:
        schedule = await self.db.get(ScanSchedule, str(schedule_id))
        if not schedule:
            return None

        repo = await get_repository_for_user(self.db, UUID(schedule.repository_id), user_id)
        if not repo:
            return None

        return schedule

    async def update(
        self,
        schedule_id: UUID,
        data: "ScanScheduleUpdate",
        user_id: UUID | None = None,
    ) -> Optional["ScanSchedule"]:
        if user_id is not None:
            schedule = await self.get_by_id(schedule_id, user_id)
        else:
            schedule = await self.db.get(ScanSchedule, str(schedule_id))
        if not schedule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)

        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def delete(self, schedule_id: UUID, user_id: UUID | None = None) -> bool:
        if user_id is not None:
            schedule = await self.get_by_id(schedule_id, user_id)
        else:
            schedule = await self.db.get(ScanSchedule, str(schedule_id))
        if not schedule:
            return False

        await self.db.delete(schedule)
        await self.db.commit()
        return True

    async def get_due_schedules(self, limit: int = 100) -> list["ScanSchedule"]:
        now = datetime.now(UTC)
        result = await self.db.execute(
            select(ScanSchedule)
            .where(ScanSchedule.is_active.is_(True))
            .where(ScanSchedule.next_run_at <= now)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_run(
        self,
        schedule_id: UUID,
    ) -> "ScanSchedule":
        schedule = await self.db.get(ScanSchedule, str(schedule_id))
        if not schedule:
            raise ValueError("Schedule not found")

        schedule.last_run_at = datetime.now(UTC)

        if schedule.schedule_type == "daily":
            schedule.next_run_at = schedule.last_run_at + timedelta(days=1)
        elif schedule.schedule_type == "weekly":
            schedule.next_run_at = schedule.last_run_at + timedelta(weeks=1)
        elif schedule.schedule_type == "on_push":
            schedule.next_run_at = None

        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule
