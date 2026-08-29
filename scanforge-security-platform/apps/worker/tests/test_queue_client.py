from unittest.mock import AsyncMock

import pytest

from app.clients.queue import QueueClient
from app.contracts.queue import QueueJob


@pytest.mark.asyncio
async def test_dequeue_reclaims_stale_pending_job_before_reading_new_message():
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id="org-123",
        consumer_name="consumer-2",
    )
    stale = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})
    stale.stream_id = "1-0"
    client.reclaim_stale_jobs = AsyncMock(return_value=[stale])
    client.ensure_group = AsyncMock()
    client._command = AsyncMock()

    job = await client.dequeue()

    assert job is stale
    client.reclaim_stale_jobs.assert_awaited_once_with()
    client.ensure_group.assert_not_awaited()
    client._command.assert_not_awaited()


@pytest.mark.asyncio
async def test_transfer_to_dlq_appends_before_acknowledging_source():
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id="org-123",
        consumer_name="consumer-1",
    )
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})
    job.stream_id = "1-0"
    client._command = AsyncMock(side_effect=[{"result": "2-0"}, {"result": 1}, {"result": 1}])

    await client.transfer_to_dlq(job)

    assert [call.args[0] for call in client._command.await_args_list] == ["XADD", "XACK", "XDEL"]


@pytest.mark.asyncio
async def test_clear_scan_queues_deletes_main_and_dlq():
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id="org-123",
        consumer_name="consumer-1",
    )

    client._command = AsyncMock(return_value={"result": 3})

    deleted = await client.clear_scan_queues()

    assert deleted == 3
    client._command.assert_awaited_once_with("DEL", client.stream, client.dlq)
