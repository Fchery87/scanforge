import pytest

from app.clients.queue import QueueJob
from app.worker.main import Worker


class RecordingQueue:
    def __init__(self, job: QueueJob):
        self.job = job
        self.dequeue_calls = 0
        self.get_retry_count_calls = 0
        self.enqueue_calls: list[tuple[str, dict]] = []
        self.dlq_calls = 0

    async def dequeue(self, timeout_seconds: int = 5):
        self.dequeue_calls += 1
        if self.dequeue_calls == 1:
            return self.job
        return None

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
