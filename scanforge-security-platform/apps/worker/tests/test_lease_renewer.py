"""R09 slice 2: the worker must keep its execution lease alive while a scan runs.

The API renews leases on POST /api/v1/internal/scans/{scan_id}/heartbeat and
answers 409 when the lease was reclaimed (lease_active / stale_attempt /
lease_expired).  These tests use httpx.MockTransport (same injection style as
the httpx error fakes in test_queue_poll_outcomes.py) to prove that the
renewal loop fires on its interval, that a 409 aborts the execution path with
a typed outcome, and that a terminal scan cancels the renewer task.
"""
from __future__ import annotations

import asyncio
import json as jsonlib
import logging
import tempfile
from pathlib import Path

import httpx
import pytest
from app.services.lease_renewer import LeaseLostError, LeaseRenewer

from app.clients.queue import QueueJob
from app.services.scan_orchestrator import ScanContext, ScanOrchestrator

pytestmark = pytest.mark.asyncio

HEARTBEAT_URL = "http://api.test/api/v1/internal/scans/scan-1/heartbeat"


def _recording_handler(response_status: int = 200, body: dict | None = None):
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "credential": request.headers.get("X-Worker-Credential"),
                "json": jsonlib.loads(request.content.decode() or "null"),
            }
        )
        return httpx.Response(response_status, json=body or {"lease_expires_at": "2026-01-01T00:00:00Z"})

    return handler, requests


def _renewer(handler, **overrides) -> LeaseRenewer:
    kwargs = {
        "scan_id": "scan-1",
        "attempt_id": "attempt-1",
        "execution_revision": 2,
        "api_base_url": "http://api.test",
        "worker_credential": "cred-1",
        "renewal_seconds": 0.02,
        "retry_backoff_seconds": 0.01,
        "max_retry_backoff_seconds": 0.02,
        "transport": httpx.MockTransport(handler),
    }
    kwargs.update(overrides)
    return LeaseRenewer(**kwargs)


async def test_renewal_fires_on_interval_with_worker_credential_and_identity():
    handler, requests = _recording_handler()
    renewer = _renewer(handler)

    renewer.start()
    await asyncio.sleep(0.07)
    await renewer.stop()

    assert renewer.renewal_count >= 2
    assert renewer.lost is None
    for request in requests:
        assert request["url"] == HEARTBEAT_URL
        assert request["credential"] == "cred-1"
        assert request["json"] == {"attempt_id": "attempt-1", "execution_revision": 2}


async def test_conflict_409_stops_renewing_and_reports_typed_lease_lost():
    handler, requests = _recording_handler(
        response_status=409,
        body={"detail": {"code": "stale_attempt", "current_owner": "worker-b", "remaining_seconds": None}},
    )
    renewer = _renewer(handler)

    renewer.start()
    await asyncio.sleep(0.07)

    assert isinstance(renewer.lost, LeaseLostError)
    assert renewer.lost.reason == "stale_attempt"
    assert renewer.lost.detail.get("current_owner") == "worker-b"
    assert not renewer.is_running
    assert renewer.renewal_count == 0
    assert len(requests) == 1, "no heartbeat may follow a 409 conflict"


async def test_conflict_409_without_json_detail_falls_back_to_unknown_reason():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, text="conflict")

    renewer = _renewer(handler)
    renewer.start()
    await asyncio.sleep(0.07)

    assert renewer.lost is not None
    assert renewer.lost.reason == "unknown"


async def test_network_error_retries_with_bounded_backoff_without_crashing(caplog):
    attempts = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] <= 3:
            raise httpx.ConnectError("connection refused", request=_request)
        return httpx.Response(200, json={"lease_expires_at": "2026-01-01T00:00:00Z"})

    renewer = _renewer(handler)
    with caplog.at_level(logging.WARNING):
        renewer.start()
        await asyncio.sleep(0.12)
        await renewer.stop()

    assert renewer.lost is None, "a transient outage must not abort the scan by itself"
    assert renewer.renewal_count == 1
    assert attempts["count"] == 4
    retries = [
        record.retry_in_seconds
        for record in caplog.records
        if record.name == "app.services.lease_renewer" and record.levelno == logging.WARNING
    ]
    # Backoff doubles from 0.01 s and is capped at 0.02 s.
    assert retries == [0.01, 0.02, 0.02]


async def test_stop_cancels_renewer_task_before_any_heartbeat():
    handler, requests = _recording_handler()
    renewer = _renewer(handler, renewal_seconds=3600)

    renewer.start()
    assert renewer.is_running
    await renewer.stop()

    assert not renewer.is_running
    assert renewer._task is not None and renewer._task.cancelled()
    assert renewer.renewal_count == 0
    assert requests == []


