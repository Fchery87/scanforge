from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.canonical_findings import (
    CanonicalFindingCandidate,
    CanonicalFindingInstance,
    CanonicalFindingReference,
)
from app.schemas.scan_completion import (
    ScanCompletionRequest,
    ScannerRunCompletion,
)
from app.services.evidence_contract import (
    CURRENT_EVIDENCE_CONTRACT_VERSION,
    DuplicateJsonKeyError,
    DuplicateScannerRunError,
    ForbiddenWorkerAuthorityError,
    InvalidJsonNumberError,
    UnknownScannerError,
    UnsupportedContractVersionError,
    compute_canonical_evidence_digest,
    derive_scan_evidence_decision,
    negotiate_contract_version,
    parse_strict_contract_json,
)


def _fresh_db_time() -> datetime:
    return datetime.now(UTC) - timedelta(days=2)


def _stale_db_time() -> datetime:
    return datetime.now(UTC) - timedelta(days=10)


def test_full_coverage_requires_all_expected_scanners_fresh_db_and_verified_ancestry():
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[
            ScannerRunCompletion(
                scanner_name="trivy",
                scanner_version="0.58.1",
                status="completed",
                outcome_status="completed",
                parser_version="trivy-json-v2",
                rules_digest="sha256:rules-trivy",
                db_digest="sha256:db-trivy",
                db_published_at=_fresh_db_time(),
                db_freshness_state="fresh",
                image_digest="sha256:image-1",
                artifact_availability="verified_immutable",
            ),
            ScannerRunCompletion(
                scanner_name="gitleaks",
                scanner_version="8.21.2",
                status="completed",
                outcome_status="completed",
                parser_version="gitleaks-json-v1",
                rules_digest="sha256:rules-gitleaks",
                db_freshness_state="not_applicable",
                image_digest="sha256:image-1",
                artifact_availability="unavailable",
            ),
        ],
        findings=[],
        summary_json={"scanner_health": {"complete": False}},
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["trivy", "gitleaks"],
        commit_sha="a" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        ancestry_status="verified_descendant",
        cleanup_state="completed",
    )

    # Server derives completeness and closure eligibility from validated evidence,
    # ignoring worker summary_json["scanner_health"]["complete"] == False.
    assert decision.coverage_completeness == "full"
    assert decision.scanner_runs_complete is True
    assert decision.closure_eligible is True
    # Secondary artifact availability is tracked separately from scanner coverage!
    assert decision.artifact_availability == "partial"


def test_partial_coverage_when_expected_scanner_fails_or_is_missing_blocks_closure():
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[
            ScannerRunCompletion(
                scanner_name="trivy",
                scanner_version="0.58.1",
                status="completed",
                outcome_status="completed",
                db_published_at=_fresh_db_time(),
                db_freshness_state="fresh",
                image_digest="sha256:image-1",
            ),
            ScannerRunCompletion(
                scanner_name="semgrep",
                scanner_version="1.96.0",
                status="failed",
                outcome_status="failed",
                db_freshness_state="not_applicable",
                image_digest="sha256:image-1",
                error_message="semgrep exited with 2",
            ),
        ],
        summary_json={"scanner_health": {"complete": True}},
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["trivy", "semgrep"],
        commit_sha="b" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        ancestry_status="verified_descendant",
        cleanup_state="completed",
    )

    # Worker claimed complete=True in summary_json, but server derives partial coverage.
    assert decision.coverage_completeness == "partial"
    assert decision.scanner_runs_complete is False
    assert decision.closure_eligible is False


def test_stale_scanner_database_older_than_seven_days_blocks_full_coverage_and_closure():
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[
            ScannerRunCompletion(
                scanner_name="trivy",
                scanner_version="0.58.1",
                status="completed",
                outcome_status="completed",
                db_published_at=_stale_db_time(),
                db_freshness_state="fresh",
                image_digest="sha256:image-1",
            ),
        ],
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["trivy"],
        commit_sha="c" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        ancestry_status="verified_descendant",
        cleanup_state="completed",
    )

    assert decision.coverage_completeness == "partial"
    assert decision.closure_eligible is False


