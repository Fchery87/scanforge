import json
from datetime import UTC, datetime

import httpx

from app.contracts.queue import QueueJob


class QueueClient:
    GROUP = "scanforge-workers"
    SCAN_TIMEOUT = 1800

    def __init__(self, redis_url: str, redis_token: str, organization_id: str = "dev", consumer_name: str = "dev"):
        if not organization_id or not consumer_name:
            raise ValueError("organization_id and consumer_name are required")
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.organization_id = organization_id
        self.consumer_name = consumer_name
        self.stream = f"queue:scans:{organization_id}"
        self.dlq = f"{self.stream}:dlq"
        self._headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}

    async def _command(self, *args: str | int | float) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(self.redis_url, headers=self._headers, json=list(args), timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def ensure_group(self) -> None:
        try:
            await self._command("XGROUP", "CREATE", self.stream, self.GROUP, "0", "MKSTREAM")
        except httpx.HTTPStatusError as exc:
            if "BUSYGROUP" not in exc.response.text:
                raise

    async def dequeue(self, timeout_seconds: int = 5) -> QueueJob | None:
        reclaimed = await self.reclaim_stale_jobs()
        if reclaimed:
            return reclaimed[0]
        await self.ensure_group()
        result = await self._command(
            "XREADGROUP", "GROUP", self.GROUP, self.consumer_name,
            "COUNT", 1, "BLOCK", timeout_seconds * 1000, "STREAMS", self.stream, ">",
        )
        rows = result.get("result") or []
        if not rows or not rows[0][1]:
            return None
        stream_id, fields = rows[0][1][0]
        values = dict(zip(fields[::2], fields[1::2], strict=True))
        job = QueueJob.model_validate_json(values["job"])
        job.stream_id = stream_id
        return job

    async def ack(self, job_id: str, stream_id: str | None = None) -> None:
        if not stream_id:
            raise ValueError(f"stream id required to acknowledge job {job_id}")
        await self._command("XACK", self.stream, self.GROUP, stream_id)
        await self._command("XDEL", self.stream, stream_id)

    async def reclaim_stale_jobs(self, min_idle_ms: int = 300_000) -> list[QueueJob]:
        await self.ensure_group()
        pending = await self._command("XPENDING", self.stream, self.GROUP)
        if not pending.get("result"):
            return []
        result = await self._command(
            "XAUTOCLAIM", self.stream, self.GROUP, self.consumer_name, min_idle_ms, "0-0", "COUNT", 10
        )
        claimed = (result.get("result") or ["0-0", []])[1]
        jobs: list[QueueJob] = []
        for stream_id, fields in claimed:
            values = dict(zip(fields[::2], fields[1::2], strict=True))
            job = QueueJob.model_validate_json(values["job"])
            job.stream_id = stream_id
            jobs.append(job)
        return jobs

    async def enqueue_to_dlq(self, job: QueueJob) -> None:
        await self._command("XADD", self.dlq, "*", "job", job.model_dump_json())

    async def transfer_to_dlq(self, job: QueueJob) -> None:
        """Durably append to the DLQ before removing the pending source entry."""
        await self.enqueue_to_dlq(job)
        await self.ack(job.job_id, job.stream_id)

    async def release(self, _job_id: str) -> None:
        """Keep the stream entry pending so XAUTOCLAIM can recover it."""

    async def requeue(self, _job: QueueJob, delay_seconds: int = 0) -> None:
        if delay_seconds:
            raise NotImplementedError("Delayed stream retries are not supported")
        # Leaving the entry pending is the durable retry mechanism.

    async def clear_scan_queues(self) -> int:
        result = await self._command("DEL", self.stream, self.dlq)
        return int(result.get("result", 0))

    async def get_queue_length(self) -> int:
        result = await self._command("XLEN", self.stream)
        return int(result.get("result", 0))

    async def get_job_status(self, job_id: str) -> dict | None:
        result = await self._command("GET", f"job:{job_id}:status")
        return json.loads(result["result"]) if result.get("result") else None

    async def update_job_status(self, job_id: str, stage: str, metadata: dict | None = None) -> None:
        data = {"stage": stage, "updated_at": datetime.now(UTC).isoformat(), **(metadata or {})}
        await self._command("SETEX", f"job:{job_id}:status", 86400, json.dumps(data))

    async def increment_retry(self, job_id: str) -> int:
        result = await self._command("INCR", f"job:{job_id}:retries")
        return int(result.get("result", 1))

    async def get_retry_count(self, job_id: str) -> int:
        result = await self._command("GET", f"job:{job_id}:retries")
        return int(result.get("result") or 0)
