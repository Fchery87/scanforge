from __future__ import annotations

import os
import time

import pytest

redis = pytest.importorskip("redis")


@pytest.mark.integration
def test_second_consumer_reclaims_pending_scan_after_first_consumer_crash():
    url = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
    try:
        client = redis.Redis.from_url(url, decode_responses=True)
        client.ping()
    except Exception as exc:
        pytest.skip(f"Redis is not available: {exc}")

    organization_id = f"integration-{time.time_ns()}"
    stream = f"queue:scans:{organization_id}"
    group = "scanforge-workers"
    scan_id = "scan-crash-recovery"
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        client.xadd(stream, {"job": "{}", "job_id": scan_id})
        first = client.xreadgroup(group, "consumer-a", {stream: ">"}, count=1)
        assert first[0][1][0][1]["job_id"] == scan_id

        reclaimed = client.xautoclaim(
            stream,
            group,
            "consumer-b",
            min_idle_time=0,
            start_id="0-0",
            count=1,
        )
        messages = reclaimed[1]
        assert messages[0][1]["job_id"] == scan_id
    finally:
        client.delete(stream)
