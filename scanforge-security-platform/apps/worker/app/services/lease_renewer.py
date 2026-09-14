"""Worker-side execution lease renewal (R09 slice 2).

The API owns execution leases and renews them whenever a worker POSTs to
``/api/v1/internal/scans/{scan_id}/heartbeat`` with its worker credential.
While a scan is running, the worker must keep that heartbeat up: if the
lease is reclaimed (409 with ``lease_active`` / ``stale_attempt`` /
``lease_expired``), the scan has lost the right to execute and must abort
instead of double-writing results with a successor attempt.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.logging import get_logger

_log = get_logger(__name__)


class LeaseLostError(Exception):
    """The API reports this attempt's execution lease was reclaimed."""

    def __init__(self, reason: str, detail: dict[str, Any] | None = None):
        self.reason = reason
        self.detail = detail or {}
        super().__init__(f"execution lease lost (reason={reason}): {self.detail}")


class LeaseRenewer:
    """Keep one scan attempt's execution lease alive with periodic heartbeats.

    The loop starts with ``start()`` and POSTs the attempt identity to the
    heartbeat endpoint every ``renewal_seconds``. A 409 answer means the
    lease was reclaimed: the loop records a :class:`LeaseLostError`, stops
    renewing, and ``wait_lost()`` resolves so the execution path can abort.
    Transport and 5xx failures retry with exponential backoff capped at
    ``max_retry_backoff_seconds``; a transient outage never aborts a scan
    by itself. ``stop()`` cancels the loop, and no heartbeat is sent after
    a terminal state, cancellation, or stop.
    """

    RENEWAL_SECONDS = 30.0
    RETRY_BACKOFF_SECONDS = 1.0
    MAX_RETRY_BACKOFF_SECONDS = 30.0
    HEARTBEAT_TIMEOUT_SECONDS = 30.0

    def __init__(
        self,
        scan_id: str,
        attempt_id: str | None,
        execution_revision: int | None,
        api_base_url: str,
        worker_credential: str,
        *,
        renewal_seconds: float = RENEWAL_SECONDS,
        retry_backoff_seconds: float = RETRY_BACKOFF_SECONDS,
        max_retry_backoff_seconds: float = MAX_RETRY_BACKOFF_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.scan_id = scan_id
        self.attempt_id = attempt_id
        self.execution_revision = execution_revision
        self.api_base_url = api_base_url.rstrip("/")
        self.worker_credential = worker_credential
        self.renewal_seconds = renewal_seconds
        self.retry_backoff_seconds = retry_backoff_seconds
        self.max_retry_backoff_seconds = max_retry_backoff_seconds
        self.transport = transport

        self.renewal_count = 0
        self.lost: LeaseLostError | None = None
        self._task: asyncio.Task | None = None
        self._stopped = False
        self._lost_event = asyncio.Event()

    def start(self) -> None:
        """Start the renewal loop; disabled without a full execution identity."""
        if self._task is not None and not self._task.done():
            return
        if not self.attempt_id or self.execution_revision is None:
            _log.warning(
                "lease renewal disabled: execution identity missing",
                extra={"scan_id": self.scan_id},
            )
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name=f"lease-renewer-{self.scan_id}")

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def wait_lost(self) -> None:
        """Resolve once the lease is reported lost (never for disabled renewal)."""
        await self._lost_event.wait()

    async def stop(self) -> None:
        """Cancel the renewal task and wait for it; safe to call repeatedly."""
        self._stopped = True
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        backoff = self.retry_backoff_seconds
        async with httpx.AsyncClient(transport=self.transport) as client:
            # Deadline-based pacing: every attempt has an absolute due time, so
            # a slow loop tick delays one attempt instead of shifting the whole
            # schedule. The first attempt is immediate.
            due = loop.time()
            while not self._stopped:
                # Yield twice so a stop() that races this task's startup (a scan
                # that reached a terminal state in the same loop tick start() ran)
                # is always resumed before the first heartbeat is sent: the
                # waiter chain from the finished scan task back to process_job is
                # exactly one hop, and each sleep(0) puts us one hop further back.
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                if self._stopped:
                    return
                await asyncio.sleep(max(0.0, due - loop.time()))
                if self._stopped:
                    return
                try:
                    await self._heartbeat(client)
                except LeaseLostError as exc:
                    self.lost = exc
                    self._lost_event.set()
                    return
                except httpx.HTTPError as exc:
                    _log.warning(
                        "lease heartbeat failed; retrying with backoff",
                        extra={
                            "scan_id": self.scan_id,
                            "error": str(exc),
                            "retry_in_seconds": backoff,
                        },
                    )
                    # Never retry faster than the renewal interval itself.
                    due = max(due, loop.time() - self.renewal_seconds) + self.renewal_seconds + backoff
                    backoff = min(backoff * 2, self.max_retry_backoff_seconds)
                    continue
                self.renewal_count += 1
                backoff = self.retry_backoff_seconds
                due = max(due + self.renewal_seconds, loop.time())

    async def _heartbeat(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            f"{self.api_base_url}/api/v1/internal/scans/{self.scan_id}/heartbeat",
            json={"attempt_id": self.attempt_id, "execution_revision": self.execution_revision},
            headers={"X-Worker-Credential": self.worker_credential},
            timeout=self.HEARTBEAT_TIMEOUT_SECONDS,
        )
        if response.status_code == 409:
            raise LeaseLostError(**self._parse_conflict(response))
        response.raise_for_status()

    @staticmethod
    def _parse_conflict(response: httpx.Response) -> dict[str, Any]:
        """Extract a typed reason from a 409 body, defaulting to ``unknown``."""
        try:
            detail = response.json().get("detail")
        except ValueError:
            return {"reason": "unknown", "detail": {}}
        if isinstance(detail, dict) and detail.get("code"):
            return {"reason": str(detail["code"]), "detail": detail}
        return {"reason": "unknown", "detail": detail if isinstance(detail, dict) else {"detail": detail}}
