from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.exports import ExportAuthorizationError, ExportService


@pytest.mark.asyncio
async def test_create_export_persists_title():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())
    captured = {}

    db = AsyncMock()
    db.get.return_value = project
    db.add = Mock(side_effect=lambda export: captured.setdefault("export", export))

    service = ExportService(db)

    result = await service.create(
        project_id,
        SimpleNamespace(
            export_type="findings",
            format="csv",
            filters=None,
            title="Q1 report",
        ),
        user_id,
    )

    assert result is captured["export"]
    assert captured["export"].title == "Q1 report"


@pytest.mark.asyncio
async def test_create_export_rejects_non_member_of_target_org():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())

    db = AsyncMock()
    db.get.return_value = project
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = None
    db.execute.return_value = membership_result

    service = ExportService(db)

    with pytest.raises(ExportAuthorizationError):
        await service.create(
            project_id,
            SimpleNamespace(
                export_type="findings",
                format="csv",
                filters=None,
                title="Q1 report",
            ),
            user_id,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_export_allows_member_of_target_org():
    project_id = uuid4()
    user_id = uuid4()
    project = SimpleNamespace(id=project_id, organization_id=uuid4())
    captured = {}

    db = AsyncMock()
    db.get.return_value = project
    membership_result = Mock()
    membership_result.scalar_one_or_none.return_value = SimpleNamespace(id=uuid4())
    db.execute.return_value = membership_result
    db.add = Mock(side_effect=lambda export: captured.setdefault("export", export))

    service = ExportService(db)

    result = await service.create(
        project_id,
        SimpleNamespace(
            export_type="findings",
            format="csv",
            filters=None,
            title="Q1 report",
        ),
        user_id,
    )

    assert result is captured["export"]
    assert captured["export"].project_id == str(project_id)
    assert captured["export"].requested_by_user_id == str(user_id)
