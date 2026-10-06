from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import _seed_repository
from test_findings_disappearance_scope import db_session as _db_session

from app.db.models import Export, Notification, Project, User
from app.schemas.exports import ExportCreate
from app.schemas.notifications import NotificationResponse
from app.services.exports import ExportService
from app.services.notifications import NotificationService

db_session = _db_session


@pytest.mark.asyncio
async def test_export_create_requires_project_membership(db_session):
    _, project_id = await _seed_repository(db_session)
    with pytest.raises(ValueError, match="Project not found"):
        await ExportService(db_session).create(
            UUID(project_id), ExportCreate(export_type="findings", format="csv"), uuid4()
        )
    assert (await db_session.execute(select(Export))).scalars().all() == []


@pytest.mark.asyncio
async def test_export_create_for_member(db_session):
    _, project_id = await _seed_repository(db_session)
    project = await db_session.get(Project, project_id)
    export = await ExportService(db_session).create(
        UUID(project_id), ExportCreate(export_type="findings", format="csv"), UUID(project.created_by_user_id)
    )
    assert export.project_id == project_id
    assert export.status == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize("recipient", ["outsider", "inactive", "member"])
async def test_notification_recipient_belongs_to_worker_organization(db_session, recipient):
    _, project_id = await _seed_repository(db_session)
    project = await db_session.get(Project, project_id)
    user_id = project.created_by_user_id
    organization_id = uuid4() if recipient == "outsider" else UUID(project.organization_id)
    if recipient == "inactive":
        user = await db_session.get(User, user_id)
        user.is_active = False
        await db_session.commit()
    service = NotificationService(db_session)
    if recipient == "member":
        notification = await service.create(
            UUID(user_id), "scan_completed", "Finished", organization_id=organization_id
        )
        assert notification.user_id == user_id
    else:
        with pytest.raises(ValueError, match="recipient"):
            await service.create(UUID(user_id), "scan_completed", "Finished", organization_id=organization_id)
        assert (await db_session.execute(select(Notification))).scalars().all() == []


@pytest.mark.asyncio
async def test_notification_link_survives_persistence_and_response_validation(db_session):
    _, project_id = await _seed_repository(db_session)
    project = await db_session.get(Project, project_id)
    notification = await NotificationService(db_session).create(
        UUID(project.created_by_user_id),
        "scan_completed",
        "Finished",
        link="/dashboard/organizations/project/scans/scan",
        metadata_json={"scan_id": "scan"},
        organization_id=UUID(project.organization_id),
    )
    response = NotificationResponse.model_validate(notification)
    assert response.link == "/dashboard/organizations/project/scans/scan"
    assert response.metadata_json["scan_id"] == "scan"
    assert notification.organization_id == project.organization_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "link", ["https://example.com", "//example.com", "/dashboard/\\example.com", "/dashboard/\nexample"]
)
@pytest.mark.parametrize("source", ["link", "metadata"])
async def test_notification_rejects_external_links(db_session, link, source):
    _, project_id = await _seed_repository(db_session)
    project = await db_session.get(Project, project_id)
    kwargs = {"link": link} if source == "link" else {"metadata_json": {"link": link}}
    with pytest.raises(ValueError, match="relative dashboard"):
        await NotificationService(db_session).create(
            UUID(project.created_by_user_id),
            "scan_completed",
            "Finished",
            organization_id=UUID(project.organization_id),
            **kwargs,
        )
    assert (await db_session.execute(select(Notification))).scalars().all() == []
