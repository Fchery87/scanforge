import os
from uuid import uuid4

import pytest
import redis.asyncio as redis
from redis.exceptions import ResponseError

from app.clients.queue import QueueClient
from app.contracts.queue import QueueJob

pytestmark = pytest.mark.skipif(not os.environ.get("REDIS_URL"), reason="REDIS_URL is required")


@pytest.mark.asyncio
async def test_native_pending_recovery_ack_and_ownership_checked_heartbeat():
    native = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    organization_id = f"beta-test-{uuid4()}"
    first = QueueClient("https://unused.example", "unused", organization_id=organization_id, consumer_name="first")
    second = QueueClient("https://unused.example", "unused", organization_id=organization_id, consumer_name="second")

    async def command(*args):
        try:
            return {"result": await native.execute_command(*args)}
        except ResponseError as exc:
            raise RuntimeError(f"Redis command failed: {exc}") from exc

    first._command = second._command = command
    second.visibility_timeout_ms = 0
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-fixture"})
    try:
        await native.xadd(first.scan_queue, {"job": job.model_dump_json(), "job_id": job.job_id})
        claimed = await first.dequeue(timeout_seconds=1)
        assert claimed.job_id == "scan-fixture"
        assert await first.get_oldest_job_age_seconds() == 0
        assert await first.heartbeat(claimed) is True
        reclaimed = await second.dequeue(timeout_seconds=1)
        assert reclaimed.job_id == claimed.job_id
        assert reclaimed.stream_entry_id == claimed.stream_entry_id
        assert await first.heartbeat(claimed) is False
        assert await second.heartbeat(reclaimed) is True
        assert await second.get_oldest_job_age_seconds() == 0
        await second.ack(reclaimed)
        assert (await native.xpending(second.scan_queue, second.CONSUMER_GROUP))["pending"] == 0
        assert await native.xlen(second.scan_queue) == 0
    finally:
        await native.delete(first.scan_queue, first.dlq, first.retry_queue)
        await native.aclose()


@pytest.mark.asyncio
async def test_api_enqueue_is_atomic_and_replay_safe():
    import importlib.util
    from pathlib import Path
    api_source = Path(__file__).resolve().parents[2] / "api/app/clients/queue.py"
    spec = importlib.util.spec_from_file_location("beta_api_queue", api_source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    native = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    org = f"beta-test-{uuid4()}"
    queue = module.QueueClient("https://unused.example", "unused")
    async def command(*args):
        return {"result": await native.execute_command(*args)}
    queue._command = command
    stream = f"queue:scans:{org}"
    dedupe = f"{stream}:dedupe:scan-fixture"
    try:
        await queue.enqueue("scan.repo.full", {"scan_id": "scan-fixture"}, organization_id=org)
        await queue.enqueue("scan.repo.full", {"scan_id": "scan-fixture"}, organization_id=org)
        assert await native.xlen(stream) == 1
        await native.delete(stream, dedupe)
        await native.set(stream, "wrong type")
        with pytest.raises(ResponseError):
            await queue.enqueue("scan.repo.full", {"scan_id": "scan-fixture"}, organization_id=org)
        assert not await native.exists(dedupe)
    finally:
        await native.delete(stream, dedupe)
        await native.aclose()
