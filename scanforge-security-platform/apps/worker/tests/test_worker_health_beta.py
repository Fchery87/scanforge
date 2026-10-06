from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.worker.main import Worker


@pytest.mark.asyncio
async def test_worker_reports_queue_outage_and_recovery_without_claiming_empty():
    worker = Worker()
    queue = SimpleNamespace(dequeue=AsyncMock(side_effect=httpx.ConnectError("failed")))
    await worker.process_single_job(queue, SimpleNamespace())
    assert worker.queue_available is False
    assert worker.queue_failures == 1
    queue.dequeue = AsyncMock(return_value=None)
    await worker.process_single_job(queue, SimpleNamespace())
    assert worker.queue_available is True
    assert worker.queue_failures == 0


def test_queue_outage_backoff_is_bounded():
    worker = Worker()
    worker.queue_failures = 20
    assert 0 < worker.queue_backoff_seconds <= 60


def test_readiness_requires_live_recent_worker_and_available_queue(monkeypatch, tmp_path):
    from app.worker.health import ready, write_health

    monkeypatch.setenv("WORKER_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setenv("WORKER_ORGANIZATION_ID", "org")
    assert ready() is False
    write_health(queue_available=True, queue_failures=0)
    assert ready() is True
    write_health(queue_available=False, queue_failures=1)
    assert ready() is False


def test_private_beta_rejects_parallel_scans(monkeypatch):
    monkeypatch.setenv("APP_ENV", "private-beta")
    with pytest.raises(ValueError, match="one scan"):
        Worker(concurrency=2)
    assert Worker().concurrency == 1
