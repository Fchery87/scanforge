from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.exports import ExportService


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
