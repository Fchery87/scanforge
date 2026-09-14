"""R05 scope-safe disappearance regressions.

Absence-based disappearance must never make a finding appear fixed from a
partial or non-comparable scan.  These cases run against a real database
session (SQLite here; the same regressions run on disposable PostgreSQL
through test_r05_postgres_disappearance_gates with R05_POSTGRES_URL set).
"""
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import CHAR, TypeDecorator

from app.db.base import Base
from app.db.enums import MemberRole, ScanStatus
from app.db.models import (
    Finding,
    FindingEvent,
    Organization,
    OrganizationMember,
    Project,
    Repository,
    Scan,
    ScannerRun,
    User,
)
from app.services.findings import FindingService


@compiles(PGUUID, "sqlite")
def _pg_uuid_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):  # noqa: ARG001
    return "VARCHAR(45)"


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR())

    def bind_processor(self, dialect):
        if dialect.name == "postgresql":
            return None

        def process(value):
            if value is None:
                return None
            return value if isinstance(value, str) else value.hex

        return process


def _downcast_postgres_uuid_columns() -> None:
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_downcast_postgres_uuid_columns()

FULL_HEALTH = {
    "expected": ["trivy", "gitleaks"],
    "completed": ["trivy", "gitleaks"],
    "failed": [],
    "missing": [],
    "complete": True,
}
MAIN = "refs/heads/main"
DEV = "refs/heads/dev"
OK_RUNS = (("trivy", "completed"), ("gitleaks", "completed"))


def _health(**overrides):
    health = dict(FULL_HEALTH)
    health.update(overrides)
    return {"scanner_health": health}


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    _downcast_postgres_uuid_columns()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def pg_session():
    url = os.getenv("R05_POSTGRES_URL")
    if not url:
        pytest.skip("set R05_POSTGRES_URL to a disposable PostgreSQL database")
    engine = create_async_engine(url)
    _downcast_postgres_uuid_columns()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _seed_repo(session):
    user_id = uuid4()
    org_id, project_id, repo_id = (uuid4() for _ in range(3))
    member = User(
        id=str(user_id), auth_provider_user_id=f"ap-{user_id}", email=f"{user_id}@example.com"
    )
    session.add(member)
    await session.flush()
    session.add(
        Organization(id=str(org_id), name="org", slug=f"org-{org_id}", created_by_user_id=str(user_id))
    )
    await session.flush()
    session.add(
        Project(
            id=str(project_id),
            organization_id=str(org_id),
            name="p",
            slug=f"p-{project_id}",
            created_by_user_id=str(user_id),
        )
    )
    await session.flush()
    session.add(
        Repository(
            id=str(repo_id),
            project_id=str(project_id),
            provider="github",
            owner_name="o",
            repo_name="r",
            full_name="o/r",
        )
    )
    await session.flush()
    session.add(
        OrganizationMember(
            id=str(uuid4()), organization_id=str(org_id), user_id=str(user_id), role=MemberRole.OWNER
        )
    )
    await session.flush()
    await session.commit()
    return str(repo_id), str(project_id), user_id


