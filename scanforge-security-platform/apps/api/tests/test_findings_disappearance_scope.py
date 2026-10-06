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
    FindingInstance,
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
def _compile_uuid(_type, _compiler, **_kwargs):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _compile_json(_type, _compiler, **_kwargs):
    return "JSON"


@compiles(INET, "sqlite")
def _compile_inet(_type, _compiler, **_kwargs):
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


def _use_sqlite_uuid_types():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGUUID):
                column.type = _SQLiteUUID()


_use_sqlite_uuid_types()


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _seed_repository(session):
    user_id = str(uuid4())
    organization_id = str(uuid4())
    project_id = str(uuid4())
    repository_id = str(uuid4())
    session.add(
        User(
            id=user_id,
            auth_provider_user_id=f"provider-{user_id}",
            email=f"{user_id}@example.com",
        )
    )
    session.add(
        Organization(
            id=organization_id,
            name="Test organization",
            slug=f"org-{organization_id}",
            created_by_user_id=user_id,
        )
    )
    session.add(
        OrganizationMember(
            id=str(uuid4()),
            organization_id=organization_id,
            user_id=user_id,
            role=MemberRole.OWNER,
        )
    )
    session.add(
        Project(
            id=project_id,
            organization_id=organization_id,
            name="Test project",
            slug=f"project-{project_id}",
            created_by_user_id=user_id,
        )
    )
    session.add(
        Repository(
            id=repository_id,
            project_id=project_id,
            provider="github",
            owner_name="owner",
            repo_name="repo",
            full_name="owner/repo",
        )
    )
    await session.commit()
    return repository_id, project_id


async def _seed_finding(session, repository_id, project_id, fingerprint):
    finding = Finding(
        id=str(uuid4()),
        project_id=project_id,
        repository_id=repository_id,
        category="vulnerability",
        severity="high",
        status="open",
        title="Test finding",
        canonical_fingerprint=fingerprint,
        primary_scanner="trivy",
        metadata_json={
            "observed_branches": ["refs/heads/main"],
            "scanner_evidence_by_branch": {"refs/heads/main": {"trivy": {
                "scanner_version": "1.0.0", "rules_version": "2026-09-13"
            }}},
        },
    )
    session.add(finding)
    await session.commit()
    return finding


async def _seed_scan(
    session,
    repository_id,
    project_id,
    *,
    commit_sha,
    scan_type="full",
    run_statuses=("completed", "completed"),
):
    scan = Scan(
        id=str(uuid4()),
        project_id=project_id,
        repository_id=repository_id,
        trigger_type="manual",
        scan_type=scan_type,
        status=ScanStatus.RUNNING,
        branch_name="refs/heads/main",
        commit_sha=commit_sha,
    )
    session.add(scan)
    await session.flush()
    for scanner_name, status in zip(("trivy", "gitleaks"), run_statuses, strict=True):
        session.add(
            ScannerRun(
                id=str(uuid4()),
                scan_id=str(scan.id),
                scanner_name=scanner_name,
                scanner_version="1.0.0",
                status=ScanStatus(status),
                metadata_json={"rules_version": "2026-09-13"},
            )
        )
    await session.commit()
    return scan


async def _absence(session, repository_id, project_id, *, commit_sha, scan_type="full", run_statuses=None):
    scan = await _seed_scan(
        session,
        repository_id,
        project_id,
        commit_sha=commit_sha,
        scan_type=scan_type,
        run_statuses=run_statuses or ("completed", "completed"),
    )
    health = {
        "expected": ["trivy", "gitleaks"],
        "completed": (
            ["trivy", "gitleaks"]
            if all(status == "completed" for status in run_statuses or ("completed", "completed"))
            else ["trivy"]
        ),
        "failed": [] if not run_statuses or all(status == "completed" for status in run_statuses) else ["gitleaks"],
        "missing": [],
        "complete": not run_statuses or all(status == "completed" for status in run_statuses),
    }
    scan.summary_json = {"scanner_health": health, "coverage_comparable": True}
    await session.commit()
    return await FindingService(session).mark_not_observed_after_scan(
        repository_id=repository_id,
        scan_id=str(scan.id),
        seen_fingerprints=set(),
        scan_summary={"scanner_health": health, "coverage_comparable": True},
    )


