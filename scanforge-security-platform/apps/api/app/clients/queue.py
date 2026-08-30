import json
from datetime import UTC, datetime
from uuid import UUID

import httpx

from app.contracts.queue import QueueJob, ScanJobType


class QueueClient:
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

    async def enqueue(
        self,
        job_type: ScanJobType,
        payload: dict,
        *,
        organization_id: UUID | str,
        delay_seconds: int = 0,
    ) -> str:
        if delay_seconds > 0:
            raise NotImplementedError("Delayed jobs are not implemented for the scan queue")

        job = QueueJob.create(job_type, payload)
        job_json = job.model_dump_json()
        dedupe_key = f"queue:scans:{organization_id}:dedupe:{job.job_id}"
        claimed = await self._command("SET", dedupe_key, "1", "NX", "EX", 86400)
        if claimed.get("result") is None:
            return job.job_id

        try:
            await self._command(
                "XADD",
                self._scan_queue_key(organization_id),
                "*",
                "job",
                job_json,
                "job_id",
                job.job_id,
            )
        except Exception:
            await self._command("DEL", dedupe_key)
            raise

        return job.job_id

    @staticmethod
    def _scan_queue_key(organization_id: UUID | str) -> str:
        return f"queue:scans:{organization_id}"

    async def get_job_status(self, job_id: str) -> dict | None:
        result = await self._command("GET", f"job:{job_id}:status")
        if result and result.get("result"):
            return json.loads(result["result"])
        return None

    async def update_job_status(
        self,
        job_id: str,
        stage: str,
        metadata: dict | None = None,
    ) -> None:
        status_data = {
            "stage": stage,
            "updated_at": datetime.now(UTC).isoformat(),
            **(metadata or {}),
        }
        await self._command("SETEX", f"job:{job_id}:status", 86400, json.dumps(status_data))

    async def increment_retry(self, job_id: str) -> int:
        result = await self._command("INCR", f"job:{job_id}:retries")
        return int(result.get("result", 1))

    async def get_retry_count(self, job_id: str) -> int:
        result = await self._command("GET", f"job:{job_id}:retries")
        return int(result.get("result") or 0)
