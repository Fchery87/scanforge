"""#49 / P2.3: shadow review candidates reconcile across pushes; out-of-order head guard.

Seams: evidence ingress (ScanCompletionService.complete) -> candidate records, and
ScanService.create_pr_shadow (head recording / out-of-order guard). Candidates are keyed by
fingerprint identity per (repository, PR). Nothing here publishes to GitHub. Real PostgreSQL
(row locks, unique-constraint races) was NOT run.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_pr_shadow_classification import (  # noqa: F401
    BASE,
    MERGE_BASE,
    _complete,
    _finding,
    _runs,
    _uniform_sqlite_uuid_columns,
)
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from app.db.enums import ScanStatus
from app.db.models import Repository, Scan, ShadowReviewCandidate
from app.schemas.canonical_findings import CanonicalFindingInstance
from app.services.pr_candidates import ShadowCandidateService, StalePullRequestHead
from app.services.scans import ScanService

T0 = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def _sha(n: int) -> str:
    return f"{n:x}" * 40


async def _head(db, repo, n, *, at=None, number=17):
    scan, _, _ = await ScanService(db).create_pr_shadow(
        repo.id,
        pull_request_number=number,
        head_sha=_sha(n),
        base_sha=BASE,
        merge_base_sha=MERGE_BASE,
        is_fork=False,
        head_observed_at=at if at is not None else T0 + timedelta(minutes=n),
    )
    return scan


def _located(fingerprint, line, scanner="semgrep"):
    finding = _finding(fingerprint, scanner)
    finding.instance = CanonicalFindingInstance(path="app/api.py", line_start=line)
    return finding


async def _candidates(db, repo, number=17):
    rows = (
        await db.execute(
            select(ShadowReviewCandidate).where(
                ShadowReviewCandidate.repository_id == str(repo.id),
                ShadowReviewCandidate.pull_request_number == number,
            )
        )
    ).scalars()
    return {row.fingerprint: row for row in rows}


@pytest.mark.asyncio
async def test_repush_of_the_same_issue_updates_the_existing_candidate(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _head(db_session, repo, 1)
    await _complete(db_session, first, findings=[_located("fp-a", 10)])
    second = await _head(db_session, repo, 2)
    await _complete(db_session, second, findings=[_located("fp-a", 10)])

    rows = await _candidates(db_session, repo)
    assert list(rows) == ["fp-a"]
    candidate = rows["fp-a"]
    assert candidate.state == "active"
    assert candidate.head_sha == _sha(2)
    assert str(candidate.first_scan_id) == str(first.id)
    assert str(candidate.last_scan_id) == str(second.id)
    assert (candidate.path, candidate.line_start) == ("app/api.py", 10)


@pytest.mark.asyncio
async def test_rebase_keeps_one_candidate_and_follows_the_moved_location(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    await _complete(db_session, await _head(db_session, repo, 2), findings=[_located("fp-a", 42)])

    (candidate,) = (await _candidates(db_session, repo)).values()
    assert candidate.state == "active"
    assert candidate.line_start == 42


@pytest.mark.asyncio
async def test_force_push_that_removes_the_issue_under_comparable_analysis_resolves_it(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    # Force-push replaces the head with a non-descendant that no longer has fp-a but has fp-b.
    await _complete(db_session, await _head(db_session, repo, 2), findings=[_located("fp-b", 5)])

    rows = await _candidates(db_session, repo)
    assert rows["fp-a"].state == "resolved"
    assert rows["fp-a"].resolution_basis == "comparable_absence"
    assert rows["fp-b"].state == "active"
    assert rows["fp-b"].first_scan_id == rows["fp-b"].last_scan_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "later_runs",
    [
        {"overrides": {"semgrep": {"rules_digest": "rules-b"}}},
        {
            "coverage": {
                "semgrep": {"declared_scope": "workspace", "inputs_found": 3, "inputs_supported": 3, "truncated": True}
            }
        },
        {"overrides": {"semgrep": {"status": "failed", "outcome_status": "failed", "metadata_json": None}}},
    ],
    ids=["rules_changed", "partial_coverage", "scanner_failed"],
)
async def test_absence_without_comparable_complete_analysis_is_outdated_not_a_fix(db_session, later_runs):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    await _complete(db_session, await _head(db_session, repo, 2), runs=_runs(**later_runs))

    candidate = (await _candidates(db_session, repo))["fp-a"]
    assert candidate.state == "outdated"
    assert candidate.resolution_basis is None
    assert await ShadowCandidateService(db_session).remediation_evidence(repo.id, 17) == []


@pytest.mark.asyncio
async def test_only_resolved_candidates_with_a_basis_are_remediation_evidence(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(
        db_session,
        await _head(db_session, repo, 1),
        findings=[_located("fp-fixed", 1), _located("fp-stale", 2, "gitleaks")],
    )
    # Semgrep unchanged and complete -> fp-fixed resolved; gitleaks rules changed -> fp-stale outdated.
    await _complete(
        db_session,
        await _head(db_session, repo, 2),
        runs=_runs(overrides={"gitleaks": {"rules_digest": "rules-b"}}),
    )

    evidence = await ShadowCandidateService(db_session).remediation_evidence(repo.id, 17)
    assert [c.fingerprint for c in evidence] == ["fp-fixed"]
    rows = await _candidates(db_session, repo)
    assert rows["fp-stale"].state == "outdated"


@pytest.mark.asyncio
async def test_new_head_supersedes_active_candidates_until_it_is_analyzed(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    assert (await _candidates(db_session, repo))["fp-a"].state == "active"

    second = await _head(db_session, repo, 2)
    candidate = (await _candidates(db_session, repo))["fp-a"]
    assert candidate.state == "superseded"
    assert candidate.resolution_basis is None
    assert await ShadowCandidateService(db_session).remediation_evidence(repo.id, 17) == []

    await _complete(db_session, second, findings=[_located("fp-a", 10)])
    assert (await _candidates(db_session, repo))["fp-a"].state == "active"


@pytest.mark.asyncio
async def test_reappearing_issue_reactivates_the_same_candidate(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    await _complete(db_session, await _head(db_session, repo, 2))
    assert (await _candidates(db_session, repo))["fp-a"].state == "resolved"
    await _complete(db_session, await _head(db_session, repo, 3), findings=[_located("fp-a", 10)])

    rows = await _candidates(db_session, repo)
    assert list(rows) == ["fp-a"]
    assert rows["fp-a"].state == "active"
    assert rows["fp-a"].resolution_basis is None


@pytest.mark.asyncio
async def test_reconciling_twice_is_idempotent(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 10)])
    second = await _head(db_session, repo, 2)
    await _complete(db_session, second, findings=[_located("fp-b", 3)])

    async def snapshot():
        rows = await _candidates(db_session, repo)
        return {fp: (c.state, c.head_sha, c.last_scan_id) for fp, c in rows.items()}

    before = await snapshot()
    service = ShadowCandidateService(db_session)
    await service.reconcile(second)
    await service.reconcile(second)
    # Webhook redelivery of the same head returns the same run and changes nothing.
    again = await _head(db_session, repo, 2)

    assert again.id == second.id
    assert await snapshot() == before


@pytest.mark.asyncio
async def test_completion_of_a_non_current_head_does_not_touch_candidates(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    older = await _head(db_session, repo, 1)
    older.status = ScanStatus.RUNNING  # already started, so it is marked obsolete, not canceled
    older.current_attempt_id = "attempt-1"
    await db_session.commit()
    await _head(db_session, repo, 2)  # newer head recorded while the older run is still going

    # The older run's evidence lands late (attempt-fenced ingress already accepted it).
    older.status = ScanStatus.COMPLETED
    older.summary_json = {**older.summary_json, "result_index": {"fp-late": "semgrep"}}
    await ShadowCandidateService(db_session).reconcile(older)

    assert await _candidates(db_session, repo) == {}


@pytest.mark.asyncio
async def test_candidates_never_cross_repositories_or_pull_requests(db_session):
    _o, project, repo, _u = await _seed_org_project_repo(db_session)
    other = Repository(
        id=str(uuid4()),
        project_id=project.id,
        provider="github",
        external_repo_id="777",
        owner_name="acme",
        repo_name="other",
        full_name="acme/other",
        default_branch="main",
        is_active=True,
        lifecycle_state="connected",
    )
    db_session.add(other)
    await db_session.commit()

    await _complete(db_session, await _head(db_session, repo, 1), findings=[_located("fp-a", 1)])
    await _complete(db_session, await _head(db_session, other, 1), findings=[_located("fp-a", 1)])
    await _complete(db_session, await _head(db_session, repo, 5, number=18))

    assert list(await _candidates(db_session, repo)) == ["fp-a"]
    assert list(await _candidates(db_session, other)) == ["fp-a"]
    assert (await _candidates(db_session, repo))["fp-a"].state == "active"
    assert await _candidates(db_session, repo, number=18) == {}


@pytest.mark.asyncio
async def test_late_event_for_an_older_head_cannot_supersede_a_newer_queued_run(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    newer = await _head(db_session, repo, 2, at=T0 + timedelta(minutes=10))

    with pytest.raises(StalePullRequestHead) as stale:
        await _head(db_session, repo, 1, at=T0 + timedelta(minutes=5))

    assert stale.value.recorded_head_sha == _sha(2)
    await db_session.refresh(newer)
    assert newer.status == ScanStatus.QUEUED
    assert newer.superseded_by_scan_id is None
    scans = (await db_session.execute(select(Scan).where(Scan.repository_id == str(repo.id)))).scalars().all()
    assert [s.commit_sha for s in scans] == [_sha(2)]


@pytest.mark.asyncio
async def test_late_older_event_does_not_displace_a_running_newer_run(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    newer = await _head(db_session, repo, 2, at=T0 + timedelta(minutes=10))
    newer.status = ScanStatus.RUNNING
    newer.current_attempt_id = "attempt-1"
    await db_session.commit()

    with pytest.raises(StalePullRequestHead):
        await _head(db_session, repo, 1, at=T0 + timedelta(minutes=5))

    await db_session.refresh(newer)
    assert newer.status == ScanStatus.RUNNING
    assert "newer_head_scan_id" not in (newer.summary_json or {})


@pytest.mark.asyncio
async def test_redelivery_of_the_newest_head_and_genuinely_newer_heads_are_accepted(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _head(db_session, repo, 1, at=T0)
    again = await _head(db_session, repo, 1, at=T0)
    newer = await _head(db_session, repo, 2, at=T0 + timedelta(seconds=1))

    assert again.id == first.id
    await db_session.refresh(first)
    assert first.superseded_by_scan_id == newer.id


@pytest.mark.asyncio
async def test_stale_guard_is_per_pull_request(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    await _head(db_session, repo, 2, at=T0 + timedelta(minutes=10), number=17)
    other = await _head(db_session, repo, 1, at=T0, number=18)
    assert other.status == ScanStatus.QUEUED
