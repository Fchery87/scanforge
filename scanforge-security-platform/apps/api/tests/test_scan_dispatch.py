from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import socket
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import CHAR, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from app.clients.queue import QueueClient
from app.core.error_messages import GENERIC_QUEUE_ERROR
from app.db.base import Base
from app.db.enums import DispatchObligationStatus
from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import (
    Organization,
    Project,
    Repository,
    ScanDispatchObligation,
    User,
)
from app.schemas.scans import ScanCreate
from app.services.scan_dispatch import (
    ScanCapacityExceededError,
    ScanDispatchService,
    compute_automatic_business_identity,
)
from app.services.scan_lifecycle import ScanLifecycleService
from app.services.scans import ScanService


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    return "JSON"


@compiles(INET, "sqlite")
def _compile_inet_sqlite(_type, _compiler, **_kw):
    return "VARCHAR(45)"


class _SQLiteUUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, UUID) else UUID(str(value))
        return str(value)

    def process_result_value(self, value, _dialect):
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(str(value))


def _patch_uuid_columns_for_sqlite() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.type.__class__.__name__ == "UUID":
                column.type = _SQLiteUUID()


class InMemoryUpstashQueue(QueueClient):
    """Stateful Upstash Redis REST emulator supporting SET NX EX, GET, DEL, XADD, and XLEN."""

    def __init__(self) -> None:
        super().__init__(redis_url="https://upstash.local", redis_token="test-token")
        self.kv: dict[str, str] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.outage: bool = False
        self.command_log: list[tuple] = []
        self._lock = asyncio.Lock()
        self._seq = 0

    async def _command(self, *args: str | int | float) -> dict:
        async with self._lock:
            self.command_log.append(tuple(args))
            if self.outage:
                raise RuntimeError("Upstash Redis connection refused: secret-redis-token-xyz")

            op = str(args[0]).upper()
            if op == "SET":
                key = str(args[1])
                val = str(args[2])
                flags = {str(a).upper() for a in args[3:]}
                if "NX" in flags and key in self.kv:
                    return {"result": None}
                self.kv[key] = val
                return {"result": "OK"}
            if op == "GET":
                key = str(args[1])
                return {"result": self.kv.get(key)}
            if op == "DEL":
                removed = 0
                for key in args[1:]:
                    if str(key) in self.kv:
                        del self.kv[str(key)]
                        removed += 1
                return {"result": removed}
            if op == "XADD":
                stream = str(args[1])
                fields_raw = args[3:]
                fields = {
                    str(fields_raw[i]): str(fields_raw[i + 1])
                    for i in range(0, len(fields_raw), 2)
                }
                self._seq += 1
                entry_id = f"1760000000000-{self._seq}"
                self.streams.setdefault(stream, []).append((entry_id, fields))
                return {"result": entry_id}
            if op == "XLEN":
                stream = str(args[1])
                return {"result": len(self.streams.get(stream, []))}
            raise NotImplementedError(f"Unsupported command in test emulator: {op}")


@pytest_asyncio.fixture
async def db_session():
    _patch_uuid_columns_for_sqlite()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


