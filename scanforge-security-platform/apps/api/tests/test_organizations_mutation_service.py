from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.organizations import OrganizationUpdate
from app.services.organizations import OrganizationService


@pytest.mark.asyncio
async def test_update_organization_returns_none_when_user_cannot_access_org():
    org_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = OrganizationService(db)
    service.get_by_id = AsyncMock(return_value=None)

    updated = await service.update(org_id, OrganizationUpdate(name="Renamed"), user_id=user_id)

    assert updated is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_organization_returns_false_when_user_cannot_access_org():
    org_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = OrganizationService(db)
    service.get_by_id = AsyncMock(return_value=None)

    deleted = await service.delete(org_id, user_id=user_id)

    assert deleted is False
    db.commit.assert_not_awaited()
