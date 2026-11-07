"""#46: shadow PR runs must never mutate the canonical finding baseline.

Shadow analysis is stored on the run (completion summary, scanner runs, artifacts).
It must not create, reopen or close repository findings, and a fork head named
"main" must not be able to drive absence credit for the real main branch.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from test_findings_disappearance_scope import (  # noqa: F401
    MAIN,
    OK_RUNS,
    _add_runs,
    _health,
    _observe,
    _reload,
    _seed_finding,
    _seed_repo,
    db_session,
)

from app.db.enums import ScanStatus
from app.db.models import Finding, Scan
from app.services.finding_lifecycle import AbsenceBlockReason, evaluate_scan_absence_evidence
from app.services.findings import FindingService

CANDIDATE = {
    "category": "vulnerability",
    "severity": "high",
    "title": "t",
    "canonical_fingerprint": "fp-pr",
    "primary_scanner": "trivy",
    "confidence_score": 0.9,
}


async def _pr_scan(session, repo_id, project_id, *, branch_name=None):
    scan = Scan(
        id=str(uuid4()),
        project_id=project_id,
        repository_id=repo_id,
        trigger_type="pull_request",
        scan_type="full",
        status=ScanStatus.RUNNING,
        branch_name=branch_name,
        full_ref_name="refs/pull/17/head",
        commit_sha="e" * 40,
        pull_request_number=17,
    )
    session.add(scan)
    await session.flush()
    await session.commit()
    return scan


@pytest.mark.asyncio
@pytest.mark.parametrize("branch_name", [None, MAIN])
async def test_shadow_scan_findings_do_not_create_repository_findings(db_session, branch_name):
    repo_id, project_id, _ = await _seed_repo(db_session)
    scan = await _pr_scan(db_session, repo_id, project_id, branch_name=branch_name)

    result = await FindingService(db_session).upsert_from_scan(
        scan_id=str(scan.id),
        repository_id=repo_id,
        project_id=project_id,
        normalized_findings=[CANDIDATE],
    )

    assert result == (0, 0)
    assert (await db_session.execute(select(Finding))).scalars().all() == []


@pytest.mark.asyncio
async def test_shadow_scan_cannot_reopen_a_fixed_finding(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    finding = await _seed_finding(db_session, repo_id, project_id, "fp-pr", status="fixed")
    scan = await _pr_scan(db_session, repo_id, project_id)

    await FindingService(db_session).upsert_from_scan(
        scan_id=str(scan.id),
        repository_id=repo_id,
        project_id=project_id,
        normalized_findings=[CANDIDATE],
    )

    assert (await _reload(db_session, finding)).status == "fixed"


@pytest.mark.asyncio
async def test_shadow_scan_never_credits_absence_even_with_healthy_evidence_on_a_colliding_branch(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    finding = await _seed_finding(db_session, repo_id, project_id, "fp-main")
    service = await _observe(db_session, repo_id, project_id, "fp-main", commit="0" * 40)
    # A fork PR whose head branch is literally named "main", healthy and complete.
    scan = await _pr_scan(db_session, repo_id, project_id, branch_name=MAIN)
    await _add_runs(db_session, scan.id, OK_RUNS)

    updated = await service.mark_not_observed_after_scan(
        repository_id=repo_id,
        scan_id=str(scan.id),
        seen_fingerprints=set(),
        scan_summary=_health(),
    )

    assert updated == 0
    after = await _reload(db_session, finding)
    assert after.status == "open"
    assert after.metadata_json["absence_series"][MAIN]["qualifying_absences"] == []


def test_absence_evidence_names_shadow_runs_as_ineligible():
    eligible, reasons = evaluate_scan_absence_evidence(
        {
            "scan_type": "full",
            "trigger_type": "pull_request",
            "branch_name": "main",
            "commit_sha": "a" * 40,
            **_health(),
        }
    )

    assert eligible is False
    assert AbsenceBlockReason.PULL_REQUEST_SHADOW in reasons
