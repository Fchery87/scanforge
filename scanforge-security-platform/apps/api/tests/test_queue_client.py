import json
from unittest.mock import ANY, AsyncMock
from uuid import uuid4

import pytest

from app.clients.queue import QueueClient


@pytest.mark.asyncio
async def test_enqueue_rejects_unimplemented_delayed_jobs():
    queue = QueueClient(redis_url="https://example.upstash.io", redis_token="token")

    with pytest.raises(NotImplementedError, match="Delayed jobs are not implemented"):
        await queue.enqueue(
            "scan.repo.full",
            {"scan_id": "123"},
            organization_id=uuid4(),
            delay_seconds=30,
        )


@pytest.mark.asyncio
async def test_enqueue_writes_an_organization_stream_with_the_scan_id_as_job_id():
    organization_id = uuid4()
    queue = QueueClient(redis_url="https://example.upstash.io", redis_token="token")
    queue._command = AsyncMock(
        side_effect=[
            {"result": "OK"},
            {"result": "1740000000000-0"},
        ]
    )

    job_id = await queue.enqueue(
        "scan.repo.full",
        {"scan_id": "scan-123"},
        organization_id=organization_id,
    )

    assert job_id == "scan-123"
    command = queue._command.await_args.args
    assert command[0] == "EVAL"
    assert command[2:5] == (
        2, f"queue:scans:{organization_id}:dedupe:scan-123", f"queue:scans:{organization_id}",
    )
    assert json.loads(command[5]) == {
        "job_type": "scan.repo.full", "job_id": "scan-123", "payload": {"scan_id": "scan-123"}, "created_at": ANY,
    }
    assert command[6] == "scan-123"
    queue._command.assert_awaited_once()



@pytest.mark.asyncio
async def test_replayed_enqueue_does_not_add_a_duplicate_stream_entry():
    organization_id = uuid4()
    queue = QueueClient(redis_url="https://example.upstash.io", redis_token="token")
    queue._command = AsyncMock(return_value={"result": None})

    job_id = await queue.enqueue(
        "scan.repo.full",
        {"scan_id": "scan-123"},
        organization_id=organization_id,
    )

    assert job_id == "scan-123"
    queue._command.assert_awaited_once()
