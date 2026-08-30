"""Organization-scoped Redis Streams client for dedicated ScanForge workers."""

import json
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from app.contracts.queue import QueueJob


class QueueClient:
    """Consume one organization's scan stream with at-least-once semantics."""

    CONSUMER_GROUP = "scanforge-workers"
    visibility_timeout_ms = 30 * 60 * 1000
    PROMOTE_RETRY_SCRIPT = """
local score = redis.call('ZSCORE', KEYS[1], ARGV[1])
if not score then
    return false
end
local entry_id = redis.call('XADD', KEYS[2], '*', 'job', ARGV[1], 'job_id', ARGV[2])
redis.call('ZREM', KEYS[1], ARGV[1])
return entry_id
"""
    QUARANTINE_RETRY_SCRIPT = """
local score = redis.call('ZSCORE', KEYS[1], ARGV[1])
if not score then
    return false
end
local entry_id = redis.call('XADD', KEYS[2], '*', 'raw_retry', ARGV[1], 'reason', ARGV[2])
redis.call('ZREM', KEYS[1], ARGV[1])
return entry_id
"""

    def __init__(
        self,
        redis_url: str,
        redis_token: str,
        *,
        organization_id: str,
        consumer_name: str,
    ):
        if not str(organization_id).strip():
            raise ValueError("organization_id is required for a dedicated worker queue")
        if not consumer_name.strip():
            raise ValueError("consumer_name is required for a dedicated worker queue")

        self.redis_url = redis_url
        self.redis_token = redis_token
        self.organization_id = str(organization_id)
        self.consumer_name = consumer_name
        self.scan_queue = f"queue:scans:{self.organization_id}"
        self.dlq = f"{self.scan_queue}:dlq"
        self.retry_queue = f"{self.scan_queue}:retry"
        self._headers = {
            "Authorization": f"Bearer {redis_token}",
            "Content-Type": "application/json",
        }

    async def _command(self, *args: str | int | float) -> dict:
        """Send one Redis command as a JSON array to the Upstash REST API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.redis_url,
                headers=self._headers,
                json=list(args),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def _ensure_consumer_group(self) -> None:
        try:
            await self._command(
                "XGROUP",
                "CREATE",
                self.scan_queue,
                self.CONSUMER_GROUP,
                "0",
                "MKSTREAM",
            )
        except httpx.HTTPError:
            # Redis responds with BUSYGROUP after the first worker creates it.
            # A transport failure is handled by dequeue's normal failure path.
            return

    async def dequeue(self, timeout_seconds: int = 5) -> QueueJob | None:
        """Reclaim a stale pending delivery before reading a new stream message."""
        try:
            await self._ensure_consumer_group()
            await self._command("XPENDING", self.scan_queue, self.CONSUMER_GROUP)
            reclaimed = await self._reclaim_one_pending_job()
            if reclaimed is not None:
                return reclaimed

            result = await self._command(
                "XREADGROUP",
                "GROUP",
                self.CONSUMER_GROUP,
                self.consumer_name,
                "COUNT",
                1,
                "BLOCK",
                timeout_seconds * 1000,
                "STREAMS",
                self.scan_queue,
                ">",
            )
            return await self._job_from_read_result(result.get("result"))
        except httpx.HTTPError:
            return None

    async def _reclaim_one_pending_job(self) -> QueueJob | None:
        result = await self._command(
            "XAUTOCLAIM",
            self.scan_queue,
            self.CONSUMER_GROUP,
            self.consumer_name,
            self.visibility_timeout_ms,
            "0-0",
            "COUNT",
            1,
        )
        payload = result.get("result")
        if not payload or len(payload) < 2:
            return None
        return await self._job_from_entry(payload[1][0]) if payload[1] else None

    async def _job_from_read_result(self, payload) -> QueueJob | None:
        if not payload:
            return None
        # Upstash uses [[stream, [[entry_id, [field, value, ...]]]]].
        return await self._job_from_entry(payload[0][1][0])

    async def _job_from_entry(self, entry) -> QueueJob | None:
        entry_id = entry[0] if isinstance(entry, (list, tuple)) and entry else None
        try:
            _, fields = entry
            if isinstance(fields, dict):
                job_json = fields["job"]
            else:
                field_map = dict(zip(fields[::2], fields[1::2], strict=True))
                job_json = field_map["job"]
            job = QueueJob.model_validate_json(job_json)
        except (KeyError, TypeError, ValidationError, ValueError):
            await self._quarantine_stream_entry(entry_id, entry)
            return None
        job.stream_entry_id = entry_id
        return job

    async def _quarantine_stream_entry(self, entry_id, raw_entry) -> None:
        """Persist malformed delivery evidence before removing a poison pending entry."""
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("malformed stream entry has no entry id")
        raw_json = json.dumps(raw_entry, default=str, separators=(",", ":"))
        await self._command(
            "XADD",
            self.dlq,
            "*",
            "raw_entry",
            raw_json,
            "reason",
            "malformed_stream_entry",
        )
        await self._command("XACK", self.scan_queue, self.CONSUMER_GROUP, entry_id)
        await self._command("XDEL", self.scan_queue, entry_id)

    async def ack(self, job: QueueJob) -> None:
        """Acknowledge and delete a processed stream entry only after persistence succeeds."""
        entry_id = self._required_stream_entry_id(job)
        await self._command("XACK", self.scan_queue, self.CONSUMER_GROUP, entry_id)
        await self._command("XDEL", self.scan_queue, entry_id)

    async def move_to_dlq(self, job: QueueJob) -> None:
        """Durably write the DLQ copy before removing the source pending entry."""
        entry_id = self._required_stream_entry_id(job)
        await self._command("XADD", self.dlq, "*", "job", job.model_dump_json(), "job_id", job.job_id)
        await self._command("XACK", self.scan_queue, self.CONSUMER_GROUP, entry_id)
        await self._command("XDEL", self.scan_queue, entry_id)

    async def requeue(self, job: QueueJob, delay_seconds: int = 0) -> None:  # noqa: ARG002
        """Durably stage a delayed successor before removing the pending delivery."""
        entry_id = self._required_stream_entry_id(job)
        due_at = datetime.now(UTC).timestamp() + delay_seconds
        job_json = job.model_dump_json()
        await self._command("ZADD", self.retry_queue, due_at, job_json)
        await self._command("XACK", self.scan_queue, self.CONSUMER_GROUP, entry_id)
        await self._command("XDEL", self.scan_queue, entry_id)

    async def promote_due_retries(self) -> int:
        """Atomically promote due retries without a duplicate XADD/ZREM crash window."""
        now = datetime.now(UTC).timestamp()
        result = await self._command("ZRANGEBYSCORE", self.retry_queue, "-inf", now)
        pending_jobs = result.get("result") or []
        promoted = 0
        for job_json in pending_jobs:
            try:
                job = QueueJob.model_validate_json(job_json)
            except ValidationError:
                await self._quarantine_retry_entry(job_json)
                continue
            result = await self._command(
                "EVAL",
                self.PROMOTE_RETRY_SCRIPT,
                2,
                self.retry_queue,
                self.scan_queue,
                job_json,
                job.job_id,
            )
            if result.get("result"):
                promoted += 1
        return promoted

    async def _quarantine_retry_entry(self, raw_retry: str) -> None:
        await self._command(
            "EVAL",
            self.QUARANTINE_RETRY_SCRIPT,
            2,
            self.retry_queue,
            self.dlq,
            raw_retry,
            "malformed_retry",
        )

    async def get_job_status(self, job_id: str) -> dict | None:
        result = await self._command("GET", self._status_key(job_id))
        if result and result.get("result"):
            return json.loads(result["result"])
        return None

    async def update_job_status(self, job_id: str, stage: str, metadata: dict | None = None) -> None:
        status_data = {
            "stage": stage,
            "updated_at": datetime.now(UTC).isoformat(),
            **(metadata or {}),
        }
        await self._command("SETEX", self._status_key(job_id), 86400, json.dumps(status_data))

    async def increment_retry(self, job_id: str) -> int:
        result = await self._command("INCR", self._retry_key(job_id))
        return int(result.get("result", 1))

    async def get_retry_count(self, job_id: str) -> int:
        result = await self._command("GET", self._retry_key(job_id))
        return int(result.get("result") or 0)

    async def get_queue_length(self) -> int:
        result = await self._command("XLEN", self.scan_queue)
        return int(result.get("result", 0))

    async def reclaim_stale_jobs(self) -> int:
        """Claim pending messages for this worker; no recovery state is deleted."""
        await self._ensure_consumer_group()
        result = await self._command(
            "XAUTOCLAIM",
            self.scan_queue,
            self.CONSUMER_GROUP,
            self.consumer_name,
            self.visibility_timeout_ms,
            "0-0",
            "COUNT",
            100,
        )
        payload = result.get("result") or []
        return len(payload[1]) if len(payload) > 1 else 0

    async def clear_scan_queues(self) -> int:
        result = await self._command("DEL", self.scan_queue, self.dlq, self.retry_queue)
        return int(result.get("result", 0))

    def _status_key(self, job_id: str) -> str:
        return f"{self.scan_queue}:job:{job_id}:status"

    def _retry_key(self, job_id: str) -> str:
        return f"{self.scan_queue}:job:{job_id}:retries"

    @staticmethod
    def _required_stream_entry_id(job: QueueJob) -> str:
        if not job.stream_entry_id:
            raise ValueError("stream entry id is required to acknowledge a queue job")
        return job.stream_entry_id