@pytest.mark.asyncio
async def test_partial_scan_cannot_advance_disappearance(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "partial")

    updated = await _absence(
        db_session,
        repository_id,
        project_id,
        commit_sha="a" * 40,
        run_statuses=("completed", "failed"),
    )

    await db_session.refresh(finding)
    assert updated == 0
    assert finding.status == "open"
    assert finding.metadata_json["observed_branches"] == ["refs/heads/main"]


@pytest.mark.asyncio
async def test_unknown_scanner_provenance_cannot_advance_disappearance(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "unknown-provenance")
    scan = await _seed_scan(
        db_session,
        repository_id,
        project_id,
        commit_sha="u" * 40,
    )
    scanner_runs = await db_session.execute(
        select(ScannerRun).where(ScannerRun.scan_id == str(scan.id))
    )
    for scanner_run in scanner_runs.scalars():
        scanner_run.scanner_version = None
        scanner_run.metadata_json = None
    scan.summary_json = {
        "scanner_health": {
            "expected": ["trivy", "gitleaks"],
            "completed": ["trivy", "gitleaks"],
            "failed": [],
            "missing": [],
            "complete": True,
        },
        "coverage_comparable": True,
    }
    await db_session.commit()

    updated = await FindingService(db_session).mark_not_observed_after_scan(
        repository_id=repository_id,
        scan_id=str(scan.id),
        seen_fingerprints=set(),
        scan_summary={"coverage_comparable": True},
    )

    await db_session.refresh(finding)
    assert updated == 0
    assert finding.status == "open"


@pytest.mark.asyncio
async def test_diff_scan_cannot_advance_disappearance(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "diff")

    updated = await _absence(
        db_session,
        repository_id,
        project_id,
        commit_sha="b" * 40,
        scan_type="diff",
    )

    await db_session.refresh(finding)
    assert updated == 0
    assert finding.status == "open"


@pytest.mark.asyncio
async def test_two_distinct_healthy_absences_close_finding(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "healthy")

    first = await _absence(db_session, repository_id, project_id, commit_sha="c" * 40)
    second = await _absence(db_session, repository_id, project_id, commit_sha="d" * 40)

    await db_session.refresh(finding)
    assert first == 1
    assert second == 1
    assert finding.status == "fixed"
    assert len(finding.metadata_json["absence_series"]["refs/heads/main"]["qualifying_absences"]) == 2


@pytest.mark.asyncio
async def test_same_commit_retry_does_not_count_twice(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "retry")

    first = await _absence(db_session, repository_id, project_id, commit_sha="e" * 40)
    retry = await _absence(db_session, repository_id, project_id, commit_sha="e" * 40)

    await db_session.refresh(finding)
    assert first == 1
    assert retry == 0
    assert finding.status == "not_observed"
    assert len(finding.metadata_json["absence_series"]["refs/heads/main"]["qualifying_absences"]) == 1


@pytest.mark.asyncio
async def test_persisted_finding_instance_counts_as_presence(db_session):
    repository_id, project_id = await _seed_repository(db_session)
    finding = await _seed_finding(db_session, repository_id, project_id, "present")
    scan = await _seed_scan(
        db_session,
        repository_id,
        project_id,
        commit_sha="f" * 40,
    )
    db_session.add(
        FindingInstance(
            id=str(uuid4()),
            finding_id=str(finding.id),
            scan_id=str(scan.id),
            occurrence_fingerprint="occurrence",
            evidence_json={},
        )
    )
    scan.summary_json = {
        "scanner_health": {
            "expected": ["trivy", "gitleaks"],
            "completed": ["trivy", "gitleaks"],
            "failed": [],
            "missing": [],
            "complete": True,
        },
        "coverage_comparable": True,
    }
    await db_session.commit()

    updated = await FindingService(db_session).mark_not_observed_after_scan(
        repository_id=repository_id,
        scan_id=str(scan.id),
        seen_fingerprints=set(),
        scan_summary={
            "scanner_health": {
                "expected": ["trivy", "gitleaks"],
                "completed": ["trivy", "gitleaks"],
                "failed": [],
                "missing": [],
                "complete": True,
            },
            "coverage_comparable": True,
        },
    )

    await db_session.refresh(finding)
    assert updated == 0
    assert finding.status == "open"
