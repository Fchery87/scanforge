"""#41 / P1.6: absence eligibility is evaluated per finding capability (G6).

A failed scanner blocks absence credit only for the capability it serves.
Unrelated capability success never proves absence.
"""

from __future__ import annotations

import pytest
from test_findings_disappearance_scope import (  # noqa: F401
    GITLEAKS_V1,
    MAIN,
    TRIVY_V1,
    _absence,
    _observe,
    _reload,
    _seed_finding,
    _seed_repo,
    db_session,
)

from app.services.evidence_contract import capability_for_scanner
from app.services.finding_lifecycle import AbsenceBlockReason, evaluate_scan_absence_evidence

CHECKOV_V1 = {"scanner_version": "3.2.0", "parser_version": "2026-10-parser.v1", "rules_digest": "sha256:ck-a"}
SEMGREP_V1 = {"scanner_version": "1.90.0", "parser_version": "2026-10-parser.v1", "rules_digest": "sha256:sg-a"}

HEALTHY_RUNS = (
    ("trivy", "completed", TRIVY_V1),
    ("gitleaks", "completed", GITLEAKS_V1),
    ("checkov", "completed", CHECKOV_V1),
)
IAC_FAILED_RUNS = (
    ("trivy", "completed", TRIVY_V1),
    ("gitleaks", "completed", GITLEAKS_V1),
    ("checkov", "failed", CHECKOV_V1),
)
IAC_FAILED_HEALTH = {
    "scanner_health": {
        "expected": ["trivy", "gitleaks", "checkov"],
        "completed": ["trivy", "gitleaks"],
        "failed": ["checkov"],
        "missing": [],
        "complete": False,
    }
}

FIVE_SCANNER_HEALTH = {
    "expected": ["trivy", "gitleaks", "semgrep", "syft", "checkov"],
    "completed": ["trivy", "gitleaks", "semgrep", "syft"],
    "failed": ["checkov"],
    "missing": [],
    "complete": False,
}


def _context(health):
    return {
        "scan_type": "full",
        "branch_name": MAIN,
        "commit_sha": "a" * 40,
        "scanner_health": health,
    }


def test_capability_map_assigns_each_scanner_one_capability():
    assert capability_for_scanner("gitleaks") == "secrets"
    assert capability_for_scanner("semgrep") == "sast"
    assert {capability_for_scanner(s) for s in ("trivy", "syft", "osv", "grype")} == {"dependencies"}
    assert capability_for_scanner("checkov") == "iac"
    assert capability_for_scanner("unknown") is None


@pytest.mark.parametrize("capability", ["secrets", "sast", "dependencies"])
def test_failed_iac_scanner_does_not_block_other_capabilities(capability):
    eligible, reasons = evaluate_scan_absence_evidence(_context(FIVE_SCANNER_HEALTH), capability=capability)
    assert eligible is True
    assert reasons == []


def test_failed_capability_is_ineligible_for_its_own_findings():
    eligible, reasons = evaluate_scan_absence_evidence(_context(FIVE_SCANNER_HEALTH), capability="iac")
    assert eligible is False
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons


def test_dependency_capability_needs_every_dependency_scanner_healthy():
    health = dict(FIVE_SCANNER_HEALTH, completed=["gitleaks", "semgrep", "trivy", "checkov"], failed=["syft"])
    eligible, _ = evaluate_scan_absence_evidence(_context(health), capability="dependencies")
    assert eligible is False


def test_capability_with_no_expected_scanner_is_never_proven_by_other_successes():
    health = {
        "expected": ["trivy", "gitleaks"],
        "completed": ["trivy", "gitleaks"],
        "failed": [],
        "missing": [],
        "complete": True,
    }
    eligible, reasons = evaluate_scan_absence_evidence(_context(health), capability="sast")
    assert eligible is False
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons


def test_scoped_evaluation_still_applies_scan_level_gates():
    context = dict(_context(FIVE_SCANNER_HEALTH), scan_type="diff")
    eligible, reasons = evaluate_scan_absence_evidence(context, capability="secrets")
    assert eligible is False
    assert AbsenceBlockReason.SCAN_TYPE_NOT_FULL in reasons


@pytest.mark.asyncio
async def test_failed_iac_scanner_does_not_block_secret_absence_credit(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    finding = await _seed_finding(db_session, repo_id, project_id, "fp-secret", scanner="gitleaks")
    service = await _observe(
        db_session, repo_id, project_id, "fp-secret", commit="0" * 40, runs=HEALTHY_RUNS, scanner="gitleaks"
    )

    updated = await _absence(
        service,
        repo_id,
        project_id,
        commit="a" * 40,
        summary=IAC_FAILED_HEALTH,
        run_statuses=IAC_FAILED_RUNS,
    )

    assert updated == 1
    assert (await _reload(db_session, finding)).status == "not_observed"


@pytest.mark.asyncio
async def test_failed_capability_grants_no_absence_for_its_own_findings(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    finding = await _seed_finding(db_session, repo_id, project_id, "fp-iac", scanner="checkov")
    service = await _observe(
        db_session, repo_id, project_id, "fp-iac", commit="0" * 40, runs=HEALTHY_RUNS, scanner="checkov"
    )

    updated = await _absence(
        service,
        repo_id,
        project_id,
        commit="a" * 40,
        summary=IAC_FAILED_HEALTH,
        run_statuses=IAC_FAILED_RUNS,
    )

    assert updated == 0
    after = await _reload(db_session, finding)
    assert after.status == "open"
    assert after.metadata_json["absence_series"][MAIN]["qualifying_absences"] == []


@pytest.mark.asyncio
async def test_unrelated_capability_success_never_proves_absence(db_session):
    repo_id, project_id, _ = await _seed_repo(db_session)
    finding = await _seed_finding(db_session, repo_id, project_id, "fp-sast", scanner="semgrep")
    service = await _observe(
        db_session,
        repo_id,
        project_id,
        "fp-sast",
        commit="0" * 40,
        runs=HEALTHY_RUNS + (("semgrep", "completed", SEMGREP_V1),),
        scanner="semgrep",
    )

    # Semgrep did not run in the absence scan; healthy trivy/gitleaks/checkov must not stand in for it.
    all_healthy = {
        "scanner_health": {
            "expected": ["trivy", "gitleaks", "checkov"],
            "completed": ["trivy", "gitleaks", "checkov"],
            "failed": [],
            "missing": [],
            "complete": True,
        }
    }
    updated = await _absence(
        service, repo_id, project_id, commit="a" * 40, summary=all_healthy, run_statuses=HEALTHY_RUNS
    )

    assert updated == 0
    assert (await _reload(db_session, finding)).status == "open"
