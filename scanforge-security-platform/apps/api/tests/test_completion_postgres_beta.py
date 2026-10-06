import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.enums import RepoProvider, ScanStatus
from app.db.models import Finding, FindingInstance, Organization, Project, Repository, Scan, ScanCompletionReceipt, User
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.scan_completion import CompletionPayloadConflict, ScanCompletionService

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is required")


@pytest.fixture
async def postgres_scan():
    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = {name: uuid4() for name in ("user", "org", "project", "repo", "scan", "attempt")}
    async with sessions() as db:
        db.add(User(id=ids["user"], auth_provider_user_id=str(ids["user"]), email=f'{ids["user"]}@example.test'))
        await db.flush()
        db.add(Organization(id=ids["org"], name="Beta fixture", slug=str(ids["org"]), created_by_user_id=ids["user"]))
        await db.flush()
        db.add(Project(id=ids["project"], organization_id=ids["org"], name="Fixture", slug="fixture", created_by_user_id=ids["user"]))
        await db.flush()
        db.add(Repository(id=ids["repo"], project_id=ids["project"], provider=RepoProvider.GITHUB,
                          owner_name="fixture", repo_name=str(ids["repo"]), full_name=f'fixture/{ids["repo"]}'))
        await db.flush()
        db.add(Scan(id=ids["scan"], project_id=ids["project"], repository_id=ids["repo"], trigger_type="manual",
                    scan_type="secrets", status=ScanStatus.RUNNING, branch_name="main", commit_sha="a" * 40,
                    current_attempt_id=str(ids["attempt"]), execution_revision=1))
        await db.commit()
    yield sessions, ids
    async with sessions() as db:
        org = await db.get(Organization, ids["org"])
        await db.delete(org)
        await db.flush()
        user = await db.get(User, ids["user"])
        await db.delete(user)
        await db.commit()
    await engine.dispose()


def payload(ids):
    return ScanCompletionRequest(
        winning_attempt_id=ids["attempt"], execution_revision=1,
        findings=[{"canonical_fingerprint": str(ids["scan"]), "primary_scanner": "gitleaks", "category": "secret",
                   "severity": "high", "title": "Secret fixture", "instance": {"path": "fixture.txt", "line_start": 1}}],
        scanner_runs=[{"scanner_name": "gitleaks", "scanner_version": "8.30.0", "status": "completed", "exit_code": 0,
                       "metadata_json": {"configuration_digest": "fixture-rules-v1"}}],
    )


@pytest.mark.asyncio
async def test_concurrent_completion_and_response_loss_produce_one_occurrence(postgres_scan):
    sessions, ids = postgres_scan

    async def complete():
        async with sessions() as db:
            return await ScanCompletionService(db).complete(ids["scan"], ids["org"], payload(ids))

    results = await asyncio.gather(complete(), complete())
    assert sorted(item["replayed"] for item in results) == [False, True]
    replay = await complete()
    assert replay["replayed"] is True
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(FindingInstance).where(FindingInstance.scan_id == ids["scan"])) == 1
        assert await db.scalar(select(func.count()).select_from(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == ids["scan"])) == 1
        assert (await db.get(Scan, ids["scan"])).status == ScanStatus.COMPLETED
        changed = payload(ids)
        changed.findings[0].title = "Conflicting evidence"
        with pytest.raises(CompletionPayloadConflict):
            await ScanCompletionService(db).complete(ids["scan"], ids["org"], changed)


@pytest.mark.asyncio
async def test_failure_after_findings_flush_rolls_back_all_evidence(postgres_scan, monkeypatch):
    from app.services.findings import FindingService

    sessions, ids = postgres_scan

    async def fail_after_findings(self, **kwargs):
        raise RuntimeError("injected lifecycle failure")

    monkeypatch.setattr(FindingService, "mark_not_observed_after_scan", fail_after_findings)
    async with sessions() as db:
        with pytest.raises(RuntimeError, match="injected"):
            await ScanCompletionService(db).complete(ids["scan"], ids["org"], payload(ids))
    async with sessions() as db:
        assert (await db.get(Scan, ids["scan"])).status == ScanStatus.RUNNING
        assert await db.scalar(select(func.count()).select_from(Finding).where(Finding.repository_id == ids["repo"])) == 0
        assert await db.scalar(select(func.count()).select_from(FindingInstance).where(FindingInstance.scan_id == ids["scan"])) == 0
        assert await db.scalar(select(func.count()).select_from(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == ids["scan"])) == 0
