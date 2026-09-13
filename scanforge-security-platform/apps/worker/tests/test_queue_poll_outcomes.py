"""R09: queue poll outcomes must be observable, never folded into "empty".

These cases emulate the Upstash REST surface with an in-memory fake and with
httpx error injection.  They prove client classification and bounded backoff.
Real-Redis stream semantics are covered separately by
test_redis_stream_recovery_integration.py against a live redis-server.
"""
from __future__ import annotations

import httpx
import pytest

from app.clients.queue import QueueClient, QueuePollStatus
from app.contracts.queue import QueueJob

pytestmark = pytest.mark.asyncio


def _client() -> QueueClient:
    return QueueClient(
        redis_url="http://upstash.test",
        redis_token="token",
        organization_id="org-1",
        consumer_name="consumer-1",
    )


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://upstash.test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"HTTP {status_code}", request=request, response=response)


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (_http_status_error(401), QueuePollStatus.UNAUTHORIZED),
        (_http_status_error(403), QueuePollStatus.UNAUTHORIZED),
        (_http_status_error(429), QueuePollStatus.RATE_LIMITED),
        (_http_status_error(500), QueuePollStatus.UNAVAILABLE),
        (httpx.ConnectError("connection refused"), QueuePollStatus.UNAVAILABLE),
        (httpx.ReadTimeout("timed out"), QueuePollStatus.UNAVAILABLE),
    ],
)
async def test_outage_polls_are_explicitly_classified(raised, expected, monkeypatch):
    client = _client()

    async def fail(*_args, **_kwargs):
        raise raised

    monkeypatch.setattr(client, "_ensure_consumer_group", fail)
    job, status = await client.dequeue_with_status(timeout_seconds=1)
    assert job is None
    assert status is expected


async def test_empty_poll_is_distinct_from_outage(monkeypatch):
    client = _client()

    async def empty_command(*_args, **_kwargs):
        return {"result": None}

    async def group_ok(*_args, **_kwargs):
        return None

    async def no_reclaim(*_args, **_kwargs):
        return None

    monkeypatch.setattr(client, "_command", empty_command)
    monkeypatch.setattr(client, "_ensure_consumer_group", group_ok)
    monkeypatch.setattr(client, "_reclaim_one_pending_job", no_reclaim)
    job, status = await client.dequeue_with_status(timeout_seconds=0)
    assert job is None
    assert status is QueuePollStatus.EMPTY


async def test_delivered_poll_reports_delivered(monkeypatch):
    client = _client()
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-1"})

    async def group_ok(*_args, **_kwargs):
        return None

    async def no_reclaim(*_args, **_kwargs):
        return None

    async def fake_read(*_args, **_kwargs):
        entry_id = "1-1"
        job.stream_entry_id = entry_id
        return {"result": [[client.scan_queue, [[entry_id, ["job", job.model_dump_json()]]]]]}

    monkeypatch.setattr(client, "_ensure_consumer_group", group_ok)
    monkeypatch.setattr(client, "_reclaim_one_pending_job", no_reclaim)
    monkeypatch.setattr(client, "_command", fake_read)
    got, status = await client.dequeue_with_status(timeout_seconds=0)
    assert status is QueuePollStatus.DELIVERED
    assert got is not None and got.job_id == job.job_id


async def test_backoff_is_bounded_and_resets(monkeypatch):
    client = _client()

    async def fail(*_args, **_kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(client, "_ensure_consumer_group", fail)
    delays = []
    for _ in range(7):
        _job, status = await client.dequeue_with_status(timeout_seconds=0)
        assert status is QueuePollStatus.UNAVAILABLE
        delays.append(client.backoff_seconds)
    # 1, 2, 4, 8, 16, then capped at 30 s.
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0]

    client._note_success()
    assert client.backoff_seconds == 0.0


async def test_requeue_and_dlq_write_before_acknowledge(monkeypatch):
    """No message loss: the successor/DLQ copy is durable before the source
    pending entry is acknowledged and deleted (R03 recovery policy)."""
    client = _client()
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-1"})
    job.stream_entry_id = "1-2"
    calls: list[tuple] = []

    async def record(*args, **_kwargs):
        calls.append(args)
        return {"result": "OK"}

    monkeypatch.setattr(client, "_command", record)

    await client.requeue(job, delay_seconds=60)
    requeue_ops = [c[0] for c in calls]
    assert requeue_ops.index("ZADD") < requeue_ops.index("XACK") < requeue_ops.index("XDEL")

    calls.clear()
    await client.move_to_dlq(job)
    dlq_ops = [c[0] for c in calls]
    assert dlq_ops.index("XADD") < dlq_ops.index("XACK") < dlq_ops.index("XDEL")
