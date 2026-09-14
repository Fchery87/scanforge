from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.notifications import NotificationAuthorizationError, NotificationService


@pytest.mark.asyncio
async def test_create_notification_rejects_caller_outside_target_org():
    recipient_id = uuid4()
    caller_organization_id = uuid4()
    organization_id = uuid4()

    db = AsyncMock()
    service = NotificationService(db)

    with pytest.raises(NotificationAuthorizationError) as excinfo:
        await service.create(
            recipient_id,
            "scan_completed",
            "Scan finished",
            caller_organization_id=caller_organization_id,
            organization_id=organization_id,
        )

    assert NotificationAuthorizationError.code == "notification_org_membership_required"
    assert "member" in str(excinfo.value)
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_rejects_recipient_outside_target_org():
    recipient_id = uuid4()
    organization_id = uuid4()

    db = AsyncMock()
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = None
    db.execute.return_value = membership_result

    service = NotificationService(db)

    with pytest.raises(NotificationAuthorizationError):
        await service.create(
            recipient_id,
            "scan_completed",
            "Scan finished",
            caller_organization_id=organization_id,
            organization_id=organization_id,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_allows_member_caller_and_recipient():
    recipient_id = uuid4()
    organization_id = uuid4()
    captured = {}

    db = AsyncMock()
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4())
    db.execute.return_value = membership_result
    db.add = Mock(side_effect=lambda notification: captured.setdefault("notification", notification))

    service = NotificationService(db)

    result = await service.create(
        recipient_id,
        "scan_completed",
        "Scan finished",
        body="Findings are ready",
        caller_organization_id=organization_id,
        organization_id=organization_id,
    )

    assert result is captured["notification"]
    assert captured["notification"].user_id == str(recipient_id)
    assert captured["notification"].organization_id == str(organization_id)
