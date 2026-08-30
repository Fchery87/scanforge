import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.clients.queue import QueueClient
from app.contracts.queue import QueueJob


@pytest.mark.asyncio
async def test_clear_scan_queues_deletes_main_and_dlq():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-a",
    )
    client._command = AsyncMock(return_value={"result": 3})

    deleted = await client.clear_scan_queues()

    assert deleted == 3
    client._command.assert_awaited_once_with("DEL", client.scan_queue, client.dlq, client.retry_queue)


@pytest.mark.asyncio
async def test_dequeue_reclaims_a_stale_pending_scan_before_reading_new_messages():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-b",
    )
    job_json = json.dumps(
        {
            "job_type": "scan.repo.full",
            "job_id": "scan-123",
            "payload": {"scan_id": "scan-123"},
            "created_at": "2026-08-20T00:00:00+00:00",
        }
    )
    client._command = AsyncMock(
        side_effect=[
            {"result": "OK"},
            {"result": [1, "1740000000000-0", "1740000000000-0", [["worker-a", "1"]]]},
            {"result": ["0-0", [["1740000000000-0", ["job", job_json, "job_id", "scan-123"]]], []]},
        ]
    )

    delivery = await client.dequeue(timeout_seconds=5)

    assert delivery is not None
    assert delivery.job_id == "scan-123"
    assert delivery.stream_entry_id == "1740000000000-0"
    assert client._command.await_args_list[0].args == (
        "XGROUP",
        "CREATE",
        f"queue:scans:{organization_id}",
        "scanforge-workers",
        "0",
        "MKSTREAM",
    )
    assert client._command.await_args_list[1].args == (
        "XPENDING",
        f"queue:scans:{organization_id}",
        "scanforge-workers",
    )
    assert client._command.await_args_list[2].args == (
        "XAUTOCLAIM",
        f"queue:scans:{organization_id}",
        "scanforge-workers",
        "worker-b",
        client.visibility_timeout_ms,
        "0-0",
        "COUNT",
        1,
    )


@pytest.mark.asyncio
async def test_dead_letter_write_happens_before_original_entry_is_acknowledged_and_deleted():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-a",
    )
    client._command = AsyncMock(return_value={"result": 1})
    job = QueueJob.create("scan.secrets", {"scan_id": "scan-123"})
    job.stream_entry_id = "1740000000000-0"

    await client.move_to_dlq(job)

    assert [call.args[0] for call in client._command.await_args_list] == ["XADD", "XACK", "XDEL"]
    assert client._command.await_args_list[0].args[1] == f"queue:scans:{organization_id}:dlq"


@pytest.mark.asyncio
async def test_second_consumer_reclaims_the_same_scan_after_first_consumer_crashes_before_ack():
    organization_id = uuid4()
    job_json = json.dumps(
        {
            "job_type": "scan.repo.full",
            "job_id": "scan-123",
            "payload": {"scan_id": "scan-123"},
            "created_at": "2026-08-20T00:00:00+00:00",
        }
    )
    first = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-first",
    )
    first._command = AsyncMock(
        side_effect=[
            {"result": "OK"},
            {"result": [0, None, None, []]},
            {"result": ["0-0", [], []]},
            {"result": [[f"queue:scans:{organization_id}", [["1740000000000-0", ["job", job_json]]]]]},
        ]
    )
    delivered = await first.dequeue()

    second = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-second",
    )
    second._command = AsyncMock(
        side_effect=[
            {"result": "BUSYGROUP Consumer Group name already exists"},
            {"result": [1, "1740000000000-0", "1740000000000-0", [["worker-first", "1"]]]},
            {"result": ["0-0", [["1740000000000-0", ["job", job_json]]], []]},
        ]
    )
    reclaimed = await second.dequeue()

    assert delivered is not None
    assert reclaimed is not None
    assert reclaimed.payload["scan_id"] == delivered.payload["scan_id"] == "scan-123"
    assert first._command.await_args_list[3].args == (
        "XREADGROUP",
        "GROUP",
        "scanforge-workers",
        "worker-first",
        "COUNT",
        1,
        "BLOCK",
        5000,
        "STREAMS",
        f"queue:scans:{organization_id}",
        ">",
    )
    assert second._command.await_args_list[1].args[0] == "XPENDING"
    assert second._command.await_args_list[2].args[0] == "XAUTOCLAIM"


