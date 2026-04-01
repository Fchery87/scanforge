from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.db.enums import ScanStatus as ScanStatusEnum
from app.services.scans import ScanService


@pytest.mark.asyncio
async def test_delete_scan_allows_non_completed_statuses():
    scan_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(id=scan_id, status=ScanStatusEnum.FAILED)

    db = AsyncMock()
    db.delete = AsyncMock()
    service = ScanService(db)
    service.get_by_id = AsyncMock(return_value=scan)

    deleted = await service.delete(scan_id, user_id)

    assert deleted is scan
    db.delete.assert_awaited_once_with(scan)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_scan_rejects_completed_scans():
    scan_id = uuid4()
    user_id = uuid4()
    scan = SimpleNamespace(id=scan_id, status=ScanStatusEnum.COMPLETED)

    db = AsyncMock()
    db.delete = Mock()
    service = ScanService(db)
    service.get_by_id = AsyncMock(return_value=scan)

    with pytest.raises(ValueError, match="completed scans"):
        await service.delete(scan_id, user_id)

    db.delete.assert_not_called()
    db.commit.assert_not_awaited()
