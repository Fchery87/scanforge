"""#47 / P2.1: new / existing / unknown classification of shadow PR results.

Seam: evidence ingress (ScanCompletionService.complete) with real database state, then the
read-time classification (ShadowClassificationService.classify), which is also what the scan
detail API serves. Classification is derived from per-scan completion evidence
(summary_json result index + scanner runs), because shadow findings are deliberately not
stored as repository findings (#46). Nothing here publishes to GitHub. Real PostgreSQL was NOT run.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_scan_dispatch import _seed_org_project_repo, db_session  # noqa: F401

from test_scan_dispatch import _SQLiteUUID

from app.db.base import Base
from app.db.models import Finding, Scan
from app.schemas.canonical_findings import CanonicalFindingCandidate
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services.pr_classification import ShadowClassificationService
from app.services.scan_completion import ScanCompletionService
from app.services.scans import ScanService

@pytest.fixture(autouse=True)
def _uniform_sqlite_uuid_columns():
    # Other test modules leave their own UUID shim on shared metadata; multi-row inserts
    # (the scanner runs below) need one consistent bind/result shim to match sentinels.
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.type.__class__.__name__ in {"UUID", "_SQLiteUUID"}:
                column.type = _SQLiteUUID()


BASE = "b" * 40
HEAD = "a" * 40
MERGE_BASE = "d" * 40
FULL = ["gitleaks", "semgrep", "checkov", "trivy", "syft"]
COMPLETE_COVERAGE = {"declared_scope": "workspace", "inputs_found": 3, "inputs_supported": 3}


def _runs(*, overrides=None, coverage=None, scanners=FULL):
    overrides = overrides or {}
    runs = []
    for name in scanners:
        cov = (coverage or {}).get(name, COMPLETE_COVERAGE)
        fields = {
            "scanner_name": name,
            "scanner_version": "1.0.0",
            "parser_version": "p1",
            "rules_digest": "rules-a",
            "status": "completed",
            "outcome_status": "completed",
            "db_freshness_state": "fresh",
            "metadata_json": {"coverage": cov} if cov is not None else None,
            **overrides.get(name, {}),
        }
        runs.append(ScannerRunCompletion(**fields))
    return runs


def _finding(fingerprint, scanner="semgrep"):
    return CanonicalFindingCandidate(
        canonical_fingerprint=fingerprint,
        fingerprint_version="fp.v3",
        severity="high",
        category="vulnerability",
        title=f"t-{fingerprint}",
        primary_scanner=scanner,
    )


async def _complete(db, scan, *, findings=(), runs=None):
    request = ScanCompletionRequest(
        winning_attempt_id=uuid4(),
        execution_revision=1,
        findings=list(findings),
        scanner_runs=runs if runs is not None else _runs(),
        summary_json={},
    )
    await ScanCompletionService(db).complete(scan.id, (await _org_id(db, scan)), request)
    await db.refresh(scan)


async def _org_id(db, scan):
    from app.db.models import Project

    return (await db.get(Project, scan.project_id)).organization_id


async def _head(db, repo, *, merge_base=MERGE_BASE, number=17, head_sha=HEAD):
    scan, _, _ = await ScanService(db).create_pr_shadow(
        repo.id,
        pull_request_number=number,
        head_sha=head_sha,
        base_sha=BASE,
        merge_base_sha=merge_base,
        is_fork=False,
    )
    return scan


async def _baseline_scans(db, repo):
    return (
        (
            await db.execute(
                select(Scan).where(Scan.repository_id == str(repo.id), Scan.commit_sha == MERGE_BASE)
            )
        )
        .scalars()
        .all()
    )


def _by_fp(classification):
    return {r["fingerprint"]: r for r in classification["results"]}


@pytest.mark.asyncio
async def test_preexisting_result_is_existing_and_new_result_is_new(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-old"), _finding("fp-new")])

    (baseline,) = await _baseline_scans(db_session, repo)
    await _complete(db_session, baseline, findings=[_finding("fp-old")])

    result = await ShadowClassificationService(db_session).classify(head)
    by_fp = _by_fp(result)
    assert by_fp["fp-old"]["classification"] == "existing"
    assert by_fp["fp-new"]["classification"] == "new"
    assert result["counts"] == {"new": 1, "existing": 1, "unknown": 0}
    assert result["baseline_scan_id"] == str(baseline.id)
    assert result["merge_base_sha"] == MERGE_BASE
    assert result["comparison_strategy"] == "head_vs_merge_base"
    # Shadow evidence never becomes repository findings.
    assert (await db_session.execute(select(Finding))).scalars().all() == []


@pytest.mark.asyncio
async def test_missing_baseline_is_unknown_never_clean_and_schedules_baseline_work_once(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-a")])

    result = await ShadowClassificationService(db_session).classify(head)
    assert _by_fp(result)["fp-a"]["classification"] == "unknown"
    assert _by_fp(result)["fp-a"]["reason"] == "baseline_pending"
    assert result["counts"] == {"new": 0, "existing": 0, "unknown": 1}

    (baseline,) = await _baseline_scans(db_session, repo)
    assert baseline.trigger_type == "pull_request"
    assert baseline.scan_type == "full"
    assert baseline.pull_request_number == 17
    assert baseline.head_is_fork is False
    assert baseline.dispatch_state == "awaiting_dispatch"

    # Re-classifying and replaying the head's completion never schedules a second baseline.
    await ShadowClassificationService(db_session).classify(head)
    assert len(await _baseline_scans(db_session, repo)) == 1


@pytest.mark.asyncio
async def test_unresolved_merge_base_is_unknown_and_nothing_is_guessed_or_scheduled(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo, merge_base=None)
    await _complete(db_session, head, findings=[_finding("fp-a")])

    result = await ShadowClassificationService(db_session).classify(head)
    assert _by_fp(result)["fp-a"]["classification"] == "unknown"
    assert _by_fp(result)["fp-a"]["reason"] == "merge_base_unresolved"
    scans = (await db_session.execute(select(Scan))).scalars().all()
    assert [s.id for s in scans] == [head.id]


@pytest.mark.asyncio
async def test_analyzer_difference_never_yields_new(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(
        db_session,
        head,
        findings=[_finding("fp-old"), _finding("fp-new"), _finding("fp-secret", "gitleaks")],
    )
    (baseline,) = await _baseline_scans(db_session, repo)
    # Semgrep ran a different rule pack at the base; gitleaks is unchanged.
    await _complete(
        db_session,
        baseline,
        findings=[_finding("fp-old")],
        runs=_runs(overrides={"semgrep": {"rules_digest": "rules-b"}}),
    )

    by_fp = _by_fp(await ShadowClassificationService(db_session).classify(head))
    assert by_fp["fp-new"]["classification"] == "unknown"
    assert by_fp["fp-new"]["reason"] == "analyzer_not_comparable"
    # Positive observation at the base is still a fact; an unchanged analyzer can still say new.
    assert by_fp["fp-old"]["classification"] == "existing"
    assert by_fp["fp-secret"]["classification"] == "new"


@pytest.mark.asyncio
async def test_baseline_from_an_older_analyzer_is_unknown_and_requests_one_fresh_baseline(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    first = await _head(db_session, repo)
    await _complete(db_session, first, findings=[_finding("fp-new")])
    (old_baseline,) = await _baseline_scans(db_session, repo)
    await _complete(db_session, old_baseline)

    # A later push is analyzed after a scanner upgrade; the merge-base baseline predates it.
    upgraded = _runs(overrides={"semgrep": {"scanner_version": "2.0.0"}})
    second = await _head(db_session, repo, head_sha="c" * 40)
    await _complete(db_session, second, findings=[_finding("fp-new")], runs=upgraded)

    entry = _by_fp(await ShadowClassificationService(db_session).classify(second))["fp-new"]
    assert entry["classification"] == "unknown"
    assert entry["reason"] == "analyzer_not_comparable"
    assert len(await _baseline_scans(db_session, repo)) == 2
    await ShadowClassificationService(db_session).classify(second)
    assert len(await _baseline_scans(db_session, repo)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "coverage",
    [
        {"semgrep": {"declared_scope": "workspace", "inputs_found": 3, "inputs_supported": 3, "truncated": True}},
        {"semgrep": None},
    ],
    ids=["partial", "unreported"],
)
async def test_baseline_coverage_gap_never_yields_new(db_session, coverage):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-new")])
    (baseline,) = await _baseline_scans(db_session, repo)
    await _complete(db_session, baseline, runs=_runs(coverage=coverage))

    entry = _by_fp(await ShadowClassificationService(db_session).classify(head))["fp-new"]
    assert entry["classification"] == "unknown"
    assert entry["reason"] == "baseline_coverage_not_complete"


@pytest.mark.asyncio
async def test_failed_baseline_scanner_never_yields_new(db_session):
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-new")])
    (baseline,) = await _baseline_scans(db_session, repo)
    failed = {"semgrep": {"status": "failed", "outcome_status": "failed", "metadata_json": None}}
    await _complete(db_session, baseline, runs=_runs(overrides=failed))

    entry = _by_fp(await ShadowClassificationService(db_session).classify(head))["fp-new"]
    assert entry["classification"] == "unknown"


@pytest.mark.asyncio
async def test_other_tenants_scans_are_never_a_baseline(db_session):
    _o2, _p2, other_repo, _u2 = await _seed_org_project_repo(db_session)
    other_repo.full_name = "other/tenant-repo"
    await db_session.commit()
    _o, _p, repo, _u = await _seed_org_project_repo(db_session)
    other_head = await _head(db_session, other_repo)
    await _complete(db_session, other_head, findings=[_finding("fp-new")])
    (other_baseline,) = await _baseline_scans(db_session, other_repo)
    await _complete(db_session, other_baseline, findings=[_finding("fp-new")])

    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-new")])

    entry = _by_fp(await ShadowClassificationService(db_session).classify(head))["fp-new"]
    assert entry["classification"] == "unknown"
    assert entry["reason"] == "baseline_pending"


@pytest.mark.asyncio
async def test_scan_detail_serves_classification_for_shadow_runs_only(db_session):
    from types import SimpleNamespace

    from app.api.v1.routes import scans as scan_routes
    from app.db.enums import MemberRole
    from app.db.models import OrganizationMember

    org, project, repo, user = await _seed_org_project_repo(db_session)
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=MemberRole.OWNER))
    await db_session.commit()
    head = await _head(db_session, repo)
    await _complete(db_session, head, findings=[_finding("fp-a")])
    (baseline,) = await _baseline_scans(db_session, repo)
    await _complete(db_session, baseline, findings=[_finding("fp-a")])

    async def detail(scan):
        return await scan_routes.get_scan(
            UUID(str(org.id)),
            UUID(str(project.id)),
            UUID(str(scan.id)),
            current_user=SimpleNamespace(user_id=UUID(str(user.id))),
            db=db_session,
        )

    served = await detail(head)
    assert served.shadow_classification.counts.existing == 1
    assert served.shadow_classification.results[0].classification == "existing"
    assert served.shadow_classification.comparison_strategy == "head_vs_merge_base"

    branch = Scan(
        id=str(uuid4()),
        project_id=project.id,
        repository_id=repo.id,
        trigger_type="manual",
        scan_type="full",
        status="completed",
        branch_name="main",
        commit_sha="9" * 40,
    )
    db_session.add(branch)
    await db_session.commit()
    assert (await detail(branch)).shadow_classification is None