async def test_missing_execution_identity_disables_renewal_instead_of_looping_422s():
    handler, requests = _recording_handler()
    renewer = _renewer(handler, attempt_id=None)

    renewer.start()
    await asyncio.sleep(0.06)

    assert requests == []
    assert not renewer.is_running


class DummyQueue:
    def __init__(self):
        self.ack_calls = 0
        self.increment_retry_calls = 0
        self.requeued_jobs: list = []
        self.dlq_calls = 0

    async def update_job_status(self, *_args, **_kwargs):
        return None

    async def ack(self, *_args, **_kwargs):
        self.ack_calls += 1

    async def increment_retry(self, *_args, **_kwargs):
        self.increment_retry_calls += 1
        return 0

    async def requeue(self, job, delay_seconds: int = 0):
        self.requeued_jobs.append((job, delay_seconds))

    async def move_to_dlq(self, *_args, **_kwargs):
        self.dlq_calls += 1


class DummyR2:
    pass


def _orchestrator(queue: DummyQueue) -> ScanOrchestrator:
    orchestrator = ScanOrchestrator(queue=queue, r2=DummyR2(), api_base_url="http://api.test")

    async def noop(*_args, **_kwargs):
        return None

    async def false_stop(*_args, **_kwargs):
        return False

    async def load_context(job):
        return ScanContext(
            scan_id=job.payload["scan_id"],
            organization_id="org-1",
            repository_id="repo-1",
            project_id="project-1",
            branch=None,
            commit_sha=None,
            job_id=job.job_id,
            attempt_id="attempt-1",
            execution_revision=2,
        )

    orchestrator._update_status = noop
    orchestrator._update_scan_status = noop
    orchestrator._stop_if_canceled = false_stop
    orchestrator._load_scan_context = load_context
    orchestrator._ai_investigation.run = noop
    orchestrator._persistence.complete_scan = noop
    orchestrator._persistence.send_notifications = noop
    return orchestrator


def _conflict_renewer_factory(captured: dict):
    def build(context: ScanContext) -> LeaseRenewer:
        handler, requests = _recording_handler(
            response_status=409,
            body={"detail": {"code": "lease_active", "current_owner": "worker-b", "remaining_seconds": None}},
        )
        renewer = _renewer(handler, scan_id=context.scan_id)
        captured["requests"] = requests
        captured["renewer"] = renewer
        return renewer

    return build


async def test_lease_conflict_aborts_execution_without_failure_bookkeeping(caplog):
    queue = DummyQueue()
    orchestrator = _orchestrator(queue)
    captured: dict = {}
    orchestrator._build_lease_renewer = _conflict_renewer_factory(captured)
    body_finished = []

    async def slow_repository(_context):
        await asyncio.sleep(3600)
        body_finished.append(True)
        return Path(tempfile.gettempdir()) / "lease-renewer-unused"

    orchestrator._execution.prepare_repository = slow_repository

    with caplog.at_level(logging.ERROR):
        success = await orchestrator.process_job(QueueJob.create("scan.repo.full", {"scan_id": "scan-1"}))

    assert success is False
    assert body_finished == [], "the execution path must be aborted mid-flight"
    assert captured["renewer"].lost is not None and captured["renewer"].lost.reason == "lease_active"
    assert len(captured["requests"]) == 1
    assert queue.ack_calls == 0, "the reclaimed job stays in the pending list for redelivery"
    assert queue.increment_retry_calls == 0 and queue.requeued_jobs == [] and queue.dlq_calls == 0
    aborted = [
        record
        for record in caplog.records
        if record.getMessage() == "scan aborted: execution lease reclaimed"
    ]
    assert aborted and aborted[0].scan_id == "scan-1" and aborted[0].reason == "lease_active"


async def test_terminal_scan_cancels_renewer_task_and_never_heartbeats():
    queue = DummyQueue()
    orchestrator = _orchestrator(queue)
    captured: dict = {}

    def build(context: ScanContext) -> LeaseRenewer:
        handler, requests = _recording_handler()
        renewer = _renewer(handler, scan_id=context.scan_id, renewal_seconds=3600)
        captured["requests"] = requests
        captured["renewer"] = renewer
        return renewer

    orchestrator._build_lease_renewer = build

    async def fast_repository(_context):
        return Path(tempfile.gettempdir()) / "lease-renewer-unused"

    orchestrator._execution.prepare_repository = fast_repository

    async def empty_scanners(_context, _job_type):
        return {}

    orchestrator._execution.run_scanners = empty_scanners

    success = await orchestrator.process_job(QueueJob.create("scan.repo.full", {"scan_id": "scan-1"}))

    assert success is True
    assert queue.ack_calls == 1
    assert queue.requeued_jobs == []
    renewer = captured["renewer"]
    assert renewer is not None
    assert not renewer.is_running
    assert renewer._task is not None and renewer._task.cancelled()
    assert captured["requests"] == [], "a terminal scan must not renew its lease again"
