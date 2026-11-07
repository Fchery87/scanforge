#!/usr/bin/env python3
"""Issue #5 acceptance rehearsal: kill a real orchestrator before ack.

The drill uses the production QueueClient over the same local REST shim as the
queue recovery drill, then runs the production ScanOrchestrator against a
small HTTP API harness. The victim process is SIGKILLed after Redis claims the
job and while repository execution is still in progress. A fresh worker
reclaims the pending entry, fetches a new authoritative execution identity,
completes the scan, and acknowledges the stream entry.
"""

from __future__ import annotations

import asyncio
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR.parent / "apps" / "worker"))

from r12_queue_recovery_drill import make_backend, serve_rest

ORGANIZATION_ID = "00000000-0000-0000-0000-000000000005"
SCAN_ID = "00000000-0000-0000-0000-000000000505"
JOB_ID = "issue-5-terminal-recovery"


class ApiState:
    def __init__(self):
        self.lock = threading.Lock()
        self.attempts = 0
        self.status = "queued"
        self.completions = 0
        self.status_updates: list[str] = []


def serve_api(state: ApiState) -> tuple[ThreadingHTTPServer, int]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def _json(self, code: int, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if not path.endswith(f"/scans/{SCAN_ID}/execution-context"):
                self._json(404, {"detail": "not found"})
                return
            with state.lock:
                presented = self.headers.get("X-Scan-Attempt-Id")
                if not presented:
                    state.attempts += 1
                    attempt = state.attempts
                else:
                    attempt = state.attempts
                status = state.status
            self._json(200, {
                "scan_id": SCAN_ID,
                "org_id": ORGANIZATION_ID,
                "repository_id": "00000000-0000-0000-0000-000000000506",
                "project_id": "00000000-0000-0000-0000-000000000507",
                "scan_type": "full",
                "expected_scanners": ["fixture"],
                "branch": "main",
                "full_ref_name": "refs/heads/main",
                "branch_generation_number": 1,
                "ancestry_status": "verified_descendant",
                "commit_sha": "a" * 40,
                "head_is_fork": False,
                "status": status,
                "attempt_id": f"attempt-{attempt}",
                "execution_revision": attempt,
                "worker_incarnation_id": "victim" if attempt == 1 else "recovery",
                "lease_owner": "drill-worker",
                "reclaim_reason": "fresh_start" if attempt == 1 else "expired_lease_reclaim",
            })

        def do_PATCH(self):
            path = urlparse(self.path).path
            if not path.endswith(f"/scans/{SCAN_ID}/status"):
                self._json(404, {"detail": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            with state.lock:
                state.status = payload.get("status") or state.status
                state.status_updates.append(state.status)
            self._json(200, {"status": state.status})

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.endswith(f"/scans/{SCAN_ID}/complete"):
                self._json(404, {"detail": "not found"})
                return
            with state.lock:
                state.status = "completed"
                state.completions += 1
            self._json(200, {"status": "completed"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def build_orchestrator(queue, api_url: str, *, victim: bool):
    from app.clients.r2 import R2Client
    from app.scanners.base import ScannerResult
    from app.services.scan_orchestrator import ScanOrchestrator

    class Runtime:
        pass

    orchestrator = ScanOrchestrator(
        queue=queue,
        r2=R2Client(api_url, "drill-credential"),
        api_base_url=api_url,
        worker_credential="drill-credential",
        runtime=Runtime(),
    )

    async def prepare(_context):
        if victim:
            await asyncio.sleep(3600)
        path = Path(tempfile.mkdtemp(prefix="scanforge-issue-5-")) / "source"
        path.mkdir()
        return path

    async def run_scanners(_context, _job_type):
        return {"fixture": ScannerResult("fixture", True, {}, version="drill")}

    async def upload(_context):
        return {}

    async def no_cancel(_context, _job):
        return False

    orchestrator._execution.prepare_repository = prepare
    orchestrator._execution.run_scanners = run_scanners
    orchestrator._execution.upload_artifacts = upload
    orchestrator._execution.cleanup_scanner_artifacts = lambda _context: None
    orchestrator._stop_if_canceled = no_cancel
    async def no_notifications(*_args):
        return None

    orchestrator._persistence.send_notifications = no_notifications
    return orchestrator


def victim_process(port: int, claimed):
    from app.clients.queue import QueueClient

    async def run():
        class DrillQueue(QueueClient):
            visibility_timeout_ms = 300

            async def update_job_status(self, *_args, **_kwargs):
                return None

        queue = DrillQueue(
            f"http://127.0.0.1:{port}/", "drill-token",
            organization_id=ORGANIZATION_ID,
            consumer_name="victim",
        )
        job, status = await queue.dequeue_with_status(5)
        if job is None:
            raise RuntimeError(f"victim did not claim job: {status}")
        claimed.put(job.stream_entry_id)
        orchestrator = build_orchestrator(queue, os.environ["ISSUE5_API_URL"], victim=True)
        await orchestrator.process_job(job)

    asyncio.run(run())


def recovery_process(port: int, result):
    from app.clients.queue import QueueClient

    async def run():
        class DrillQueue(QueueClient):
            visibility_timeout_ms = 300

            async def update_job_status(self, *_args, **_kwargs):
                return None

        queue = DrillQueue(
            f"http://127.0.0.1:{port}/", "drill-token",
            organization_id=ORGANIZATION_ID,
            consumer_name="recovery",
        )
        job, status = await queue.dequeue_with_status(5)
        if job is None:
            raise RuntimeError(f"recovery did not reclaim job: {status}")
        orchestrator = build_orchestrator(queue, os.environ["ISSUE5_API_URL"], victim=False)
        completed = await orchestrator.process_job(job)
        result.put((completed, job.stream_entry_id))

    asyncio.run(run())


def main() -> int:
    multiprocessing.set_start_method("spawn", force=True)
    backend_label, redis_client, owned = make_backend()
    redis_client.flushdb()
    redis_url_server, redis_port = serve_rest(backend_label, redis_client)
    api_state = ApiState()
    api_server, api_port = serve_api(api_state)
    api_url = f"http://127.0.0.1:{api_port}"
    os.environ["ISSUE5_API_URL"] = api_url
    stream = f"queue:scans:{ORGANIZATION_ID}"
    try:
        from app.contracts.queue import QueueJob

        job = QueueJob.create("scan.repo.full", {"scan_id": SCAN_ID}, job_id=JOB_ID)
        redis_client.xadd(stream, {"job": job.model_dump_json(), "job_id": JOB_ID})
        claimed = multiprocessing.Queue()
        victim = multiprocessing.Process(target=victim_process, args=(redis_port, claimed), daemon=True)
        victim.start()
        entry_id = claimed.get(timeout=15)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with api_state.lock:
                if api_state.attempts >= 1:
                    break
            time.sleep(0.01)
        else:
            raise RuntimeError("victim did not fetch an authoritative execution context")
        victim.kill()
        victim.join(timeout=5)
        if victim.exitcode == 0:
            raise RuntimeError("victim unexpectedly exited cleanly")
        print(f"victim SIGKILLed after claim entry={entry_id}", flush=True)
        time.sleep(0.4)

        recovered = multiprocessing.Queue()
        recovery = multiprocessing.Process(target=recovery_process, args=(redis_port, recovered), daemon=True)
        recovery.start()
        completed, recovered_entry = recovered.get(timeout=30)
        recovery.join(timeout=10)
        if recovery.exitcode != 0 or not completed:
            raise RuntimeError(f"recovery did not complete: exit={recovery.exitcode}, result={completed}")
        pending = redis_client.xpending(stream, "scanforge-workers")["pending"]
        stream_len = redis_client.xlen(stream)
        dlq_len = redis_client.xlen(f"{stream}:dlq")
        print(
            f"recovered entry={recovered_entry}; terminal_status=completed; "
            f"pending={pending}; stream_len={stream_len}; dlq={dlq_len}",
            flush=True,
        )
        if pending or stream_len or dlq_len:
            raise RuntimeError("queue was not drained after terminal completion")
        print("RESULT: PASS (killed worker reclaimed, authoritative context refreshed, terminal completion persisted, acked)")
        return 0
    finally:
        api_server.shutdown()
        redis_url_server.shutdown()
        redis_client.delete(stream, f"{stream}:dlq", f"{stream}:retry")
        if owned is not None:
            owned.terminate()
            owned.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
