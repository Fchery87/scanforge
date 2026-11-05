"""M07 acceptance on real PostgreSQL (P1.3, #35).

Every test here needs a disposable PostgreSQL (``DISPATCH_POSTGRES_URL``,
``R04_POSTGRES_URL`` or local PostgreSQL binaries) and skips otherwise.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_scan_dispatch import (
    InMemoryUpstashQueue,
    _disposable_postgres_url,
    _seed_org_project_repo,
)

from app.db.enums import DispatchObligationStatus
from app.db.models import Scan, ScanDispatchObligation
from app.schemas.scans import ScanCreate
from app.services.scan_dispatch import ScanDispatchService
from app.services.scans import ScanService

TERMINAL = {
    DispatchObligationStatus.DISPATCHED.value,
    DispatchObligationStatus.SUPERSEDED.value,
    DispatchObligationStatus.CANCELED.value,
}


@pytest.fixture(scope="module")
def pg_url():
    with _disposable_postgres_url() as url:
        yield url


@pytest_asyncio.fixture
async def factory(pg_url):
    engine = create_async_engine(pg_url, poolclass=NullPool, future=True)
    try:
        # Disposable database only: start every test from an empty tenant graph.
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations, users, repositories CASCADE"))
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


def _webhook(repo, sha: str, *, branch: str = "main") -> ScanCreate:
    return ScanCreate(
        repository_id=UUID(str(repo.id)),
        trigger_type="webhook",
        branch_name=branch,
        commit_sha=sha,
        scan_type="full",
    )


def _manual(repo, sha: str, key: str | None = None) -> ScanCreate:
    return ScanCreate(
        repository_id=UUID(str(repo.id)),
        trigger_type="manual",
        branch_name="main",
        commit_sha=sha,
        scan_type="full",
        idempotency_key=key,
    )


async def _create_in_own_session(factory, repo, data, user_id=None, **kwargs) -> str:
    async with factory() as session:
        scan, _, _ = await ScanService(session).create(UUID(str(repo.id)), data, user_id, **kwargs)
        return str(scan.id)


async def _push(factory, repo, sha: str) -> str:
    return await _create_in_own_session(factory, repo, _webhook(repo, sha), ancestry_relation="ahead")


async def _drain(factory, queue, name: str, *, now=None) -> list[str]:
    dispatched: list[str] = []
    async with factory() as session:
        svc = ScanDispatchService(session, queue=queue)
        while True:
            batch = await svc.dispatch_due_obligations(lease_owner=name, limit=3, now=now)
            if not batch:
                return dispatched
            dispatched.extend(str(r.scan_id) for r in batch if r.dispatched)


async def _obligations(factory, org_id) -> list[ScanDispatchObligation]:
    async with factory() as session:
        return list(
            (
                await session.execute(
                    select(ScanDispatchObligation).where(
                        ScanDispatchObligation.organization_id == str(org_id)
                    )
                )
            )
            .scalars()
            .all()
        )


async def _scan_count(factory, repo) -> int:
    async with factory() as session:
        return (
            await session.execute(
                select(func.count()).select_from(Scan).where(Scan.repository_id == str(repo.id))
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_concurrent_duplicate_automatic_triggers_yield_one_scan_and_one_obligation(factory):
    async with factory() as seed:
        org, _p, repo, _u = await _seed_org_project_repo(seed)

    ids = [str(i) for i in await asyncio.gather(*[_push(factory, repo, "a" * 40) for _ in range(8)])]

    assert len(set(ids)) == 1
    obligations = await _obligations(factory, org.id)
    assert [str(o.scan_id) for o in obligations] == [ids[0]]
    assert await _scan_count(factory, repo) == 1


@pytest.mark.asyncio
async def test_concurrent_manual_requests_split_idempotent_duplicates_from_deliberate_reruns(factory):
    async with factory() as seed:
        org, _p, repo, user = await _seed_org_project_repo(seed)
    uid = UUID(str(user.id))

    results = await asyncio.gather(
        *[_create_in_own_session(factory, repo, _manual(repo, "a" * 40, "req-1"), uid) for _ in range(6)],
        *[_create_in_own_session(factory, repo, _manual(repo, "a" * 40), uid) for _ in range(3)],
    )

    assert len(set(results[:6])) == 1
    assert len(set(results[6:])) == 3
    assert not set(results[:6]) & set(results[6:])
    assert len(await _obligations(factory, org.id)) == 4


@pytest.mark.asyncio
async def test_scan_and_obligation_commit_or_roll_back_together(factory, monkeypatch):
    async with factory() as seed:
        org, _p, repo, _u = await _seed_org_project_repo(seed)

    async def boom(*_args, **_kwargs):
        raise RuntimeError("obligation insert failed")

    monkeypatch.setattr(ScanDispatchService, "create_obligation_for_scan", boom)
    async with factory() as session:
        with pytest.raises(RuntimeError):
            await ScanService(session).create(
                UUID(str(repo.id)), _webhook(repo, "b" * 40), None, ancestry_relation="ahead"
            )
        await session.rollback()

    assert await _scan_count(factory, repo) == 0
    assert await _obligations(factory, org.id) == []


@pytest.mark.asyncio
async def test_dispatcher_restart_reclaims_expired_lease_and_delivers_once(factory):
    async with factory() as seed:
        org, _p, repo, _u = await _seed_org_project_repo(seed)
    scan_id = await _push(factory, repo, "c" * 40)
    t0 = datetime.now(UTC)
    queue = InMemoryUpstashQueue()

    # Dispatcher 1 claims, then dies before enqueueing anything.
    async with factory() as session:
        claimed = await ScanDispatchService(session, queue=queue).claim_due_obligations(
            lease_owner="dead", lease_seconds=30, now=t0
        )
    assert [str(o.scan_id) for o in claimed] == [scan_id]

    # While the lease is live nobody else may take it; after expiry a restart reclaims it.
    assert await _drain(factory, queue, "early", now=t0 + timedelta(seconds=5)) == []
    assert await _drain(factory, queue, "restarted", now=t0 + timedelta(seconds=31)) == [scan_id]

    assert len(queue.streams.get(f"queue:scans:{org.id}", [])) == 1
    (ob,) = await _obligations(factory, org.id)
    assert ob.status == DispatchObligationStatus.DISPATCHED.value
    assert ob.attempt_count == 2


@pytest.mark.asyncio
async def test_burst_with_concurrent_dispatchers_leaves_no_stranded_obligation(factory):
    async with factory() as seed:
        org, _p, repo, user = await _seed_org_project_repo(seed)
    queue = InMemoryUpstashQueue()

    triggers = [_push(factory, repo, f"{i:040x}") for i in range(1, 11)]
    triggers += [_push(factory, repo, f"{i:040x}") for i in (2, 5, 9)]  # duplicate deliveries
    triggers.append(
        _create_in_own_session(factory, repo, _manual(repo, "1" * 40), UUID(str(user.id)))
    )
    created = await asyncio.gather(*triggers)
    manual_scan_id = created[-1]

    # Dispatchers also run while a second wave is still arriving.
    await asyncio.gather(
        *[_drain(factory, queue, f"d{i}") for i in range(3)],
        *[_push(factory, repo, f"{i:040x}") for i in (11, 12)],
    )
    await _drain(factory, queue, "sweeper")

    obligations = await _obligations(factory, org.id)
    assert len(obligations) == 13  # 12 distinct automatic + 1 manual; duplicates collapsed
    assert [o.status for o in obligations if o.status not in TERMINAL] == []

    dispatched = {
        str(o.scan_id) for o in obligations if o.status == DispatchObligationStatus.DISPATCHED.value
    }
    assert manual_scan_id in dispatched
    stream = queue.streams.get(f"queue:scans:{org.id}", [])
    assert len(stream) == len(dispatched)
