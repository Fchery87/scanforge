import json
import logging

import pytest

from app.clients.queue import QueueJob, QueuePollStatus
from app.core.logging import _JsonFormatter
from app.worker.main import Worker
from app.worker.scheduler import run_scheduled_scans


@pytest.mark.asyncio
async def test_worker_logs_include_structured_status_fields():
    logger = logging.getLogger("test.worker")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        1,
        "worker status",
        (),
        None,
        extra={"queue_length": 2, "active_tasks": 1, "workers": 3},
    )
    payload = json.loads(_JsonFormatter().format(record))
    assert payload["queue_length"] == 2
    assert payload["active_tasks"] == 1
    assert payload["workers"] == 3


@pytest.mark.asyncio
async def test_scheduler_logs_structured_result(monkeypatch, caplog):
    async def fake_trigger():
        return {"found": 2, "queued": 1, "failed": 0}

    monkeypatch.setattr("app.worker.scheduler.trigger_due_scan_schedules", fake_trigger)
    with caplog.at_level(logging.INFO):
        await run_scheduled_scans()

    record = caplog.records[-1]
    assert record.getMessage() == "processed due schedules"
    assert record.found == 2
    assert record.queued == 1
    assert record.failed == 0


class RecordingQueue:
    def __init__(self, job: QueueJob):
        self.job = job
        self.dequeue_calls = 0
        self.get_retry_count_calls = 0
        self.enqueue_calls: list[tuple[str, dict]] = []
        self.dlq_calls = 0

    async def dequeue(self, timeout_seconds: int = 5):
        job, _status = await self.dequeue_with_status(timeout_seconds)
        return job

    async def dequeue_with_status(self, timeout_seconds: int = 5):
        self.dequeue_calls += 1
        if self.dequeue_calls == 1:
            return self.job, QueuePollStatus.DELIVERED
        return None, QueuePollStatus.EMPTY

    async def get_retry_count(self, job_id: str) -> int:
        self.get_retry_count_calls += 1
        return 1

    async def enqueue(self, job_type: str, payload: dict):
        self.enqueue_calls.append((job_type, payload))

    async def enqueue_to_dlq(self, job):
        self.dlq_calls += 1


class FailingOrchestrator:
    MAX_RETRIES = 3

    async def process_job(self, job: QueueJob) -> bool:
        return False


@pytest.mark.asyncio
async def test_worker_does_not_reenqueue_when_orchestrator_returns_false():
    worker = Worker()
    job = QueueJob.create("scan.repo.full", {"scan_id": "scan-1"})
    queue = RecordingQueue(job)
    orchestrator = FailingOrchestrator()

    await worker.process_single_job(queue, orchestrator)

    assert queue.get_retry_count_calls == 1
    assert queue.enqueue_calls == []
    assert queue.dlq_calls == 0