@pytest.mark.asyncio
async def test_requeue_stages_a_durable_delayed_successor_before_removing_pending_entry():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-a",
    )
    client._command = AsyncMock(return_value={"result": 1})
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})
    job.stream_entry_id = "1740000000000-0"
    before = datetime.now(UTC).timestamp()

    await client.requeue(job, delay_seconds=30)

    commands = client._command.await_args_list
    assert [call.args[0] for call in commands] == ["ZADD", "XACK", "XDEL"]
    assert commands[0].args[1] == f"queue:scans:{organization_id}:retry"
    assert float(commands[0].args[2]) >= before + 30
    assert commands[0].args[3] == job.model_dump_json()


@pytest.mark.asyncio
async def test_due_retry_is_promoted_to_the_scan_stream_without_deleting_recovery_state_first():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-a",
    )
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})
    job_json = job.model_dump_json()
    client._command = AsyncMock(
        side_effect=[
            {"result": [job_json]},
            {"result": "1740000030000-0"},
        ]
    )

    promoted = await client.promote_due_retries()

    assert promoted == 1
    commands = client._command.await_args_list
    assert [call.args[0] for call in commands] == ["ZRANGEBYSCORE", "EVAL"]
    assert commands[0].args[1] == f"queue:scans:{organization_id}:retry"
    assert commands[1].args == (
        "EVAL",
        client.PROMOTE_RETRY_SCRIPT,
        2,
        client.retry_queue,
        client.scan_queue,
        job_json,
        job.job_id,
    )


@pytest.mark.asyncio
async def test_atomic_retry_promotion_cannot_duplicate_a_delivery_after_a_lost_response():
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=uuid4(),
        consumer_name="worker-a",
    )
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-123"})
    job_json = job.model_dump_json()
    client._command = AsyncMock(
        side_effect=[
            {"result": [job_json]},
            {"result": "1740000030000-0"},
            {"result": [job_json]},
            {"result": None},
        ]
    )

    first_promotion = await client.promote_due_retries()
    second_promotion = await client.promote_due_retries()

    assert (first_promotion, second_promotion) == (1, 0)
    assert [call.args[0] for call in client._command.await_args_list] == [
        "ZRANGEBYSCORE",
        "EVAL",
        "ZRANGEBYSCORE",
        "EVAL",
    ]


@pytest.mark.asyncio
async def test_malformed_delayed_retry_is_quarantined_and_does_not_wedge_promotion():
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=uuid4(),
        consumer_name="worker-a",
    )
    malformed_json = "{not-json"
    client._command = AsyncMock(side_effect=[{"result": [malformed_json]}, {"result": "1740000030000-0"}])

    promoted = await client.promote_due_retries()

    assert promoted == 0
    assert client._command.await_args_list[1].args == (
        "EVAL",
        client.QUARANTINE_RETRY_SCRIPT,
        2,
        client.retry_queue,
        client.dlq,
        malformed_json,
        "malformed_retry",
    )


@pytest.mark.asyncio
async def test_malformed_stream_entry_is_dead_lettered_before_its_pending_entry_is_removed():
    organization_id = uuid4()
    client = QueueClient(
        redis_url="https://redis.example",
        redis_token="token",
        organization_id=organization_id,
        consumer_name="worker-a",
    )
    malformed_entry = ["1740000000000-0", ["job", "{not-json"]]
    client._command = AsyncMock(
        side_effect=[
            {"result": "OK"},
            {"result": [0, None, None, []]},
            {"result": ["0-0", [], []]},
            {"result": [[f"queue:scans:{organization_id}", [malformed_entry]]]},
            {"result": "1740000030000-0"},
            {"result": 1},
            {"result": 1},
        ]
    )

    delivery = await client.dequeue()

    assert delivery is None
    commands = client._command.await_args_list
    assert [call.args[0] for call in commands[-3:]] == ["XADD", "XACK", "XDEL"]
    assert commands[-3].args[1] == f"queue:scans:{organization_id}:dlq"
    assert commands[-2].args == ("XACK", f"queue:scans:{organization_id}", "scanforge-workers", "1740000000000-0")
    assert commands[-1].args == ("XDEL", f"queue:scans:{organization_id}", "1740000000000-0")
