"""Queue maintenance races against an owned, disposable Redis process."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import shutil
import socket
import subprocess
import time
from uuid import uuid4

import pytest
import redis
from redis.exceptions import ResponseError

from app.clients.queue import QueueClient
from app.contracts.queue import QueueJob


@pytest.fixture
def owned_redis(tmp_path):
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is required for real queue maintenance tests")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [binary, "--bind", "127.0.0.1", "--port", str(port), "--dir", str(tmp_path),
         "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    client = redis.Redis(host="127.0.0.1", port=port, decode_responses=True, protocol=2,
                         socket_connect_timeout=1, socket_timeout=2)
    try:
        deadline = time.monotonic() + 5
        while True:
            if process.poll() is not None:
                pytest.fail("owned redis-server exited before readiness")
            try:
                client.ping()
                break
            except redis.ConnectionError:
                if time.monotonic() >= deadline:
                    pytest.fail("owned redis-server did not become ready")
                time.sleep(0.02)
        yield client
    finally:
        client.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def queue(owned_redis):
    client = QueueClient("http://unused", "unused", organization_id=str(uuid4()),
                         consumer_name="maintenance")
    client.visibility_timeout_ms = 60_000
    owned_redis.xgroup_create(client.scan_queue, client.CONSUMER_GROUP, id="0-0", mkstream=True)

    async def command(*args):
        # redis-py normally transforms Streams responses into dictionaries.
        # Disable that transformation to retain the production REST array shape.
        with owned_redis.client() as connection:
            connection.response_callbacks = {}
            try:
                return {"result": connection.execute_command(*args)}
            except ResponseError as exc:
                if str(exc).startswith("BUSYGROUP"):
                    return {"error": str(exc)}
                raise

    client._command = command
    return client


def pending_delivery(redis_client, queue, *, stale=True, fields=None):
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-1"})
    fields = fields if fields is not None else {"job": job.model_dump_json(), "job_id": job.job_id}
    entry = redis_client.xadd(queue.scan_queue, fields)
    redis_client.xreadgroup(queue.CONSUMER_GROUP, "worker", {queue.scan_queue: ">"}, count=1)
    if stale:
        redis_client.xclaim(queue.scan_queue, queue.CONSUMER_GROUP, "worker", 0,
                           [entry], idle=queue.visibility_timeout_ms + 1_000)
    return entry, fields


def reclaim_entry(redis_client, queue, entry):
    return redis_client.eval(queue.REQUEUE_STALE_SCRIPT, 1, queue.scan_queue,
                             queue.CONSUMER_GROUP, queue.visibility_timeout_ms, entry)


def test_maintenance_requeues_once_and_preserves_payload(owned_redis, queue):
    original, fields = pending_delivery(owned_redis, queue)
    assert asyncio.run(queue.reclaim_stale_jobs()) == 1
    assert asyncio.run(queue.reclaim_stale_jobs()) == 0
    rows = owned_redis.xrange(queue.scan_queue)
    assert len(rows) == 1 and rows[0][0] != original and rows[0][1] == fields
    assert owned_redis.xpending(queue.scan_queue, queue.CONSUMER_GROUP)["pending"] == 0


def test_replayed_eval_after_lost_response_does_not_duplicate(owned_redis, queue):
    original, _ = pending_delivery(owned_redis, queue)
    successor = reclaim_entry(owned_redis, queue, original)
    assert successor
    assert not reclaim_entry(owned_redis, queue, original)
    assert [row[0] for row in owned_redis.xrange(queue.scan_queue)] == [successor]


def test_concurrent_maintenance_candidates_create_one_successor(owned_redis, queue):
    original, _ = pending_delivery(owned_redis, queue)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: reclaim_entry(owned_redis, queue, original), range(8)))
    assert sum(bool(result) for result in results) == 1
    assert owned_redis.xlen(queue.scan_queue) == 1
    assert owned_redis.xpending(queue.scan_queue, queue.CONSUMER_GROUP)["pending"] == 0


def test_worker_claim_between_listing_and_eval_prevents_requeue(owned_redis, queue):
    original, _ = pending_delivery(owned_redis, queue)
    owned_redis.xclaim(queue.scan_queue, queue.CONSUMER_GROUP, "successor-worker", 0, [original])
    assert not reclaim_entry(owned_redis, queue, original)
    pending = owned_redis.xpending_range(queue.scan_queue, queue.CONSUMER_GROUP, "-", "+", 1)
    assert pending[0]["consumer"] == "successor-worker"
    assert owned_redis.xrange(queue.scan_queue)[0][0] == original


def test_active_delivery_is_not_requeued(owned_redis, queue):
    original, _ = pending_delivery(owned_redis, queue, stale=False)
    assert asyncio.run(queue.reclaim_stale_jobs()) == 0
    assert not reclaim_entry(owned_redis, queue, original)
    assert owned_redis.xpending(queue.scan_queue, queue.CONSUMER_GROUP)["pending"] == 1


def test_deleted_pending_entry_is_acknowledged_without_successor(owned_redis, queue):
    original, _ = pending_delivery(owned_redis, queue)
    owned_redis.xdel(queue.scan_queue, original)
    assert not reclaim_entry(owned_redis, queue, original)
    assert owned_redis.xlen(queue.scan_queue) == 0
    assert owned_redis.xpending(queue.scan_queue, queue.CONSUMER_GROUP)["pending"] == 0


def test_malformed_delivery_is_requeued_then_quarantined(owned_redis, queue):
    pending_delivery(owned_redis, queue, fields={"unexpected": "payload"})
    assert asyncio.run(queue.reclaim_stale_jobs()) == 1
    assert asyncio.run(queue.dequeue()) is None
    assert owned_redis.xlen(queue.scan_queue) == 0
    assert owned_redis.xpending(queue.scan_queue, queue.CONSUMER_GROUP)["pending"] == 0
    dlq = owned_redis.xrange(queue.dlq)
    assert len(dlq) == 1
    assert dlq[0][1]["reason"] == "malformed_stream_entry"
