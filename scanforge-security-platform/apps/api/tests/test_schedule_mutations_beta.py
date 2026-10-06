from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import _seed_repository
from test_findings_disappearance_scope import db_session as _db_session

from app.db.enums import MemberRole
from app.db.models import OrganizationMember, Project, ScanSchedule
from app.schemas.scan_schedules import ScanScheduleCreate, ScanScheduleUpdate
from app.services.scan_schedules import ScanScheduleService

db_session = _db_session


async def _context(db, role=MemberRole.OWNER):
    repository_id, project_id = await _seed_repository(db)
    project = await db.get(Project, project_id)
    member = (await db.execute(select(OrganizationMember))).scalar_one()
    member.role = role
    await db.commit()
    return UUID(repository_id), UUID(project.created_by_user_id)


async def _create_schedule(db, service, repo_id, user_id):
    schedule = await service.create(repo_id, ScanScheduleCreate(schedule_type="daily"), user_id)
    schedule.id = str(UUID(str(schedule.id)))
    await db.commit()
    await db.refresh(schedule)
    return schedule


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update", "delete"])
async def test_viewer_cannot_mutate_schedules(db_session, operation):
    repo_id, user_id = await _context(db_session)
    service = ScanScheduleService(db_session)
    schedule = await _create_schedule(db_session, service, repo_id, user_id)
    member = (await db_session.execute(select(OrganizationMember))).scalar_one()
    member.role = MemberRole.VIEWER
    await db_session.commit()
    actions = {
        "create": lambda: service.create(repo_id, ScanScheduleCreate(schedule_type="weekly"), user_id),
        "update": lambda: service.update(UUID(schedule.id), ScanScheduleUpdate(is_active=False), user_id),
        "delete": lambda: service.delete(UUID(schedule.id), user_id),
    }
    with pytest.raises(PermissionError):
        await actions[operation]()
    persisted = (await db_session.execute(select(ScanSchedule))).scalar_one()
    assert persisted.is_active
    assert persisted.schedule_type == "daily"


@pytest.mark.asyncio
async def test_schedule_updates_recalculate_due_time(db_session):
    repo_id, user_id = await _context(db_session)
    service = ScanScheduleService(db_session)
    schedule = await _create_schedule(db_session, service, repo_id, user_id)
    old_due = schedule.next_run_at
    await service.update(UUID(schedule.id), ScanScheduleUpdate(schedule_type="weekly"), user_id)
    assert (schedule.next_run_at - old_due).days == 6
    await service.update(UUID(schedule.id), ScanScheduleUpdate(is_active=False), user_id)
    assert schedule.next_run_at is None
    await service.update(UUID(schedule.id), ScanScheduleUpdate(is_active=True), user_id)
    assert schedule.next_run_at.replace(tzinfo=UTC) > datetime.now(UTC)
    await service.update(UUID(schedule.id), ScanScheduleUpdate(schedule_type="on_push"), user_id)
    assert schedule.next_run_at is None


@pytest.mark.asyncio
async def test_unsupported_cron_rejected_without_schedule_write(db_session):
    repo_id, user_id = await _context(db_session)
    service = ScanScheduleService(db_session)
    with pytest.raises(ValueError, match="cron"):
        await service.create(repo_id, ScanScheduleCreate(schedule_type="daily", cron_expression="*/5 * * * *"), user_id)
    assert (await db_session.execute(select(ScanSchedule))).scalars().all() == []
    schedule = await _create_schedule(db_session, service, repo_id, user_id)
    with pytest.raises(ValueError, match="cron"):
        await service.update(UUID(schedule.id), ScanScheduleUpdate(cron_expression="*/5 * * * *"), user_id)
    assert schedule.cron_expression is None


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [MemberRole.ADMIN, MemberRole.SECURITY_REVIEWER, MemberRole.DEVELOPER])
async def test_non_viewer_members_can_mutate_schedules(db_session, role):
    repo_id, user_id = await _context(db_session, role)
    service = ScanScheduleService(db_session)
    schedule = await _create_schedule(db_session, service, repo_id, user_id)
    updated = await service.update(UUID(schedule.id), ScanScheduleUpdate(scan_type="dependencies"), user_id)
    assert updated.scan_type == "dependencies"
    assert await service.delete(UUID(schedule.id), user_id)
    assert (await db_session.execute(select(ScanSchedule))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["schedule_type", "scan_type", "is_active"])
async def test_schedule_patch_rejects_null_required_fields(db_session, field):
    repo_id, user_id = await _context(db_session)
    service = ScanScheduleService(db_session)
    schedule = await _create_schedule(db_session, service, repo_id, user_id)
    with pytest.raises(ValueError, match="cannot be null"):
        await service.update(UUID(schedule.id), ScanScheduleUpdate(**{field: None}), user_id)
    assert schedule.schedule_type == "daily"
    assert schedule.scan_type == "full"
    assert schedule.is_active
