"""Queue client — Upstash Redis REST API backed with at-least-once semantics.

Jobs are BRPOP'd from the ready queue, then persisted with a visibility deadline
so a crash mid-processing can be reclaimed. Successful completion acks the job.
"""

import json
from datetime import datetime

import httpx

from app.contracts.queue import QueueJob

SCAN_TIMEOUT = 1800
VISIBILITY_GRACE = 300
PROCESSING_SET = "queue:scans:processing"


class QueueClient:
    SCAN_QUEUE = "queue:scans"
    DLQ = "queue:scans:dlq"
    PROCESSING_SET = "queue:scans:processing"

    def __init__(self, redis_url: str, redis_token: str):
        self.redis_url = redis_url
        self.redis_token = redis_token
        self._headers = {
            "Authorization": f"Bearer {redis_token}",
            "Content-Type": "application/json",
        }

    async def _command(self, *args: str | int | float) -> dict:
        """Send a Redis command as a JSON array to the Upstash REST API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.redis_url,
                headers=self._headers,
                json=list(args),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def enqueue(self, job_type: str, payload: dict, delay_seconds: int = 0) -> str:
        job = QueueJob.create(job_type, payload)
        job_json = job.model_dump_json()

        if delay_seconds > 0:
            score = datetime.utcnow().timestamp() + delay_seconds
            await self._command("ZADD", self.SCAN_QUEUE, score, job_json)
        else:
            await self._command("LPUSH", self.SCAN_QUEUE, job_json)

        return job.job_id

    async def requeue(self, job: QueueJob, delay_seconds: int = 0) -> None:
        job_json = job.model_dump_json()

        if delay_seconds > 0:
            score = datetime.utcnow().timestamp() + delay_seconds
            await self._command("ZADD", self.SCAN_QUEUE, score, job_json)
        else:
            await self._command("LPUSH", self.SCAN_QUEUE, job_json)

    async def dequeue(self, timeout_seconds: int = 5) -> QueueJob | None:
        try:
            result = await self._command("BRPOP", self.SCAN_QUEUE, timeout_seconds)

            if result and result.get("result"):
                _, value = result["result"]
                job = QueueJob.model_validate_json(value)

                deadline = int(datetime.utcnow().timestamp()) + SCAN_TIMEOUT + VISIBILITY_GRACE
                payload_ttl = SCAN_TIMEOUT + VISIBILITY_GRACE + 3600

                await self._command("SETEX", f"job:{job.job_id}:payload", payload_ttl, value)
                await self._command("ZADD", PROCESSING_SET, deadline, job.job_id)

                return job
        except httpx.HTTPStatusError:
            pass
        return None

    async def ack(self, job_id: str) -> None:
        """Mark a job as successfully completed and remove it from processing tracking."""
        try:
            await self._command("ZREM", PROCESSING_SET, job_id)
            await self._command("DEL", f"job:{job_id}:payload")
        except httpx.HTTPError:
            pass

    async def release(self, job_id: str) -> None:
        """Remove processing tracking for a failed job that is being requeued or DLQ'd."""
        try:
            await self._command("ZREM", PROCESSING_SET, job_id)
            await self._command("DEL", f"job:{job_id}:payload")
        except httpx.HTTPError:
            pass

    async def enqueue_to_dlq(self, job: QueueJob) -> None:
        job_json = job.model_dump_json()
        await self._command("LPUSH", self.DLQ, job_json)

    async def get_job_status(self, job_id: str) -> dict | None:
        result = await self._command("GET", f"job:{job_id}:status")
        if result and result.get("result"):
            return json.loads(result["result"])
        return None

    async def update_job_status(self, job_id: str, stage: str, metadata: dict | None = None) -> None:
        status_data = {
            "stage": stage,
            "updated_at": datetime.utcnow().isoformat(),
            **(metadata or {}),
        }
        await self._command("SETEX", f"job:{job_id}:status", 86400, json.dumps(status_data))

    async def increment_retry(self, job_id: str) -> int:
        result = await self._command("INCR", f"job:{job_id}:retries")
        return int(result.get("result", 1))

    async def get_retry_count(self, job_id: str) -> int:
        result = await self._command("GET", f"job:{job_id}:retries")
        return int(result.get("result") or 0)

    async def get_queue_length(self) -> int:
        result = await self._command("LLEN", self.SCAN_QUEUE)
        return int(result.get("result", 0))

    async def reclaim_stale_jobs(self) -> int:
        """Re-enqueue jobs whose visibility deadline has expired.

        Returns the number of jobs reclaimed.
        """
        now = int(datetime.utcnow().timestamp())
        result = await self._command("ZRANGEBYSCORE", PROCESSING_SET, "-inf", now)
        stale_job_ids = result.get("result")
        if not stale_job_ids:
            return 0

        reclaimed = 0
        for job_id in stale_job_ids:
            payload_result = await self._command("GET", f"job:{job_id}:payload")
            payload = payload_result.get("result") if payload_result else None
            if payload:
                await self._command("LPUSH", self.SCAN_QUEUE, payload)
                reclaimed += 1
            await self._command("ZREM", PROCESSING_SET, job_id)
            await self._command("DEL", f"job:{job_id}:payload")
        return reclaimed

    async def clear_scan_queues(self) -> int:
        result = await self._command("DEL", self.SCAN_QUEUE, self.DLQ, PROCESSING_SET)
        return int(result.get("result", 0))