@pytest.mark.parametrize(
    "database_evidence",
    [
        {"db_freshness_state": "unverified", "db_published_at": _fresh_db_time(), "db_digest": "sha256:db"},
        {"db_freshness_state": "fresh", "db_published_at": None, "db_digest": "sha256:db"},
        {"db_freshness_state": "fresh", "db_published_at": _fresh_db_time(), "db_digest": None},
        {
            "db_freshness_state": "fresh",
            "db_published_at": datetime.now(UTC) + timedelta(minutes=1),
            "db_digest": "sha256:db",
        },
    ],
)
def test_unverifiable_or_future_scanner_database_never_grants_full_coverage(database_evidence):
    request = ScanCompletionRequest(
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[
            ScannerRunCompletion(
                scanner_name="trivy",
                status="completed",
                outcome_status="completed",
                **database_evidence,
            )
        ],
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["trivy"],
        commit_sha="a" * 40,
        ancestry_status="verified_descendant",
        cleanup_state="completed",
    )

    assert decision.coverage_completeness == "partial"
    assert decision.closure_eligible is False
    assert "scanner_database_stale" in decision.ineligibility_reasons


def test_unknown_ancestry_or_cleanup_pending_blocks_closure_eligibility():
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[
            ScannerRunCompletion(
                scanner_name="gitleaks",
                scanner_version="8.21.2",
                status="completed",
                outcome_status="completed",
                db_freshness_state="not_applicable",
                image_digest="sha256:image-1",
            ),
        ],
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["gitleaks"],
        commit_sha="d" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=2,
        ancestry_status="recreated_or_force_pushed",
        cleanup_state="pending",
    )

    assert decision.coverage_completeness == "full"
    assert decision.closure_eligible is False
    assert "non_descendant_ancestry" in decision.ineligibility_reasons
    assert "cleanup_not_completed" in decision.ineligibility_reasons


def test_superseded_unstarted_work_is_never_closure_eligible():
    request = ScanCompletionRequest(
        contract_version=CURRENT_EVIDENCE_CONTRACT_VERSION,
        winning_attempt_id=uuid4(),
        execution_revision=1,
        scanner_runs=[],
    )

    decision = derive_scan_evidence_decision(
        request,
        expected_scanners=["trivy"],
        commit_sha="e" * 40,
        full_ref_name="refs/heads/main",
        branch_generation_number=1,
        ancestry_status="verified_descendant",
        cleanup_state="not_required",
        superseded_by_scan_id=str(uuid4()),
    )

    assert decision.coverage_completeness == "unknown"
    assert decision.closure_eligible is False
    assert "scan_superseded" in decision.ineligibility_reasons


def test_contract_version_negotiation_rejects_unsupported_versions():
    assert negotiate_contract_version(CURRENT_EVIDENCE_CONTRACT_VERSION) == CURRENT_EVIDENCE_CONTRACT_VERSION

    with pytest.raises(UnsupportedContractVersionError):
        negotiate_contract_version("2025-01-legacy.v0")

    with pytest.raises(UnsupportedContractVersionError):
        negotiate_contract_version(None, require_explicit=True)


