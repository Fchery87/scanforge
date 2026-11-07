"""Whole-branch review fixes for spec #32 (C2, C3, C4): shadow PR head/baseline hygiene.

Seams: ScanService.create_pr_shadow and evidence ingress (ScanCompletionService.complete).
Nothing here publishes to GitHub. Real PostgreSQL was NOT run.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from test_pr_shadow_classification import (  # noqa: F401
    MERGE_BASE,
    _complete,
    _finding,
    _head,
    _uniform_sqlite_uuid_columns,
)
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.db.enums import ScanStatus
from app.db.models import Scan

NEW_HEAD = "c" * 40
OTHER_MERGE_BASE = "e" * 40


async def _baselines(db, repo):
    return (
        (
            await db.execute(
                select(Scan).where(Scan.repository_id == str(repo.id), Scan.full_ref_name.like("refs/pull/%/base"))
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_completed_obsolete_head_does_not_schedule_baseline_work(db_session):
    """C3: only the PR's current head may request baseline work."""
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    old = await _head(db_session, repo)
    old.status = ScanStatus.RUNNING
    await db_session.commit()
    await _head(db_session, repo, head_sha=NEW_HEAD)  # running older run is not canceled, only obsolete

    await _complete(db_session, old, findings=[_finding("fp-a")])

    assert await _baselines(db_session, repo) == []


@pytest.mark.asyncio
async def test_current_head_still_schedules_baseline_work(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-a")])

    assert len(await _baselines(db_session, repo)) == 1


@pytest.mark.asyncio
async def test_unstarted_baseline_for_an_older_merge_base_is_superseded_by_a_new_head(db_session):
    """C2: stale baselines must not accumulate when the PR's merge-base moves."""
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _head(db_session, repo)
    await _complete(db_session, first, findings=[_finding("fp-a")])
    (stale,) = await _baselines(db_session, repo)
    assert stale.status == ScanStatus.QUEUED

    await _head(db_session, repo, head_sha=NEW_HEAD, merge_base=OTHER_MERGE_BASE)
    await db_session.refresh(stale)

    assert stale.status == ScanStatus.CANCELED
    assert stale.dispatch_state == "superseded"


@pytest.mark.asyncio
async def test_unstarted_baseline_for_the_same_merge_base_survives_a_new_head(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _head(db_session, repo)
    await _complete(db_session, first, findings=[_finding("fp-a")])
    (baseline,) = await _baselines(db_session, repo)

    await _head(db_session, repo, head_sha=NEW_HEAD)
    await db_session.refresh(baseline)

    assert baseline.status == ScanStatus.QUEUED
