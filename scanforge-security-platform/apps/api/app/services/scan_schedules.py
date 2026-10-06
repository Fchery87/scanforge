from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import MemberRole
from app.db.models import OrganizationMember, Project, Repository, ScanSchedule, User
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
        repo = await get_repository_for_user(self.db, str(repository_id), str(user_id))
        if not repo:
            raise ValueError("Repository not found")

        await self._require_mutation_access(repo, user_id)
        self._validate_frequency(data.schedule_type, data.cron_expression)

        schedule = ScanSchedule(
            repository_id=str(repository_id),
            schedule_type=data.schedule_type,
            cron_expression=data.cron_expression,
            scan_type=data.scan_type,
            is_active=data.is_active,
            created_by_user_id=str(user_id),
        )

        schedule.next_run_at = self._next_run_at(schedule.schedule_type, schedule.is_active)

        self.db.add(schedule)
        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def list_for_repository(
        self,
        repository_id: UUID,
        user_id: UUID,
    ) -> list["ScanSchedule"]:
        repo = await get_repository_for_user(self.db, str(repository_id), str(user_id))
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

        repo = await get_repository_for_user(self.db, str(schedule.repository_id), str(user_id))
        if not repo:
            return None

        return schedule

    async def update(
        self,
        schedule_id: UUID,
        data: "ScanScheduleUpdate",
        user_id: UUID,
    ) -> Optional["ScanSchedule"]:
        schedule = await self.get_by_id(schedule_id, user_id)
        if not schedule:
            return None

        repo = await self.db.get(Repository, schedule.repository_id)
        await self._require_mutation_access(repo, user_id)
        update_data = data.model_dump(exclude_unset=True)
        for field in ("schedule_type", "scan_type", "is_active"):
            if field in update_data and update_data[field] is None:
                raise ValueError(f"{field} cannot be null")
        self._validate_frequency(
            update_data.get("schedule_type", schedule.schedule_type),
            update_data.get("cron_expression", schedule.cron_expression),
        )
        for field, value in update_data.items():
            setattr(schedule, field, value)
        if "schedule_type" in update_data or "is_active" in update_data:
            schedule.next_run_at = self._next_run_at(schedule.schedule_type, schedule.is_active)

        await self.db.commit()
        await self.db.refresh(schedule)
        return schedule

    async def delete(self, schedule_id: UUID, user_id: UUID) -> bool:
        schedule = await self.get_by_id(schedule_id, user_id)
        if not schedule:
            return False

        repo = await self.db.get(Repository, schedule.repository_id)
        await self._require_mutation_access(repo, user_id)
        await self.db.delete(schedule)
        await self.db.commit()
        return True

    async def _require_mutation_access(self, repo: Repository, user_id: UUID) -> None:
        result = await self.db.execute(
            select(OrganizationMember)
            .join(Project, Project.organization_id == OrganizationMember.organization_id)
            .join(User, User.id == OrganizationMember.user_id)
            .where(
                Project.id == repo.project_id,
                OrganizationMember.user_id == str(user_id),
                User.is_active.is_(True),
            )
        )
        member = result.scalar_one_or_none()
        if member is None or member.role not in {
            MemberRole.OWNER,
            MemberRole.ADMIN,
            MemberRole.SECURITY_REVIEWER,
            MemberRole.DEVELOPER,
        }:
            raise PermissionError("Insufficient permission to modify scan schedules")

    @staticmethod
    def _validate_frequency(schedule_type: str, cron_expression: str | None) -> None:
        if schedule_type not in {"daily", "weekly", "on_push"}:
            raise ValueError("Unsupported schedule frequency")
        if cron_expression is not None:
            raise ValueError("Custom cron expressions are not supported")

    @staticmethod
    def _next_run_at(schedule_type: str, is_active: bool) -> datetime | None:
        if not is_active or schedule_type == "on_push":
            return None
        interval = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}[schedule_type]
        return datetime.now(UTC).replace(hour=2, minute=0, second=0, microsecond=0) + interval

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