async def _seed_org_project_repo(session: AsyncSession) -> tuple[Organization, Project, Repository, User]:
    user = User(
        id=str(uuid4()),
        email=f"dev-{uuid4().hex[:6]}@example.com",
        name="Dev User",
        auth_provider_user_id=f"user_{uuid4().hex[:8]}",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    org = Organization(
        id=str(uuid4()),
        name="Dispatch Org",
        slug=f"dispatch-org-{uuid4().hex[:6]}",
        created_by_user_id=user.id,
    )
    session.add(org)
    await session.flush()

    project = Project(
        id=str(uuid4()),
        organization_id=org.id,
        name="Core Platform",
        slug=f"core-platform-{uuid4().hex[:6]}",
        created_by_user_id=user.id,
    )
    session.add(project)
    await session.flush()

    repo = Repository(
        id=str(uuid4()),
        project_id=project.id,
        provider="github",
        external_repo_id=str(uuid4().int % 1_000_000),
        owner_name="acme",
        repo_name="core-platform",
        full_name="acme/core-platform",
        default_branch="main",
        is_active=True,
        lifecycle_state="connected",
    )
    session.add(repo)
    await session.commit()
    return org, project, repo, user


SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40


@pytest.mark.asyncio
async def test_queue_outage_retains_awaiting_dispatch_and_recovers_on_retry(db_session: AsyncSession):
    org, _project, repo, user = await _seed_org_project_repo(db_session)
    queue = InMemoryUpstashQueue()
    queue.outage = True

    lifecycle = ScanLifecycleService(db_session, queue=queue)
    scan = await lifecycle.create_manual_scan(
        org_id=UUID(str(org.id)),
        data=ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        user_id=UUID(str(user.id)),
    )

    assert scan.status == ScanStatusEnum.QUEUED
    assert scan.dispatch_state == DispatchObligationStatus.AWAITING_DISPATCH.value
    assert scan.error_message == GENERIC_QUEUE_ERROR
    assert "secret-redis-token-xyz" not in (scan.error_message or "")

    obligation = (
        await db_session.execute(
            select(ScanDispatchObligation).where(ScanDispatchObligation.scan_id == str(scan.id))
        )
    ).scalar_one()
    assert obligation.status == DispatchObligationStatus.AWAITING_DISPATCH.value
    assert obligation.attempt_count == 1
    assert obligation.last_error == GENERIC_QUEUE_ERROR
    assert queue.streams.get(f"queue:scans:{org.id}", []) == []

    # Queue recovers; dispatcher retries after backoff window.
    queue.outage = False
    dispatcher = ScanDispatchService(db_session, queue=queue)
    results = await dispatcher.dispatch_due_obligations(
        lease_owner="recovery-worker",
        now=datetime.now(UTC) + timedelta(seconds=5),
    )
    assert len(results) == 1
    assert results[0].dispatched is True
    assert results[0].status == DispatchObligationStatus.DISPATCHED.value

    await db_session.refresh(scan)
    await db_session.refresh(obligation)
    assert scan.status == ScanStatusEnum.QUEUED
    assert scan.dispatch_state == DispatchObligationStatus.DISPATCHED.value
    assert scan.error_message is None
    assert obligation.status == DispatchObligationStatus.DISPATCHED.value
    assert obligation.dispatched_at is not None

    stream_entries = queue.streams.get(f"queue:scans:{org.id}", [])
    assert len(stream_entries) == 1
    payload = json.loads(stream_entries[0][1]["job"])
    assert payload["job_id"] == str(scan.id)
    assert payload["payload"]["scan_id"] == str(scan.id)


@pytest.mark.asyncio
async def test_crash_after_queue_delivery_before_ack_is_idempotent_on_reclaim(db_session: AsyncSession):
    org, _project, repo, user = await _seed_org_project_repo(db_session)
    queue = InMemoryUpstashQueue()

    scan_service = ScanService(db_session)
    scan, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        UUID(str(user.id)),
    )

    t0 = datetime.now(UTC)

    def _crash_after_enqueue(_obligation: ScanDispatchObligation) -> None:
        raise RuntimeError("Simulated process crash after XADD before DB acknowledgement")

    crashing_dispatcher = ScanDispatchService(
        db_session,
        queue=queue,
        lease_seconds=15,
        after_enqueue_before_ack=_crash_after_enqueue,
    )
    with pytest.raises(RuntimeError, match="Simulated process crash"):
        await crashing_dispatcher.dispatch_due_obligations(
            lease_owner="dispatcher-crashed",
            now=t0,
        )

    # Queue already received the message and dedupe key, but DB obligation is still leased!
    stream_entries = queue.streams.get(f"queue:scans:{org.id}", [])
    assert len(stream_entries) == 1
    assert await queue.has_dedupe_marker(org.id, str(scan.id)) is True

    obligation = (
        await db_session.execute(
            select(ScanDispatchObligation).where(ScanDispatchObligation.scan_id == str(scan.id))
        )
    ).scalar_one()
    assert obligation.status == DispatchObligationStatus.LEASED.value
    assert obligation.lease_owner == "dispatcher-crashed"

    # Before lease expiry, another dispatcher cannot steal the leased obligation.
    healthy_dispatcher = ScanDispatchService(db_session, queue=queue, lease_seconds=15)
    early_results = await healthy_dispatcher.dispatch_due_obligations(
        lease_owner="dispatcher-healthy",
        now=t0 + timedelta(seconds=5),
    )
    assert early_results == []

    # After lease expiry, healthy dispatcher reclaims, deduplicates against Redis, and acknowledges DB.
    reclaimed_results = await healthy_dispatcher.dispatch_due_obligations(
        lease_owner="dispatcher-healthy",
        now=t0 + timedelta(seconds=20),
    )
    assert len(reclaimed_results) == 1
    assert reclaimed_results[0].dispatched is True
    assert reclaimed_results[0].status == DispatchObligationStatus.DISPATCHED.value

    # Still only ONE stream entry in Redis!
    assert len(queue.streams.get(f"queue:scans:{org.id}", [])) == 1

    await db_session.refresh(obligation)
    await db_session.refresh(scan)
    assert obligation.status == DispatchObligationStatus.DISPATCHED.value
    assert obligation.attempt_count == 2
    assert scan.dispatch_state == DispatchObligationStatus.DISPATCHED.value


