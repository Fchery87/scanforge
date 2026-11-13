"""Issue #5: SIGKILL recovery through the real HTTP API and migrated PostgreSQL.

Opt in with RECOVERY_WORKER_PYTHON pointing to an existing worker interpreter.
No configured database/Redis URL is accepted. All child services are owned here.
"""
import asyncio
import json
import os
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from recovery_support.processes import (
    SUPPORT,
    Processes,
    await_http,
    free_port,
    isolated_env,
    redis_command,
    start_redis,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_scan_dispatch import _disposable_postgres_url, _find_pg_bin, _seed_org_project_repo

from app.clients.queue import QueueClient
from app.db.models import Scan
from app.schemas.scans import ScanCreate
from app.services.scan_dispatch import ScanDispatchService
from app.services.scans import ScanService
from app.services.worker_identities import WorkerIdentityService

APP = Path(__file__).resolve().parents[3]


@pytest.fixture
async def recovery(tmp_path, monkeypatch):
    worker_python = os.environ.get("RECOVERY_WORKER_PYTHON")
    if not worker_python:
        if os.environ.get("RECOVERY_REQUIRED") == "1":
            pytest.fail("RECOVERY_WORKER_PYTHON is required")
        pytest.skip("set RECOVERY_WORKER_PYTHON to an existing worker interpreter")
    if os.environ.get("RECOVERY_REQUIRED") == "1":
        assert all(_find_pg_bin(name) for name in ("initdb", "pg_ctl", "createdb")), "PostgreSQL binaries required"
    assert Path(worker_python).is_file()
    for parent in (APP, *APP.parents):
        assert not (parent / ".env").exists(), "recovery requires a dotenv-free checkout"
    for key in ("DISPATCH_POSTGRES_URL", "R04_POSTGRES_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    processes = Processes(tmp_path)
    env = isolated_env(tmp_path)
    with _disposable_postgres_url() as database_url:
        engine = create_async_engine(database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            redis_url = start_redis(processes, worker_python, env)
            async with factory() as db:
                org, project, repo, _user = await _seed_org_project_repo(db)
                identity, credential = WorkerIdentityService(db, "disposable-pepper").create_identity(
                    organization_id=UUID(str(org.id)), name="recovery-worker",
                    capabilities=["scans:read", "scans:write", "findings:write"],
                )
                await db.commit()
                scan, _, _ = await ScanService(db).create(UUID(str(repo.id)), ScanCreate(
                    repository_id=UUID(str(repo.id)), trigger_type="webhook", scan_type="secrets",
                    branch_name="main", commit_sha="c" * 40,
                ), None, ancestry_relation="ahead")
                queue = QueueClient(redis_url, "disposable")
                results = await ScanDispatchService(db, queue=queue).dispatch_due_obligations(
                    lease_owner="recovery-test")
                assert len(results) == 1
                assert results[0].dispatched
                # Poison immutable hints in the real delivery. Only scan_id is authority lookup.
                stream = f"queue:scans:{org.id}"
                entry, fields = redis_command(redis_url, "XRANGE", stream, "-", "+")[0]
                job = json.loads(dict(zip(fields[::2], fields[1::2], strict=True))["job"])
                job["payload"].update({"organization_id": "forged", "repository_id": "forged",
                                       "commit_sha": "f" * 40, "attempt_id": "forged"})
                redis_command(redis_url, "XDEL", stream, entry)
                redis_command(redis_url, "XADD", stream, "*", "job", json.dumps(job),
                              "job_id", job["job_id"])
            port = free_port()
            api_url = f"http://127.0.0.1:{port}"
            api = processes.start("api", [sys.executable, "-m", "uvicorn", "app.main:app",
                                         "--host", "127.0.0.1", "--port", str(port)], {
                **env, "PYTHONPATH": str(APP / "apps/api"), "DATABASE_URL": database_url,
                "WORKER_CREDENTIAL_PEPPER": "disposable-pepper",
            })
            await_http(api, api_url)
            worker_env = {**env, "PYTHONPATH": str(APP / "apps/worker"), "API_BASE_URL": api_url,
                          "WORKER_ORGANIZATION_ID": str(org.id), "WORKER_CREDENTIAL": credential,
                          "WORKER_CONSUMER_NAME": "recovery", "UPSTASH_REDIS_REST_URL": redis_url,
                          "UPSTASH_REDIS_REST_TOKEN": "disposable",
                          "WORKER_WORKSPACE_ROOT": str(tmp_path / "workspaces")}
            yield Recovery(processes, factory, worker_python, worker_env, scan.id,
                           identity={"organization_id": str(org.id), "project_id": str(project.id),
                            "repository_id": str(repo.id), "scan_id": str(scan.id),
                            "commit_sha": "c" * 40}, principal=str(identity.id))
        finally:
            processes.close()
            await engine.dispose()


class Recovery:
    def __init__(self, processes, factory, python, env, scan_id, *, identity, principal):
        self.processes, self.factory, self.python, self.env = processes, factory, python, env
        self.scan_id, self.identity, self.principal = scan_id, identity, principal
        self.stream = f"queue:scans:{identity['organization_id']}"

    def command(self, *args):
        return redis_command(self.env["UPSTASH_REDIS_REST_URL"], *args)

    def worker(self, name, mode):
        return self.processes.start(name, [self.python, str(SUPPORT / "worker_process.py"), "worker"],
                                    {**self.env, "RECOVERY_BOUNDARY_MODE": mode,
                                     "WORKER_CONSUMER_NAME": name})

    async def scan(self):
        async with self.factory() as db:
            return await db.get(Scan, self.scan_id)

    async def await_state(self, state, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            scan = await self.scan()
            if scan.status.value == state:
                return scan
            await asyncio.sleep(0.1)
        raise AssertionError(f"persisted terminal/state {state} not reached: {scan.status.value}")

    def contexts(self):
        path = Path(self.env["WORKER_WORKSPACE_ROOT"]) / "contexts.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    async def kill_running_worker(self):
        first = self.worker("killed", "block")
        running = await self.await_state("running")
        deadline = time.monotonic() + 10
        while not self.contexts() and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        assert self.contexts(), "worker must reach source boundary after persisted running"
        assert self.command("XPENDING", self.stream, "scanforge-workers")[0] == 1
        first.kill()
        assert first.wait(timeout=5) == -signal.SIGKILL
        assert (await self.scan()).status.value == "running"
        return running

    async def wait_lease_expiry(self, scan):
        # Real elapsed time, never mutate persisted lifecycle state to simulate expiry.
        seconds = (scan.lease_expires_at - datetime.now(UTC)).total_seconds()
        await asyncio.sleep(max(0, seconds) + 0.1)

    def maintenance(self):
        process = self.processes.start("maintenance", [self.python,
            str(SUPPORT / "worker_process.py"), "maintenance"], self.env)
        assert process.wait(timeout=20) == 0

    async def counts(self):
        async with self.factory() as db:
            return {table: (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
                    for table in ("scans", "findings", "finding_instances", "finding_events",
                                  "scanner_runs", "scan_completion_receipts")}

    async def await_redis(self, predicate, message, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.1)
        raise AssertionError(message)


async def test_sigkill_recovery_completed_and_duplicate_delivery_is_inert(recovery):
    r = recovery
    original_delivery = r.command("XRANGE", r.stream, "-", "+")[0][1]
    running = await r.kill_running_worker()
    await r.wait_lease_expiry(running)
    # Without maintenance or a replacement consumer, expiry alone cannot recover the scan.
    with pytest.raises(AssertionError, match="persisted terminal/state completed not reached"):
        await r.await_state("completed", timeout=3)
    assert r.command("XPENDING", r.stream, "scanforge-workers")[0] == 1
    if os.environ.get("RECOVERY_DISABLE_RECLAIM") == "1":
        await r.await_state("completed", timeout=3)
        pytest.fail("disabled recovery unexpectedly completed")
    r.maintenance()
    assert r.command("XPENDING", r.stream, "scanforge-workers")[0] == 0
    assert r.command("XLEN", r.stream) == 1
    r.worker("replacement", "success")
    completed = await r.await_state("completed")
    assert completed.current_attempt_id != running.current_attempt_id
    assert completed.worker_incarnation_id != running.worker_incarnation_id
    assert completed.execution_revision == running.execution_revision + 1
    assert completed.worker_principal_id == r.principal
    async with httpx.AsyncClient() as client:
        stale = await client.patch(
            f"{r.env['API_BASE_URL']}/api/v1/internal/scans/{r.scan_id}/status",
            json={"status": "failed"}, headers={
                "X-Worker-Credential": r.env["WORKER_CREDENTIAL"],
                "X-Scan-Attempt-Id": running.current_attempt_id,
                "X-Scan-Execution-Revision": str(running.execution_revision),
                "X-Scan-Worker-Incarnation-Id": running.worker_incarnation_id,
            })
    assert stale.status_code == 409
    for context in r.contexts():
        assert {key: context[key] for key in r.identity} == r.identity
    assert r.contexts()[-1]["attempt_id"] == completed.current_attempt_id
    counts = await r.counts()
    assert counts == {"scans": 1, "findings": 1, "finding_instances": 1, "finding_events": 0,
                      "scanner_runs": 1, "scan_completion_receipts": 1}
    # Replay the same Redis delivery after completion, including untrusted context hints.
    r.command("XADD", r.stream, "*", *original_delivery)
    await r.await_redis(lambda: r.command("XLEN", r.stream) == 0, "terminal replay was not acknowledged")
    assert (await r.scan()).status.value == "completed"
    assert await r.counts() == counts
    assert len(r.contexts()) == 2, "terminal replay must not rescan or rewrite history"
    assert r.command("XLEN", r.stream) == 0
    assert r.command("XLEN", r.stream + ":dlq") == 0
    assert r.command("GET", f"{r.stream}:job:{r.scan_id}:retries") is None


async def test_sigkill_recovery_preserves_three_failure_dlq_ceiling(recovery):
    r = recovery
    running = await r.kill_running_worker()
    await r.wait_lease_expiry(running)
    r.maintenance()
    r.worker("failing-replacement", "fail")
    retry_key = f"{r.stream}:job:{r.scan_id}:retries"
    # Production delays (30/60s) and execution leases (120s) are not shortened.
    deadline = time.monotonic() + 300
    seen = set()
    while time.monotonic() < deadline:
        count = int(r.command("GET", retry_key) or 0)
        seen.add(count)
        assert count <= 3
        if r.command("XLEN", r.stream + ":dlq"):
            break
        await asyncio.sleep(0.5)
    assert {1, 2, 3} <= seen
    assert r.command("XLEN", r.stream + ":dlq") == 1
    failed = await r.await_state("failed")
    assert failed.error_message.startswith("Max retries exceeded:")
    assert failed.execution_revision == running.execution_revision + 3
    assert len(r.contexts()) == 4
    assert len({c["attempt_id"] for c in r.contexts()}) == 4
    for context in r.contexts():
        assert {key: context[key] for key in r.identity} == r.identity
    assert await r.counts() == {"scans": 1, "findings": 0, "finding_instances": 0,
                               "finding_events": 0, "scanner_runs": 0, "scan_completion_receipts": 0}
    assert r.command("XPENDING", r.stream, "scanforge-workers")[0] == 0
    assert r.command("XLEN", r.stream) == 0
    assert r.command("ZCARD", r.stream + ":retry") == 0
    await asyncio.sleep(2)
    assert int(r.command("GET", retry_key)) == 3
    assert r.command("XLEN", r.stream + ":dlq") == 1
