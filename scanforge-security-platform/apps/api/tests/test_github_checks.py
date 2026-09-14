import pytest

from app.services.github_checks import (
    CheckPublicationNotAllowed,
    build_check_run_payload,
    ensure_check_publication_allowed,
)


def test_check_run_payload_is_idempotent_for_same_scan_evidence():
    kwargs = dict(
        scan_id="11111111-1111-1111-1111-111111111111",
        head_sha="cafebabe",
        scan_status="completed",
        policy_status="pass",
        details_url="https://app.scanforge.example/scans/11111111-1111-1111-1111-111111111111",
        scanner_summary={"findings_total": 3, "scanners_complete": True, "scanners_total": 4},
    )
    first = build_check_run_payload(**kwargs)
    second = build_check_run_payload(**kwargs)
    assert first == second


def test_check_run_payload_queued_scan_has_no_conclusion():
    payload = build_check_run_payload(
        scan_id="scan-1",
        head_sha="cafebabe",
        scan_status="queued",
        details_url="https://app.scanforge.example/scans/scan-1",
    )
    assert payload["status"] == "queued"
    assert "conclusion" not in payload
    assert payload["head_sha"] == "cafebabe"
    assert payload["details_url"] == "https://app.scanforge.example/scans/scan-1"


def test_check_run_payload_completed_pass_maps_to_success():
    payload = build_check_run_payload(
        scan_id="scan-1",
        head_sha="cafebabe",
        scan_status="completed",
        policy_status="pass",
        details_url="https://app.scanforge.example/scans/scan-1",
    )
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "success"


def test_check_run_payload_completed_policy_fail_stays_advisory():
    """Advisory checks must never act as required merge gates: a policy failure is
    reported as neutral, not failure."""
    payload = build_check_run_payload(
        scan_id="scan-1",
        head_sha="cafebabe",
        scan_status="completed",
        policy_status="fail",
        details_url="https://app.scanforge.example/scans/scan-1",
    )
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "neutral"


def test_check_run_payload_failed_scan_maps_to_failure():
    payload = build_check_run_payload(
        scan_id="scan-1",
        head_sha="cafebabe",
        scan_status="failed",
        details_url="https://app.scanforge.example/scans/scan-1",
    )
    assert payload["status"] == "completed"
    assert payload["conclusion"] == "failure"


def test_check_run_output_reports_counts_and_policy_result():
    payload = build_check_run_payload(
        scan_id="scan-1",
        head_sha="cafebabe",
        scan_status="completed",
        policy_status="pass",
        details_url="https://app.scanforge.example/scans/scan-1",
        scanner_summary={"findings_total": 3, "scanners_complete": False, "scanners_total": 4},
    )
    summary = payload["output"]["summary"]
    assert "policy pass" in summary
    assert "3" in summary
    assert "3/4" in summary  # scanner gap is explicit


def test_check_publication_rejects_disabled_principal():
    with pytest.raises(CheckPublicationNotAllowed):
        ensure_check_publication_allowed(principal_enabled=False, principal_is_replacement=False)


def test_check_publication_rejects_replacement_principal():
    """D6: replacement has read/recovery capability, not historical write authority."""
    with pytest.raises(CheckPublicationNotAllowed) as exc_info:
        ensure_check_publication_allowed(principal_enabled=True, principal_is_replacement=True)
    assert "read/recovery" in str(exc_info.value)


def test_check_publication_allows_enabled_original_principal():
    ensure_check_publication_allowed(principal_enabled=True, principal_is_replacement=False)