async def _seed_finding(session, repo_id, project_id, fingerprint, *, status="open"):
    now = datetime.now(UTC)
    finding = Finding(
        project_id=project_id,
        repository_id=repo_id,
        category="vulnerability",
        severity="high",
        status=status,
        title="t",
        description=None,
        canonical_fingerprint=fingerprint,
        primary_scanner="trivy",
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(finding)
    await session.flush()
    await session.commit()
    return finding


async def _seed_scan(session, repo_id, project_id, *, branch=MAIN, commit, scan_type="full", created_at=None):
    scan = Scan(
        id=str(uuid4()),
        project_id=project_id,
        repository_id=repo_id,
        trigger_type="manual",
        scan_type=scan_type,
        status=ScanStatus.RUNNING,
        branch_name=branch,
        commit_sha=commit,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(scan)
    await session.flush()
    await session.commit()
    return scan


async def _observe(session, repo_id, project_id, fingerprint, *, branch=MAIN, commit):
    """Positive evidence: a comparable scan that reports the finding."""
    service = FindingService(session)
    scan = await _seed_scan(session, repo_id, project_id, branch=branch, commit=commit)
    await service.upsert_from_scan(
        scan_id=str(scan.id),
        repository_id=repo_id,
        project_id=project_id,
        normalized_findings=[
            {
                "category": "vulnerability",
                "severity": "high",
                "title": "t",
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "trivy",
                "confidence_score": 0.9,
            }
        ],
    )
    return service


async def _absence(
    service,
    repo_id,
    project_id,
    *,
    branch=MAIN,
    commit,
    summary=None,
    run_statuses=OK_RUNS,
    created_at=None,
):
    """One absence evaluation for a fresh scan, mirroring completion.

    Completion persists scanner-run evidence in the same transaction before
    lifecycle evaluation; the helper commits the same committed evidence.
    """
    session = service.db
    scan = await _seed_scan(
        session, repo_id, project_id, branch=branch, commit=commit, created_at=created_at
    )
    for name, status in run_statuses:
        session.add(
            ScannerRun(
                id=str(uuid4()), scan_id=str(scan.id), scanner_name=name, status=ScanStatus(status)
            )
        )
        # One row per flush keeps inserts single-row on both dialects.
        await session.flush()
    return await service.mark_not_observed_after_scan(
        repository_id=repo_id,
        scan_id=str(scan.id),
        seen_fingerprints=set(),
        scan_summary=summary or _health(),
    )


async def _reload(session, finding):
    result = await session.execute(select(Finding).where(Finding.id == finding.id))
    return result.scalar_one()


async def _events(session, finding):
    result = await session.execute(select(FindingEvent).where(FindingEvent.finding_id == finding.id))
    return sorted(result.scalars().all(), key=lambda event: event.created_at)


@pytest.mark.asyncio
async def test_non_comparable_scan_does_not_disappear_finding(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-noncomparable"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    updated = await _absence(
        service,
        repo_id,
        project_id,
        commit="c" * 40,
        summary=_health(complete=False, failed=["gitleaks"]),
        run_statuses=(("trivy", "completed"), ("gitleaks", "failed")),
    )

    assert updated == 0
    after = await _reload(db_session, finding)
    assert after.status == "open"
    assert after.metadata_json.get("observed_branches", []) == [MAIN]
    series = after.metadata_json.get("absence_series", {}).get(MAIN, {}).get("qualifying_absences")
    assert series == []


@pytest.mark.asyncio
async def test_diff_scan_does_not_disappear_finding(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-diff"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    updated = await _absence(service, repo_id, project_id, commit="d" * 40, run_statuses=())

    assert updated == 0
    assert (await _reload(db_session, finding)).status == "open"


@pytest.mark.asyncio
async def test_two_qualifying_absences_move_finding_to_fixed(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-qualifying"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    assert await _absence(service, repo_id, project_id, commit="a" * 40) == 1
    assert (await _reload(db_session, finding)).status == "not_observed"
    assert await _absence(service, repo_id, project_id, commit="b" * 40) == 1
    assert (await _reload(db_session, finding)).status == "fixed"

    events = await _events(db_session, finding)
    assert [event.event_type for event in events] == ["marked_not_observed", "fixed"]
    assert events[0].metadata_json["qualifying_absences"] == 1
    assert events[1].metadata_json["qualifying_absences"] == 2
    assert events[1].metadata_json["policy"] == "scan-evidence-v1"
    assert events[1].metadata_json["threshold"] == 2


@pytest.mark.asyncio
async def test_same_commit_rerun_does_not_close_finding(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-rerun"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    assert await _absence(service, repo_id, project_id, commit="a" * 40) == 1
    assert await _absence(service, repo_id, project_id, commit="a" * 40) == 0

    after = await _reload(db_session, finding)
    assert after.status == "not_observed"


@pytest.mark.asyncio
async def test_presence_between_absences_resets_series(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-straddle"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    await _absence(service, repo_id, project_id, commit="a" * 40)
    await _observe(db_session, repo_id, project_id, fingerprint, commit="m" * 40)
    await _absence(service, repo_id, project_id, commit="b" * 40)

    after = await _reload(db_session, finding)
    # Presence invalidated the straddling absence and reappearance reopened
    # the machine state; the following absence starts a fresh series.
    assert after.status == "not_observed"
    assert after.metadata_json["absence_series"][MAIN]["qualifying_absences"] == [
        {
            "scan_id": after.metadata_json["absence_series"][MAIN]["qualifying_absences"][0]["scan_id"],
            "commit_sha": "b" * 40,
        }
    ]


@pytest.mark.asyncio
async def test_manual_reopen_blocks_old_and_requires_new_scans(db_session):
    repo_id, project_id, owner_id = await _seed_repo(db_session)
    fingerprint = "fp-reopen"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    await _absence(service, repo_id, project_id, commit="a" * 40)
    assert (await _reload(db_session, finding)).status == "not_observed"

    checkpoint = datetime.now(UTC)
    reopened = await service.reopen(finding.id, str(owner_id), "Still reproducible")
    assert reopened.status == "open"
    assert reopened.metadata_json.get("manual_reopen_checkpoint") is not None
    series = reopened.metadata_json["absence_series"][MAIN]["qualifying_absences"]
    assert series == []

    # A scan issued before the reopen decision cannot reclose the finding.
    stale = await _absence(
        service, repo_id, project_id, commit="c" * 40, created_at=checkpoint - timedelta(minutes=5)
    )
    assert stale == 0
    assert (await _reload(db_session, finding)).status == "open"

    # A new scan issued after the decision starts a fresh qualifying series.
    fresh = await _absence(
        service, repo_id, project_id, commit="d" * 40, created_at=checkpoint + timedelta(minutes=5)
    )
    assert fresh == 1
    assert (await _reload(db_session, finding)).status == "not_observed"


@pytest.mark.asyncio
async def test_cross_branch_absence_is_ignored_until_all_branches_qualify(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-branches"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    await _observe(db_session, repo_id, project_id, fingerprint, branch=MAIN, commit="0" * 40)
    service = await _observe(db_session, repo_id, project_id, fingerprint, branch=DEV, commit="1" * 40)

    # Two qualifying absences on main alone: dev obligation is unresolved.
    await _absence(service, repo_id, project_id, branch=MAIN, commit="a" * 40)
    await _absence(service, repo_id, project_id, branch=MAIN, commit="b" * 40)
    after_main = await _reload(db_session, finding)
    assert after_main.status == "open"
    assert len(after_main.metadata_json["absence_series"][MAIN]["qualifying_absences"]) == 2

    # Dev catches up: first absence -> not_observed, second -> fixed.
    await _absence(service, repo_id, project_id, branch=DEV, commit="c" * 40)
    assert (await _reload(db_session, finding)).status == "not_observed"
    await _absence(service, repo_id, project_id, branch=DEV, commit="e" * 40)
    assert (await _reload(db_session, finding)).status == "fixed"


@pytest.mark.asyncio
async def test_absence_on_branch_where_finding_was_never_seen_is_ignored(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-foreign-branch"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, branch=MAIN, commit="0" * 40)

    await _absence(service, repo_id, project_id, branch=DEV, commit="a" * 40)
    await _absence(service, repo_id, project_id, branch=DEV, commit="b" * 40)

    after = await _reload(db_session, finding)
    assert after.status == "open"
    assert after.metadata_json.get("absence_series", {}).get(DEV) is None


@pytest.mark.asyncio
async def test_finding_without_branch_provenance_cannot_disappear(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-legacy"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = FindingService(db_session)

    # No presence was ever recorded through the lifecycle path: provenance unknown.
    await _absence(service, repo_id, project_id, commit="a" * 40)
    await _absence(service, repo_id, project_id, commit="b" * 40)

    after = await _reload(db_session, finding)
    assert after.status == "open"


@pytest.mark.asyncio
async def test_scan_without_committed_context_is_ineligible(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-noscan"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    updated = await service.mark_not_observed_after_scan(
        repository_id=repo_id,
        scan_id=str(uuid4()),
        seen_fingerprints=set(),
        scan_summary=_health(),
    )

    assert updated == 0
    assert (await _reload(db_session, finding)).status == "open"


@pytest.mark.asyncio
async def test_scan_without_committed_scanner_runs_is_ineligible(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    fingerprint = "fp-noruns"
    finding = await _seed_finding(db_session, repo_id, project_id, fingerprint)
    service = await _observe(db_session, repo_id, project_id, fingerprint, commit="0" * 40)

    # Health summary claims complete coverage but no scanner run ever
    # committed: missing evidence is ineligible, never assumed clean.
    updated = await _absence(service, repo_id, project_id, commit="a" * 40, run_statuses=())

    assert updated == 0
    assert (await _reload(db_session, finding)).status == "open"


@pytest.mark.asyncio
async def test_r05_postgres_disappearance_gates(pg_session):
    """Ordered-series regressions against real PostgreSQL (required evidence)."""
    repo_id, project_id, _ = await _seed_repo(pg_session)
    fingerprint = "fp-pg"
    finding = await _seed_finding(pg_session, repo_id, project_id, fingerprint)
    service = await _observe(pg_session, repo_id, project_id, fingerprint, commit="0" * 40)

    assert await _absence(service, repo_id, project_id, commit="a" * 40) == 1
    assert (await _reload(pg_session, finding)).status == "not_observed"
    assert await _absence(service, repo_id, project_id, commit="b" * 40) == 1
    assert (await _reload(pg_session, finding)).status == "fixed"
