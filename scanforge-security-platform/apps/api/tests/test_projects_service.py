from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.schemas.projects import ProjectUpdate
from app.services.projects import ProjectService


@pytest.mark.asyncio
async def test_update_project_returns_none_when_user_cannot_access_project():
    project_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = ProjectService(db)
    service.get_by_id = AsyncMock(return_value=None)

    updated = await service.update(project_id, ProjectUpdate(name="Renamed"), user_id=user_id)

    assert updated is None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_project_returns_false_when_user_cannot_access_project():
    project_id = uuid4()
    user_id = uuid4()

    db = AsyncMock()
    service = ProjectService(db)
    service.get_by_id = AsyncMock(return_value=None)

    deleted = await service.delete(project_id, user_id=user_id)

    assert deleted is False
    db.commit.assert_not_awaited()
