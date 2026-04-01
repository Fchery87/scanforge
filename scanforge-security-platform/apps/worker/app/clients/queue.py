import json
from datetime import datetime
from typing import Literal
from uuid import uuid4

import httpx
from pydantic import BaseModel


class QueueJob(BaseModel):
    job_type: str
    job_id: str
    payload: dict
    created_at: str

    @classmethod
    def create(
        cls,
        job_type: Literal["scan.repo.full", "scan.repo.diff", "scan.dependencies", "scan.secrets"],
        payload: dict,
    ) -> "QueueJob":
        return cls(
            job_type=job_type,
            job_id=str(uuid4()),
            payload=payload,
            created_at=datetime.utcnow().isoformat(),
        )


class QueueClient:
    SCAN_QUEUE = "queue:scans"
    DLQ = "queue:scans:dlq"
    SCAN_TIMEOUT = 1800

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
        job_type: Literal["scan.repo.full", "scan.repo.diff", "scan.dependencies", "scan.secrets"],
        payload: dict,
        delay_seconds: int = 0,
    ) -> str:
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
                # BRPOP returns [key, value]
                _, value = result["result"]
                return QueueJob.model_validate_json(value)
        except httpx.HTTPStatusError:
            pass
        return None

    async def enqueue_to_dlq(self, job: QueueJob) -> None:
        job_json = job.model_dump_json()
        await self._command("LPUSH", self.DLQ, job_json)

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

    async def clear_scan_queues(self) -> int:
        result = await self._command("DEL", self.SCAN_QUEUE, self.DLQ)
        return int(result.get("result", 0))
