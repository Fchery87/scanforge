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

    async def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        url = f"{self.redis_url}{path}"
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=self._headers, timeout=30.0)
            elif method == "POST":
                response = await client.post(url, headers=self._headers, json=data, timeout=30.0)
            elif method == "DELETE":
                response = await client.delete(url, headers=self._headers, timeout=30.0)
            else:
                raise ValueError(f"Unsupported method: {method}")

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
            await self._request("POST", "/zadd", {
                "key": self.SCAN_QUEUE,
                "members": {job_json: score},
            })
        else:
            await self._request("POST", "/lpush", {
                "key": self.SCAN_QUEUE,
                "elements": [job_json],
            })

        return job.job_id

    async def dequeue(self, timeout_seconds: int = 5) -> QueueJob | None:
        try:
            result = await self._request("POST", "/brpop", {
                "key": self.SCAN_QUEUE,
                "timeout": timeout_seconds,
            })

            if result and "element" in result:
                return QueueJob.model_validate_json(result["element"])
        except httpx.HTTPStatusError:
            pass
        return None

    async def enqueue_to_dlq(self, job: QueueJob) -> None:
        job_json = job.model_dump_json()
        await self._request("POST", "/lpush", {
            "key": self.DLQ,
            "elements": [job_json],
        })

    async def get_job_status(self, job_id: str) -> dict | None:
        result = await self._request("GET", f"/get/job:{job_id}:status")
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
        await self._request("POST", "/setex", {
            "key": f"job:{job_id}:status",
            "seconds": 86400,
            "value": json.dumps(status_data),
        })

    async def increment_retry(self, job_id: str) -> int:
        result = await self._request("POST", "/incr", {
            "key": f"job:{job_id}:retries",
        })
        return int(result.get("result", 1))

    async def get_retry_count(self, job_id: str) -> int:
        result = await self._request("GET", f"/get/job:{job_id}:retries")
        return int(result.get("result") or 0)

    async def get_queue_length(self) -> int:
        result = await self._request("GET", f"/llen/{self.SCAN_QUEUE}")
        return int(result.get("result", 0))