@pytest.mark.asyncio
async def test_automatic_business_identity_and_manual_idempotency_vs_deliberate_rerun(
    db_session: AsyncSession,
):
    org, _project, repo, user = await _seed_org_project_repo(db_session)
    scan_service = ScanService(db_session)

    # 1. Equivalent automatic triggers return the same authoritative scan.
    auto_1, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="refs/heads/main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        None,
    )
    auto_2, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        None,
    )
    assert auto_1.id == auto_2.id

    # 2. Manual requests with the same idempotency_key deduplicate, while deliberate reruns create new scans.
    manual_idem_1, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
            idempotency_key="req-key-001",
        ),
        UUID(str(user.id)),
    )
    manual_idem_2, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
            idempotency_key="req-key-001",
        ),
        UUID(str(user.id)),
    )
    assert manual_idem_1.id == manual_idem_2.id
    assert manual_idem_1.id != auto_1.id

    # Deliberate manual rerun on the exact same commit without matching idempotency key creates a new scan.
    manual_rerun, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        UUID(str(user.id)),
    )
    assert manual_rerun.id != manual_idem_1.id
    assert manual_rerun.id != auto_1.id

    # Verify automatic business identity changes when coverage/generation context changes.
    key_gen1 = compute_automatic_business_identity(
        organization_id=org.id,
        repository_id=repo.id,
        trigger_type="webhook",
        scan_type="full",
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        commit_sha=SHA_A,
        expected_scanners=["semgrep", "trivy"],
    )
    key_gen2 = compute_automatic_business_identity(
        organization_id=org.id,
        repository_id=repo.id,
        trigger_type="webhook",
        scan_type="full",
        full_ref_name="refs/heads/main",
        branch_generation_number=2,
        commit_sha=SHA_A,
        expected_scanners=["semgrep", "trivy"],
    )
    assert key_gen1 != key_gen2


