"""Whole-branch review fixes for spec #32 (C6, C7): reviewer labels and the replay corpus.

Seams: the reviewer-label route and the corpus entries it feeds. Nothing here publishes to
GitHub. Real PostgreSQL (where the label race actually occurs) was NOT run.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from test_pr_shadow_classification import (  # noqa: F401
    _complete,
    _finding,
    _head,
    _uniform_sqlite_uuid_columns,
)
from test_pr_shadow_results_view import _label, _member, _setup, _view
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.db.enums import MemberRole
from app.db.models import Scan, ShadowCorpusEntry, ShadowReviewCandidate, ShadowReviewCandidateLabel
from app.services import shadow_corpus
from app.services.shadow_review_view import ShadowReviewViewService


async def _candidate(db, org, project, head, owner, fingerprint):
    view = await _view(db, org, project, head, owner)
    cid = next(r.candidate_id for r in view.results if r.fingerprint == fingerprint)
    return await db.get(ShadowReviewCandidate, str(cid))


@pytest.mark.asyncio
async def test_corpus_entry_of_an_outdated_candidate_uses_one_consistent_revision(db_session):
    """C7: head, base and merge-base must all come from the scan the entry references."""
    org, project, repo, owner, first = await _setup(db_session)
    candidate = await _candidate(db_session, org, project, first, owner, "fp-b")
    # A later push no longer reports fp-b: the candidate is no longer observed at the new head.
    second = await _head(db_session, repo, head_sha="c" * 40, merge_base="e" * 40)
    await _complete(db_session, second, findings=[_finding("fp-a")])
    await db_session.refresh(candidate)
    assert candidate.head_sha == second.commit_sha  # candidate.head_sha moved; last_scan_id did not
    reviewer = await _member(db_session, org, MemberRole.SECURITY_REVIEWER)

    await _label(db_session, org, project, second, candidate, reviewer, "useful")

    (entry,) = (await db_session.execute(select(ShadowCorpusEntry))).scalars().all()
    scan = await db_session.get(Scan, entry.scan_id)
    assert (entry.head_sha, entry.base_sha, entry.merge_base_sha) == (
        scan.commit_sha,
        scan.base_sha,
        scan.merge_base_sha,
    )


@pytest.mark.asyncio
async def test_label_lost_insert_race_updates_the_winning_row_instead_of_failing(db_session, monkeypatch):
    """C6: two concurrent first labels by one actor hit the (candidate, actor) unique constraint."""
    org, project, _repo, owner, head = await _setup(db_session)
    candidate = await _candidate(db_session, org, project, head, owner, "fp-b")
    reviewer = await _member(db_session, org, MemberRole.SECURITY_REVIEWER)
    await _label(db_session, org, project, head, candidate, reviewer, "useful")

    real = ShadowReviewViewService._actor_label
    calls = {"n": 0}

    async def _misses_first(self, candidate_id, actor_user_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else await real(self, candidate_id, actor_user_id)

    monkeypatch.setattr(ShadowReviewViewService, "_actor_label", _misses_first)

    response = await _label(db_session, org, project, head, candidate, reviewer, "not_useful")

    assert response.label == "not_useful"
    count = (await db_session.execute(select(func.count()).select_from(ShadowReviewCandidateLabel))).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_label_for_a_candidate_outside_the_tenant_corpus_is_404_not_500(db_session, monkeypatch):
    """C6: record_label's LookupError must surface as 404."""
    org, project, _repo, owner, head = await _setup(db_session)
    candidate = await _candidate(db_session, org, project, head, owner, "fp-b")

    async def _outside(self, organization_id, label_id):
        raise LookupError("label is not part of this organization")

    monkeypatch.setattr(shadow_corpus.ShadowCorpusService, "record_label", _outside)

    with pytest.raises(HTTPException) as missing:
        await _label(db_session, org, project, head, candidate, owner, "useful")

    assert missing.value.status_code == 404
    # The route rolls back. (Not asserted on rows: pysqlite releases SAVEPOINTs outside a
    # transaction, so SQLite cannot represent the PostgreSQL rollback behaviour here.)
    assert (await db_session.execute(select(ShadowCorpusEntry))).scalars().all() == []
