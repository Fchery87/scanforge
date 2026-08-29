import json
from datetime import UTC, datetime

import httpx

from app.contracts.queue import QueueJob, ScanJobType


class QueueClient:
    GROUP = "scanforge-workers"
    SCAN_TIMEOUT = 1800

    def __init__(self, redis_url: str, redis_token: str):
        self.redis_url = redis_url
        self.redis_token = redis_token
        self._headers = {"Authorization": f"Bearer {redis_token}", "Content-Type": "application/json"}

    @staticmethod
    def stream_key(organization_id: str) -> str:
        return f"queue:scans:{organization_id}"

    @staticmethod
    def dlq_key(organization_id: str) -> str:
        return f"queue:scans:{organization_id}:dlq"

    async def _command(self, *args: str | int | float) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(self.redis_url, headers=self._headers, json=list(args), timeout=30.0)
            response.raise_for_status()
            return response.json()

    async def ensure_group(self, organization_id: str) -> None:
        stream = self.stream_key(organization_id)
        try:
            await self._command("XGROUP", "CREATE", stream, self.GROUP, "0", "MKSTREAM")
        except httpx.HTTPStatusError as exc:
            if "BUSYGROUP" not in exc.response.text:
                raise

    async def enqueue(self, organization_id: str, job_type: ScanJobType, payload: dict, delay_seconds: int = 0) -> str:
        if delay_seconds > 0:
            raise NotImplementedError("Delayed jobs are not implemented for scan streams")
        job = QueueJob.create(job_type, payload)
        stream = self.stream_key(organization_id)
        await self.ensure_group(organization_id)
        dedupe_key = f"queue:scans:{organization_id}:enqueued:{job.job_id}"
        created = await self._command("SETNX", dedupe_key, "1")
        if int(created.get("result", 0)) == 0:
            return job.job_id
        await self._command("EXPIRE", dedupe_key, 604800)
        await self._command("XADD", stream, "*", "job", job.model_dump_json())
        return job.job_id

    async def get_queue_length(self, organization_id: str) -> int:
        result = await self._command("XLEN", self.stream_key(organization_id))
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