@pytest.mark.asyncio
async def test_bounded_admission_and_explicit_supersession_of_unstarted_automatic_work(
    db_session: AsyncSession,
):
    _org, _project, repo, user = await _seed_org_project_repo(db_session)
    scan_service = ScanService(db_session)

    # Seed a manual scan and a running automatic scan on main; neither may ever be coalesced/superseded.
    manual_scan, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="manual",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        UUID(str(user.id)),
    )

    auto_scan_1, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="main",
            commit_sha=SHA_A,
            scan_type="full",
        ),
        None,
        ancestry_relation="ahead",
    )

    # Burst push 2 (descendant SHA_B in same generation) supersedes unstarted auto_scan_1, not manual_scan!
    auto_scan_2, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="main",
            commit_sha=SHA_B,
            scan_type="full",
        ),
        None,
        ancestry_relation="ahead",
    )

    await db_session.refresh(auto_scan_1)
    await db_session.refresh(manual_scan)
    assert auto_scan_1.status == ScanStatusEnum.CANCELED
    assert auto_scan_1.dispatch_state == DispatchObligationStatus.SUPERSEDED.value
    assert str(auto_scan_1.superseded_by_scan_id) == str(auto_scan_2.id)
    assert auto_scan_1.coverage_completeness == "skipped_superseded"
    assert auto_scan_1.closure_eligible is False
    assert auto_scan_1.summary_json["superseded"] is True
    assert len(auto_scan_1.summary_json["skipped_scanners"]) == 7
    assert auto_scan_1.summary_json["fabricated_observations"] is False
    assert manual_scan.status == ScanStatusEnum.QUEUED
    assert manual_scan.dispatch_state == DispatchObligationStatus.AWAITING_DISPATCH.value
    assert manual_scan.superseded_by_scan_id is None

    # A later descendant push must not supersede auto_scan_2 once it is running.
    auto_scan_2.status = ScanStatusEnum.RUNNING
    auto_scan_2.current_attempt_id = "attempt-running-2"
    await db_session.commit()

    auto_scan_3, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="main",
            commit_sha=SHA_C,
            scan_type="full",
        ),
        None,
        ancestry_relation="ahead",
    )
    await db_session.refresh(auto_scan_2)
    assert auto_scan_2.status == ScanStatusEnum.RUNNING
    assert auto_scan_2.superseded_by_scan_id is None

    # Force-push SHA_D starts generation 2 and does NOT supersede auto_scan_3 across a generation boundary!
    auto_scan_4_force, _, _ = await scan_service.create(
        UUID(str(repo.id)),
        ScanCreate(
            repository_id=UUID(str(repo.id)),
            trigger_type="webhook",
            branch_name="main",
            commit_sha=SHA_D,
            scan_type="full",
        ),
        None,
        force_pushed=True,
    )
    await db_session.refresh(auto_scan_3)
    assert auto_scan_4_force.branch_generation_number == 2
    assert auto_scan_3.branch_generation_number == 1
    assert auto_scan_3.superseded_by_scan_id is None
    assert auto_scan_3.dispatch_state == DispatchObligationStatus.AWAITING_DISPATCH.value

    # A queued manual scan remains admitted work after queue delivery succeeds.
    manual_obligation = (
        await db_session.execute(
            select(ScanDispatchObligation).where(ScanDispatchObligation.scan_id == str(manual_scan.id))
        )
    ).scalar_one()
    manual_scan.dispatch_state = DispatchObligationStatus.DISPATCHED.value
    manual_obligation.status = DispatchObligationStatus.DISPATCHED.value
    await db_session.commit()

    # Enforce bounded manual admission before accepting excess manual work.
    with pytest.raises(ScanCapacityExceededError, match="manual scan capacity"):
        await scan_service.create(
            UUID(str(repo.id)),
            ScanCreate(
                repository_id=UUID(str(repo.id)),
                trigger_type="manual",
                branch_name="main",
                commit_sha=SHA_D,
                scan_type="full",
            ),
            UUID(str(user.id)),
            max_pending_manual_per_repo=1,
        )


def _find_pg_bin(name: str) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct
    for candidate in sorted(Path("/usr/lib/postgresql").glob(f"*/bin/{name}"), reverse=True):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


