"""Redis Streams recovery integration test.

Set ``REDIS_URL`` to a Redis 7 endpoint and install the optional ``redis``
package to run this test. It uses two consumer names to model termination after
claim and recovery by a replacement worker.
"""
from __future__ import annotations

import os
import time
from uuid import uuid4

import pytest

redis_asyncio = pytest.importorskip("redis.asyncio")


@pytest.mark.asyncio
async def test_second_consumer_reclaims_job_after_first_terminates():
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is required for the Redis recovery integration test")

    client = redis_asyncio.from_url(redis_url, decode_responses=True)
    org_id = str(uuid4())
    scan_id = str(uuid4())
    stream = f"queue:scans:{org_id}"
    group = "scanforge-workers"
    try:
        await client.xgroup_create(stream, group, id="0", mkstream=True)
        entry_id = await client.xadd(stream, {"scan_id": scan_id})
        delivered = await client.xreadgroup(group, "consumer-1", {stream: ">"}, count=1)
        assert delivered[0][1][0][0] == entry_id

        # Consumer 1 terminates here without XACK. Redis retains the PEL entry.
        time.sleep(0.01)
        next_id, claimed, _deleted = await client.xautoclaim(
            stream,
            group,
            "consumer-2",
            min_idle_time=1,
            start_id="0-0",
            count=1,
        )

        assert next_id
        assert claimed == [(entry_id, {"scan_id": scan_id})]
        assert await client.xack(stream, group, entry_id) == 1
    finally:
        await client.delete(stream)
        await client.aclose()
