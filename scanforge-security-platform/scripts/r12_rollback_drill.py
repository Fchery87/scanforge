"""R12 rollback drill (imported by scripts/rehearse_rollback.sh).

Service-layer verification of R04 receipt semantics on SQLite and disposable
PostgreSQL. Evidence-only: no app code or schema changes.
"""

from __future__ import annotations

import time
from uuid import uuid4

from app.db.base import Base
from app.db.enums import ScanStatus
from app.db.models import (  # noqa: F401  (model import registers mappers)
    Organization,
    Project,
    Repository,
    Scan,
    ScanCompletionReceipt,
    ScannerRun,
    User,
)
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services.scan_completion import (
    CompletionPayloadConflict,
    CompletionSuperseded,
    ScanCompletionConflict,
    ScanCompletionService,
    canonical_evidence_digest,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import CHAR, TypeDecorator


# --- SQLite compatibility shims (mirrors apps/api/tests/test_r04_postgres_completion_red.py) ---
@compiles(PGUUID, "sqlite")
def _pg_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(32)"


@compiles(JSONB, "sqlite")
def _pg_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(INET, "sqlite")
def _pg_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR(45)"


class _SQLiteUUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(PGUUID(as_uuid=True) if dialect.name == "postgresql" else CHAR())

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


def _completion_request(**overrides) -> ScanCompletionRequest:
    values = {
        "winning_attempt_id": uuid4(),
        "execution_revision": 1,
        "findings": [],
        "scanner_runs": [ScannerRunCompletion(scanner_name="trivy", status="completed", exit_code=0)],
        "summary_json": {
            "seen_fingerprints": [],
            "scanner_health": {
                "expected": ["trivy"],
                "completed": ["trivy"],
                "failed": [],
                "missing": [],
                "complete": True,
            },
        },
    }
    values.update(overrides)
    return ScanCompletionRequest(**values)


async def _seed_scan(session):
    user_id = uuid4()
    org_id, project_id, repo_id, scan_id = (uuid4() for _ in range(4))
    session.add(User(id=str(user_id), auth_provider_user_id=f"ap-{user_id}", email=f"{user_id}@example.com"))
    await session.flush()
    session.add(Organization(id=str(org_id), name="org", slug=f"org-{org_id}", created_by_user_id=str(user_id)))
    await session.flush()
    session.add(Project(id=str(project_id), organization_id=str(org_id), name="p", slug=f"p-{project_id}", created_by_user_id=str(user_id)))
    await session.flush()
    session.add(Repository(id=str(repo_id), project_id=str(project_id), provider="github", owner_name="o", repo_name="r", full_name="o/r"))
    await session.flush()
    session.add(Scan(id=str(scan_id), project_id=str(project_id), repository_id=str(repo_id), trigger_type="manual", scan_type="full", status=ScanStatus.RUNNING))
    await session.flush()
    await session.commit()
    return str(scan_id), org_id


async def _receipt_count(session) -> int:
    result = await session.execute(select(func.count()).select_from(ScanCompletionReceipt))
    return int(result.scalar_one())


async def _run_backend(label: str, maker, expect_ok: bool) -> list[str]:
    checks: list[str] = []
    t0 = time.perf_counter()
    async with maker() as session:
        scan_id, org_id = await _seed_scan(session)
        data = _completion_request()

        # 1. First completion writes exactly one server-owned receipt.
        first = await ScanCompletionService(session).complete(scan_id, org_id, data)
        assert first["replayed"] is False, f"{label}: first completion must not be a replay"
        assert first["status"] == "completed", f"{label}: status {first['status']}"
        assert first["evidence_digest"] == canonical_evidence_digest(data)
        assert await _receipt_count(session) == 1, f"{label}: expected exactly one receipt row"
        checks.append(f"{label}: first completion -> receipt (replayed=False)")

        # 2. Identical replay returns the STORED receipt, no new row.
        replay = await ScanCompletionService(session).complete(scan_id, org_id, data)
        assert replay["replayed"] is True, f"{label}: identical replay must be flagged replayed"
        assert replay["evidence_digest"] == first["evidence_digest"], f"{label}: digest drift on replay"
        assert replay["winning_attempt_id"] == first["winning_attempt_id"]
        assert await _receipt_count(session) == 1, f"{label}: replay must not write a second receipt"
        checks.append(f"{label}: identical replay -> stored receipt returned, still 1 receipt row")

        # 3. Conflicting replay of the same identity -> payload conflict (409 family).
        conflicting = _completion_request(
            winning_attempt_id=data.winning_attempt_id,
            execution_revision=data.execution_revision,
            summary_json={"seen_fingerprints": [], "tampered": True},
        )
        try:
            await ScanCompletionService(session).complete(scan_id, org_id, conflicting)
            raise AssertionError(f"{label}: conflicting replay must raise CompletionPayloadConflict")
        except CompletionPayloadConflict as exc:
            assert exc.code == "completion_payload_conflict"
            checks.append(f"{label}: conflicting replay -> CompletionPayloadConflict (HTTP 409 family)")

        # 4. Stale identity replay -> superseded (409 family).
        stale = _completion_request()
        try:
            await ScanCompletionService(session).complete(scan_id, org_id, stale)
            raise AssertionError(f"{label}: stale-identity replay must raise CompletionSuperseded")
        except CompletionSuperseded as exc:
            assert exc.code == "completion_superseded"
            checks.append(f"{label}: stale-identity replay -> CompletionSuperseded (HTTP 409 family)")

        # 5. Integrity: receipt survives, exactly one row, terminal state durable.
        assert await _receipt_count(session) == 1
        receipt_key = first["scan_id"]  # stored form as returned by the service
        receipt = (
            await session.execute(select(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == receipt_key))
        ).scalar_one()
        assert receipt.terminal_status == ScanStatus.COMPLETED.value
        checks.append(f"{label}: receipt durable after conflicts (terminal_status=completed, 1 row)")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    checks.append(f"{label}: drill wall time {elapsed_ms:.0f} ms")
    for line in checks:
        print(f"[r12_rollback_drill] {line}")
    return checks


async def run_drill(label: str, pg_uri: str | None = None) -> int:
    _downcast_postgres_uuid_columns()
    if label == "sqlite":
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=None)
    else:
        assert pg_uri, "postgres drill requires pg_uri"
        engine = create_async_engine(pg_uri.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        await _run_backend(label, maker, expect_ok=True)
    except (AssertionError, ScanCompletionConflict) as exc:
        print(f"[r12_rollback_drill] {label}: FAIL: {exc}")
        return 1
    finally:
        await engine.dispose()
    return 0