@contextlib.contextmanager
def _disposable_postgres_url():
    configured = os.getenv("DISPATCH_POSTGRES_URL") or os.getenv("R04_POSTGRES_URL")
    if configured:
        yield configured
        return

    initdb = _find_pg_bin("initdb")
    pg_ctl = _find_pg_bin("pg_ctl")
    createdb = _find_pg_bin("createdb")
    if not (initdb and pg_ctl and createdb):
        pytest.skip("PostgreSQL binaries not available for concurrent SKIP LOCKED test")

    temp_root = Path(tempfile.mkdtemp(prefix="scanforge-pg-dispatch-"))
    pgdata = temp_root / "pgdata"
    sockdir = temp_root / "sock"
    sockdir.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = int(s.getsockname()[1])
    user = "scanforge_dispatch_test"
    db_name = "scanforge_dispatch"
    api_dir = Path(__file__).resolve().parents[1]
    alembic_bin = api_dir / ".venv" / "bin" / "alembic"

    try:
        subprocess.run(
            [initdb, "-D", str(pgdata), "-U", user, "--auth=trust", "--no-instructions"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        opts = f"-F -p {port} -h 127.0.0.1 -k {sockdir}"
        subprocess.run(
            [pg_ctl, "-D", str(pgdata), "-l", str(temp_root / "postgres.log"), "-o", opts, "start"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            [createdb, "-h", "127.0.0.1", "-p", str(port), "-U", user, db_name],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        async_url = f"postgresql+asyncpg://{user}@127.0.0.1:{port}/{db_name}"
        env = dict(os.environ)
        env["DATABASE_URL"] = async_url
        env["PYTHONPATH"] = str(api_dir)
        subprocess.run(
            [str(alembic_bin), "-c", "alembic.ini", "upgrade", "head"],
            cwd=api_dir,
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        yield async_url
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(pgdata), "-m", "immediate", "stop"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        shutil.rmtree(temp_root, ignore_errors=True)


@pytest.mark.asyncio
async def test_postgres_concurrent_dispatchers_claim_each_obligation_once_with_zero_stranded():
    with _disposable_postgres_url() as pg_url:
        engine = create_async_engine(pg_url, poolclass=NullPool, future=True)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        try:
            async with session_factory() as seed_session:
                org, _project, repo, user = await _seed_org_project_repo(seed_session)
                scan_service = ScanService(seed_session)
                created_scan_ids: list[str] = []
                for idx in range(6):
                    commit_sha = f"{idx + 1:040x}"
                    scan, _, _ = await scan_service.create(
                        UUID(str(repo.id)),
                        ScanCreate(
                            repository_id=UUID(str(repo.id)),
                            trigger_type="manual",
                            branch_name="main",
                            commit_sha=commit_sha,
                            scan_type="full",
                            idempotency_key=f"concurrent-seed-{idx}",
                        ),
                        UUID(str(user.id)),
                    )
                    created_scan_ids.append(str(scan.id))

            queue = InMemoryUpstashQueue()

            async def _run_dispatcher(worker_name: str) -> list[str]:
                dispatched_ids: list[str] = []
                async with session_factory() as worker_session:
                    svc = ScanDispatchService(worker_session, queue=queue, lease_seconds=30)
                    while True:
                        batch = await svc.dispatch_due_obligations(
                            lease_owner=worker_name,
                            limit=2,
                        )
                        if not batch:
                            break
                        for item in batch:
                            if item.dispatched:
                                dispatched_ids.append(item.scan_id)
                return dispatched_ids

            worker_results = await asyncio.gather(
                _run_dispatcher("pg-dispatcher-1"),
                _run_dispatcher("pg-dispatcher-2"),
                _run_dispatcher("pg-dispatcher-3"),
            )
            all_dispatched = [scan_id for sublist in worker_results for scan_id in sublist]
            assert sorted(all_dispatched) == sorted(created_scan_ids)
            assert len(all_dispatched) == 6

            stream_entries = queue.streams.get(f"queue:scans:{org.id}", [])
            assert len(stream_entries) == 6

            async with session_factory() as check_session:
                obligations = list(
                    (
                        await check_session.execute(
                            select(ScanDispatchObligation).where(
                                ScanDispatchObligation.organization_id == str(org.id)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                assert len(obligations) == 6
                assert all(o.status == DispatchObligationStatus.DISPATCHED.value for o in obligations)
                assert all(o.attempt_count == 1 for o in obligations)
        finally:
            await engine.dispose()
