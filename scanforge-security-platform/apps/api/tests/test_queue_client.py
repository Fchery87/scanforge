import pytest

from app.clients.queue import QueueClient


@pytest.mark.asyncio
async def test_enqueue_rejects_unimplemented_delayed_jobs():
    queue = QueueClient(redis_url="https://example.upstash.io", redis_token="token")

    with pytest.raises(NotImplementedError, match="Delayed jobs are not implemented"):
        await queue.enqueue("org-123", "scan.repo.full", {"scan_id": "123"}, delay_seconds=30)