def test_duplicate_or_unknown_scanners_and_forbidden_authority_fields_are_rejected():
    with pytest.raises(DuplicateScannerRunError):
        derive_scan_evidence_decision(
            ScanCompletionRequest(
                winning_attempt_id=uuid4(),
                execution_revision=1,
                scanner_runs=[
                    ScannerRunCompletion(scanner_name="trivy", status="completed"),
                    ScannerRunCompletion(scanner_name="trivy", status="completed"),
                ],
            ),
            expected_scanners=["trivy"],
            commit_sha="f" * 40,
        )

    with pytest.raises(UnknownScannerError):
        derive_scan_evidence_decision(
            ScanCompletionRequest(
                winning_attempt_id=uuid4(),
                execution_revision=1,
                scanner_runs=[
                    ScannerRunCompletion(scanner_name="unknown-scanner-xyz", status="completed"),
                ],
            ),
            expected_scanners=["trivy"],
            commit_sha="f" * 40,
        )

    with pytest.raises(ForbiddenWorkerAuthorityError):
        derive_scan_evidence_decision(
            ScanCompletionRequest(
                winning_attempt_id=uuid4(),
                execution_revision=1,
                scanner_runs=[
                    ScannerRunCompletion(scanner_name="trivy", status="completed"),
                ],
                summary_json={"closure_eligible": True},
            ),
            expected_scanners=["trivy"],
            commit_sha="f" * 40,
        )

    with pytest.raises(ValidationError):
        ScanCompletionRequest.model_validate(
            {
                "winning_attempt_id": str(uuid4()),
                "execution_revision": 1,
                "unknown_top_level_authority_flag": True,
            }
        )


def test_strict_json_parser_rejects_duplicate_keys_and_non_finite_numbers():
    with pytest.raises(DuplicateJsonKeyError):
        parse_strict_contract_json('{"execution_revision": 1, "execution_revision": 2}')

    with pytest.raises(DuplicateJsonKeyError):
        parse_strict_contract_json('{"summary_json": {"a": 1, "a": 2}}')

    with pytest.raises(InvalidJsonNumberError):
        parse_strict_contract_json('{"confidence_score": NaN}')

    with pytest.raises(InvalidJsonNumberError):
        parse_strict_contract_json('{"confidence_score": Infinity}')


def test_canonical_digest_is_order_independent_for_unordered_collections():
    attempt_id = uuid4()
    f1 = CanonicalFindingCandidate(
        canonical_fingerprint="fp-b",
        severity="high",
        category="vulnerability",
        title="Vuln B",
        primary_scanner="trivy",
        instance=CanonicalFindingInstance(path="b.lock", package_name="pkg-b", installed_version="1.0.0"),
        references=[
            CanonicalFindingReference(type="cve", value="CVE-2026-0002"),
            CanonicalFindingReference(type="advisory", value="GHSA-0002"),
        ],
    )
    f2 = CanonicalFindingCandidate(
        canonical_fingerprint="fp-a",
        severity="critical",
        category="secret",
        title="Secret A",
        primary_scanner="gitleaks",
        instance=CanonicalFindingInstance(path="src/config.py", line_start=10, line_end=10),
        references=[
            CanonicalFindingReference(type="rule", value="generic-api-key"),
        ],
    )
    f1_reordered_refs = CanonicalFindingCandidate(
        canonical_fingerprint="fp-b",
        severity="high",
        category="vulnerability",
        title="Vuln B",
        primary_scanner="trivy",
        instance=CanonicalFindingInstance(path="b.lock", package_name="pkg-b", installed_version="1.0.0"),
        references=[
            CanonicalFindingReference(type="advisory", value="GHSA-0002"),
            CanonicalFindingReference(type="cve", value="CVE-2026-0002"),
        ],
    )

    run_trivy = ScannerRunCompletion(scanner_name="trivy", scanner_version="0.58.1", status="completed")
    run_gitleaks = ScannerRunCompletion(scanner_name="gitleaks", scanner_version="8.21.2", status="completed")

    req_a = ScanCompletionRequest(
        winning_attempt_id=attempt_id,
        execution_revision=3,
        findings=[f1, f2],
        scanner_runs=[run_trivy, run_gitleaks],
    )
    req_b = ScanCompletionRequest(
        winning_attempt_id=attempt_id,
        execution_revision=3,
        findings=[f2, f1_reordered_refs],
        scanner_runs=[run_gitleaks, run_trivy],
    )

    digest_a = compute_canonical_evidence_digest(req_a)
    digest_b = compute_canonical_evidence_digest(req_b)
    assert len(digest_a) == 64
    assert digest_a == digest_b
