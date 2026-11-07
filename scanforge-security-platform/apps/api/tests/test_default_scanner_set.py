"""ADR-019: the default full scan expects Trivy (primary dependency engine) + Syft + non-dependency scanners.

The API declares which scanners a scan is expected to run; the worker runs its own registry. The two
must agree or every scan would be recorded as incomplete, so these tests pin the API side and prove the
server-derived evidence decision still reaches full coverage with exactly this set.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.api.v1.routes.internal import SCAN_TYPE_SCANNERS as INTERNAL_SCAN_TYPE_SCANNERS
from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion
from app.services.evidence_contract import CURRENT_EVIDENCE_CONTRACT_VERSION, derive_scan_evidence_decision
from app.services.repository_refs import SCAN_TYPE_SCANNERS

DEFAULT_FULL_SCAN = ["trivy", "gitleaks", "semgrep", "syft", "checkov"]
DB_BACKED = {"trivy", "grype", "osv"}


def _run(name: str) -> ScannerRunCompletion:
    db_backed = name in DB_BACKED
    return ScannerRunCompletion(
        scanner_name=name,
        scanner_version="1.0.0",
        status="completed",
        outcome_status="completed",
        parser_version=f"{name}-v1",
        rules_digest=f"sha256:rules-{name}",
        db_digest=f"sha256:db-{name}" if db_backed else None,
        db_published_at=(datetime.now(UTC) - timedelta(days=1)) if db_backed else None,
        db_freshness_state="fresh" if db_backed else "not_applicable",
        image_digest="sha256:image-1",
    )


def _decision(run_names: list[str], expected: list[str]):
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[_run(name) for name in run_names],
        findings=[],
        summary_json={},
    )
    return derive_scan_evidence_decision(
        request,
        expected_scanners=expected,
        commit_sha="a" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        ancestry_status="verified_descendant",
        cleanup_state="completed",
    )


def test_full_scan_expects_primary_dependency_engine_plus_inventory_and_non_dependency_scanners():
    assert SCAN_TYPE_SCANNERS["full"] == DEFAULT_FULL_SCAN
    assert INTERNAL_SCAN_TYPE_SCANNERS["full"] == DEFAULT_FULL_SCAN


def test_secondary_dependency_engines_are_not_expected_by_default_full_scans():
    for table in (SCAN_TYPE_SCANNERS, INTERNAL_SCAN_TYPE_SCANNERS):
        assert "osv" not in table["full"]
        assert "grype" not in table["full"]


def test_full_scan_with_default_set_reaches_full_coverage_without_osv_or_grype():
    decision = _decision(DEFAULT_FULL_SCAN, DEFAULT_FULL_SCAN)

    assert decision.coverage_completeness == "full"
    assert decision.closure_eligible is True
    assert decision.missing_scanners == ()


def test_scan_created_before_the_change_still_expecting_osv_and_grype_is_not_credited_as_full():
    legacy_expected = ["trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"]

    decision = _decision(DEFAULT_FULL_SCAN, legacy_expected)

    assert decision.coverage_completeness != "full"
    assert decision.closure_eligible is False
    assert set(decision.missing_scanners) == {"osv", "grype"}
