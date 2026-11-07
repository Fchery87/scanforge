"""#51 / P2.7: labelled shadow results become a replay evaluation corpus.

Seam: ShadowCorpusService plus the reviewer-label route that feeds it, over a real database
session fed by real evidence ingress. Entries are references (revision SHAs, scan / candidate /
label ids, fingerprint, split) and never copies of source, snippets or secrets. The split is a
stable function of repository + pull request, recorded at creation. Tenant deletion cascades
through the organization / repository foreign keys; retention is enforced by an expiry sweep.
Real PostgreSQL was NOT run (SQLite with foreign keys switched on stands in for cascades).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from test_pr_shadow_classification import (  # noqa: F401
    _complete,
    _finding,
    _head,
    _uniform_sqlite_uuid_columns,
)
from test_pr_shadow_results_view import _label, _member, _setup, _view
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.core.config import settings
from app.db.enums import MemberRole
from app.db.models import OrganizationMember, ShadowCorpusEntry, ShadowReviewCandidate
from app.services.organizations import OrganizationService
from app.services.shadow_corpus import ShadowCorpusService, assign_split


async def _candidate(db, org, project, head, owner, fingerprint):
    view = await _view(db, org, project, head, owner)
    cid = next(r.candidate_id for r in view.results if r.fingerprint == fingerprint)
    return await db.get(ShadowReviewCandidate, str(cid))


async def _labelled(db_session, label="useful"):
    org, project, repo, owner, head = await _setup(db_session)
    reviewer = await _member(db_session, org, MemberRole.SECURITY_REVIEWER)
    candidate = await _candidate(db_session, org, project, head, owner, "fp-b")
    await _label(db_session, org, project, head, candidate, reviewer, label)
    return org, project, repo, owner, head, reviewer, candidate


async def _entries(db_session):
    return list((await db_session.execute(select(ShadowCorpusEntry))).scalars())


@pytest.mark.asyncio
async def test_labelling_a_candidate_records_a_reference_only_corpus_entry(db_session):
    org, _project, repo, _owner, head, _reviewer, candidate = await _labelled(db_session)

    (entry,) = await _entries(db_session)

    assert str(entry.organization_id) == str(org.id)
    assert str(entry.repository_id) == str(repo.id)
    assert entry.pull_request_number == head.pull_request_number
    assert str(entry.scan_id) == str(head.id)
    assert str(entry.candidate_id) == str(candidate.id)
    assert entry.label_id is not None
    assert entry.fingerprint == "fp-b"
    assert entry.head_sha == head.commit_sha
    assert entry.base_sha == head.base_sha
    assert entry.merge_base_sha == head.merge_base_sha
    assert entry.split in {"tuning", "holdout"}
    assert entry.created_at is not None
    # References only: no column can hold source, snippets, titles, paths or secrets.
    stored = {c.name for c in ShadowCorpusEntry.__table__.columns}
    assert stored == {
        "id",
        "organization_id",
        "repository_id",
        "pull_request_number",
        "scan_id",
        "candidate_id",
        "label_id",
        "fingerprint",
        "head_sha",
        "base_sha",
        "merge_base_sha",
        "split",
        "split_policy",
        "created_at",
        "updated_at",
    }


@pytest.mark.asyncio
async def test_unlabelled_candidates_are_never_in_the_corpus(db_session):
    await _setup(db_session)  # candidates exist, nobody labelled anything
    assert await _entries(db_session) == []


@pytest.mark.asyncio
async def test_relabelling_is_idempotent_and_keeps_the_recorded_split(db_session):
    org, project, _repo, _owner, head, reviewer, candidate = await _labelled(db_session)
    (first,) = await _entries(db_session)
    recorded = (first.id, first.split, first.created_at)

    await _label(db_session, org, project, head, candidate, reviewer, "duplicate")

    (again,) = await _entries(db_session)
    assert (again.id, again.split, again.created_at) == recorded


@pytest.mark.asyncio
async def test_split_is_deterministic_and_a_pull_request_never_straddles_it(db_session):
    org, project, repo, owner, head, reviewer, _candidate_b = await _labelled(db_session)
    candidate_a = await _candidate(db_session, org, project, head, owner, "fp-a")
    await _label(db_session, org, project, head, candidate_a, reviewer, "useful")

    same_pr = await _entries(db_session)
    assert len(same_pr) == 2
    assert len({e.split for e in same_pr}) == 1
    assert same_pr[0].split == assign_split(repo.id, head.pull_request_number)

    splits = [assign_split("repo-1", number) for number in range(1, 301)]
    assert splits == [assign_split("repo-1", number) for number in range(1, 301)]
    assert set(splits) == {"tuning", "holdout"}
    assert 20 <= splits.count("holdout") <= 100  # roughly a fifth, both sides populated


@pytest.mark.asyncio
async def test_corpus_reads_are_tenant_scoped(db_session):
    org, *_ = await _labelled(db_session)

    service = ShadowCorpusService(db_session)
    assert len(await service.entries(org.id)) == 1
    assert await service.entries(uuid4()) == []


@pytest.mark.asyncio
async def test_another_tenants_label_is_never_recorded_into_a_tenant_corpus(db_session):
    *_, = await _labelled(db_session)
    (entry,) = await _entries(db_session)

    with pytest.raises(LookupError):
        await ShadowCorpusService(db_session).record_label(uuid4(), entry.label_id)
    assert len(await _entries(db_session)) == 1


@pytest.mark.asyncio
async def test_deleting_the_organization_removes_its_entries_and_only_its_entries(db_session):
    await db_session.execute(text("PRAGMA foreign_keys=ON"))
    other_org, other_project, other_repo, other_owner = await _seed_org_project_repo(db_session)
    other_repo.full_name = "other/tenant-repo"
    db_session.add(OrganizationMember(organization_id=other_org.id, user_id=other_owner.id, role=MemberRole.OWNER))
    await db_session.commit()
    org, *_ = await _labelled(db_session)

    other_head = await _head(db_session, other_repo)
    await _complete(db_session, other_head, findings=[_finding("fp-x")])
    other_reviewer = await _member(db_session, other_org, MemberRole.SECURITY_REVIEWER)
    other_candidate = await _candidate(db_session, other_org, other_project, other_head, other_owner, "fp-x")
    await _label(db_session, other_org, other_project, other_head, other_candidate, other_reviewer, "incorrect")
    assert len(await _entries(db_session)) == 2

    assert await OrganizationService(db_session).delete(org.id) is True

    remaining = await _entries(db_session)
    assert [str(e.organization_id) for e in remaining] == [str(other_org.id)]


@pytest.mark.asyncio
async def test_retention_sweep_removes_expired_entries_and_reads_exclude_them_first(db_session):
    org, *_ = await _labelled(db_session)
    (entry,) = await _entries(db_session)
    service = ShadowCorpusService(db_session, retention_days=90)

    entry.created_at = datetime.now(UTC) - timedelta(days=89)
    await db_session.commit()
    assert len(await service.entries(org.id)) == 1
    assert await service.expire_past_retention() == 0

    entry.created_at = datetime.now(UTC) - timedelta(days=91)
    await db_session.commit()
    assert await service.entries(org.id) == []  # excluded even before the sweep runs
    assert len(await _entries(db_session)) == 1
    assert await service.expire_past_retention() == 1
    assert await _entries(db_session) == []


@pytest.mark.asyncio
async def test_scheduler_route_runs_the_retention_sweep(db_session):
    from app.api.v1.routes import internal

    await _labelled(db_session)
    (entry,) = await _entries(db_session)
    entry.created_at = datetime.now(UTC) - timedelta(days=settings.SHADOW_CORPUS_RETENTION_DAYS + 1)
    await db_session.commit()

    assert await internal.expire_shadow_corpus(db=db_session) == {"expired": 1}
    assert await _entries(db_session) == []


def test_retention_period_is_a_documented_setting_with_a_conservative_default():
    assert settings.SHADOW_CORPUS_RETENTION_DAYS == 90
    assert ShadowCorpusService(None).retention == timedelta(days=90)
