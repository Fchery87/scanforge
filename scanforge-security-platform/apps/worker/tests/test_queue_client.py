from unittest.mock import AsyncMock

import pytest

from app.clients.queue import QueueClient


@pytest.mark.asyncio
async def test_clear_scan_queues_deletes_main_and_dlq():
    client = QueueClient(redis_url="https://redis.example", redis_token="token")
    client._command = AsyncMock(return_value={"result": 3})

    deleted = await client.clear_scan_queues()

    assert deleted == 3
    client._command.assert_awaited_once_with("DEL", client.SCAN_QUEUE, client.DLQ, client.PROCESSING_SET)
