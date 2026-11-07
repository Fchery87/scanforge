"""Debounce and supersession of obsolete shadow PR runs (#48, plan P2.2).

Seams: ScanService.create_pr_shadow (service) and the dispatcher's claim path.
Shadow means nothing is published to GitHub. Real PostgreSQL concurrency was NOT run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.core.config import settings
from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import ScanDispatchObligation
from app.services.scan_dispatch import ScanDispatchService
from app.services.scans import ScanService

BASE = "b" * 40
MERGE_BASE = "d" * 40


def _head(n: int) -> str:
    return f"{n:x}" * 40


async def _shadow(db, repo, head, *, number=17):
    scan, _, _ = await ScanService(db).create_pr_shadow(
        repo.id,
        pull_request_number=number,
        head_sha=head,
        base_sha=BASE,
        merge_base_sha=MERGE_BASE,
        is_fork=False,
    )
    return scan


async def _obligation(db, scan):
    return (
        await db.execute(select(ScanDispatchObligation).where(ScanDispatchObligation.scan_id == str(scan.id)))
    ).scalar_one()


@pytest.mark.asyncio
async def test_burst_of_pushes_leaves_one_live_run_for_the_latest_head(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)

    scans = [await _shadow(db_session, repo, _head(n)) for n in (1, 2, 3)]
    for s in scans:
        await db_session.refresh(s)

    live = [s for s in scans if s.status == ScanStatusEnum.QUEUED]
    assert [s.commit_sha for s in live] == [_head(3)]
    for old in scans[:2]:
        assert old.status == ScanStatusEnum.CANCELED
        assert old.dispatch_state == "superseded"


@pytest.mark.asyncio
async def test_superseded_run_records_superseding_run_and_contributes_no_results(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)

    old = await _shadow(db_session, repo, _head(1))
    new = await _shadow(db_session, repo, _head(2))
    await db_session.refresh(old)

    assert str(old.superseded_by_scan_id) == str(new.id)
    assert old.supersession_reason
    assert old.closure_eligible is False
    assert old.coverage_completeness == "skipped_superseded"
    assert old.summary_json["superseded_by_commit_sha"] == _head(2)
    assert old.summary_json["fabricated_observations"] is False
    obligation = await _obligation(db_session, old)
    assert obligation.status == "superseded"
    assert str(obligation.superseded_by_scan_id) == str(new.id)


@pytest.mark.asyncio
async def test_superseded_run_is_never_claimed_for_dispatch(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    old = await _shadow(db_session, repo, _head(1))
    new = await _shadow(db_session, repo, _head(2))

    claimed = await ScanDispatchService(db_session).claim_due_obligations(
        lease_owner="t", now=datetime.now(UTC) + timedelta(hours=1)
    )

    assert [str(o.scan_id) for o in claimed] == [str(new.id)]
    assert str(old.id) not in {str(o.scan_id) for o in claimed}


@pytest.mark.asyncio
async def test_running_older_run_is_not_coalesced_but_marked_obsolete(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    running = await _shadow(db_session, repo, _head(1))
    running.status = ScanStatusEnum.RUNNING
    running.current_attempt_id = "attempt-1"
    await db_session.commit()

    new = await _shadow(db_session, repo, _head(2))
    await db_session.refresh(running)

    assert running.status == ScanStatusEnum.RUNNING
    assert running.superseded_by_scan_id is None
    assert running.summary_json["newer_head_scan_id"] == str(new.id)
    assert running.summary_json["newer_head_commit_sha"] == _head(2)
    assert new.status == ScanStatusEnum.QUEUED


@pytest.mark.asyncio
async def test_other_pull_requests_are_not_superseded(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    other_pr = await _shadow(db_session, repo, _head(1), number=18)
    await _shadow(db_session, repo, _head(2), number=17)
    await db_session.refresh(other_pr)

    assert other_pr.status == ScanStatusEnum.QUEUED
    assert other_pr.superseded_by_scan_id is None


@pytest.mark.asyncio
async def test_same_head_redelivery_does_not_supersede_itself(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _shadow(db_session, repo, _head(1))
    again = await _shadow(db_session, repo, _head(1))

    assert again.id == first.id
    await db_session.refresh(first)
    assert first.status == ScanStatusEnum.QUEUED
    assert first.superseded_by_scan_id is None


@pytest.mark.asyncio
async def test_debounce_defers_dispatch_until_the_window_elapses(db_session, monkeypatch):
    monkeypatch.setattr(settings, "PR_SHADOW_DEBOUNCE_SECONDS", 30)
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    scan = await _shadow(db_session, repo, _head(1))
    service = ScanDispatchService(db_session)
    now = datetime.now(UTC)

    assert await service.claim_due_obligations(lease_owner="t", now=now + timedelta(seconds=5)) == []
    claimed = await service.claim_due_obligations(lease_owner="t", now=now + timedelta(seconds=60))
    assert [str(o.scan_id) for o in claimed] == [str(scan.id)]


@pytest.mark.asyncio
async def test_debounce_defaults_to_a_positive_window():
    assert settings.PR_SHADOW_DEBOUNCE_SECONDS > 0
