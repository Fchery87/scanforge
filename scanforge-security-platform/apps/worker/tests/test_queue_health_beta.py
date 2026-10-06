from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.clients.queue import QueueClient


def client():
    return QueueClient("https://redis.example", "secret", organization_id="org", consumer_name="worker")


@pytest.mark.asyncio
async def test_queue_transport_failure_is_not_an_empty_poll():
    queue = client()
    queue._command = AsyncMock(side_effect=httpx.ConnectError("unavailable"))
    with pytest.raises(httpx.HTTPError):
        await queue.dequeue()


@pytest.mark.asyncio
async def test_redis_command_error_is_not_a_successful_write():
    response = httpx.Response(200, json={"error": "NOAUTH Authentication required"},
                              request=httpx.Request("POST", "https://redis.example"))
    with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=response)):
        with pytest.raises(RuntimeError, match="Redis command failed"):
            await client().get_queue_length()


def test_crash_reclaim_deadline_is_below_beta_recovery_budget():
    assert client().visibility_timeout_ms <= 5 * 60 * 1000


@pytest.mark.asyncio
async def test_active_worker_renews_only_its_owned_pending_delivery():
    from app.contracts.queue import QueueJob

    queue = client()
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan"})
    job.stream_entry_id = "1-0"
    queue._command = AsyncMock(return_value={"result": 0})
    assert await queue.heartbeat(job) is False
    queue._command.return_value = {"result": 1}
    assert await queue.heartbeat(job) is True
    args = queue._command.await_args.args
    assert args[-3:] == (queue.CONSUMER_GROUP, queue.consumer_name, "1-0")


@pytest.mark.asyncio
async def test_oldest_job_age_is_zero_for_empty_stream_and_measures_queued_work():
    from datetime import UTC, datetime
    queue = client()
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    queue._ensure_consumer_group = AsyncMock()
    group = {"result": [{"name": queue.CONSUMER_GROUP, "last-delivered-id": "1-0"}]}
    queue._command = AsyncMock(side_effect=[group, {"result": []}, group,
                                          {"result": [[f"{now_ms - 360000}-0", []]]}])
    assert await queue.get_oldest_job_age_seconds() == 0
    assert 360 <= await queue.get_oldest_job_age_seconds() < 365
