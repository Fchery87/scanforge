"""#45 / P1.8: per-capability coverage assessment derived from committed ScannerRun evidence.

Only analyzer-reported measurements are surfaced; nothing is inferred or computed into
percentages. `not_applicable` requires analyzer evidence of zero inputs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.routes import scans
from app.services.evidence_contract import derive_capability_coverage


def _run(name, *, status="completed", outcome=None, coverage=None, metadata=None):
    meta = dict(metadata or {})
    if coverage is not None:
        meta["coverage"] = coverage
    return SimpleNamespace(
        scanner_name=name,
        status=status,
        outcome_status=outcome or status,
        metadata_json=meta or None,
    )


def _by_cap(result):
    return {c["capability"]: c for c in result}


def test_complete_when_analyzer_reports_full_supported_scope():
    result = derive_capability_coverage(
        [
            _run(
                "gitleaks",
                coverage={"declared_scope": "git working tree", "inputs_found": 120, "inputs_supported": 120},
            )
        ],
        expected_scanners=["gitleaks"],
    )
    secrets = _by_cap(result)["secrets"]
    assert secrets["state"] == "complete"
    scanner = secrets["scanners"][0]
    assert scanner["declared_scope"] == "git working tree"
    assert scanner["inputs_found"] == 120
    assert scanner["inputs_supported"] == 120


def test_healthy_run_without_reported_measurements_is_unknown_not_complete():
    result = derive_capability_coverage([_run("semgrep")], expected_scanners=["semgrep"])
    sast = _by_cap(result)["sast"]
    assert sast["state"] == "unknown"
    assert "no_analyzer_coverage_report" in sast["reasons"]
    scanner = sast["scanners"][0]
    # No invented measurements.
    assert scanner["inputs_found"] is None
    assert scanner["inputs_supported"] is None
    assert scanner["parse_failures"] is None


def test_partial_for_each_reported_limitation():
    limitations = {
        "unsupported": {"inputs_found": 4, "inputs_supported": 3, "unsupported_inputs": ["poetry.lock"]},
        "parse_failures": {"inputs_found": 4, "inputs_supported": 4, "parse_failures": 1},
        "truncated": {"inputs_found": 4, "inputs_supported": 4, "truncated": True},
        "timed_out": {"inputs_found": 4, "inputs_supported": 4, "timed_out": True},
        "supported_less_than_found": {"inputs_found": 4, "inputs_supported": 2},
    }
    for label, cov in limitations.items():
        result = derive_capability_coverage([_run("trivy", coverage=cov)], expected_scanners=["trivy"])
        assert _by_cap(result)["dependencies"]["state"] == "partial", label


def test_exclusions_are_listed_and_make_scope_partial_only_when_reported_as_limiting():
    cov = {"inputs_found": 3, "inputs_supported": 3, "exclusions": ["vendor/**"]}
    result = derive_capability_coverage([_run("checkov", coverage=cov)], expected_scanners=["checkov"])
    iac = _by_cap(result)["iac"]
    assert iac["scanners"][0]["exclusions"] == ["vendor/**"]
    # Exclusions are part of the declared scope; complete is relative to declared scope.
    assert iac["state"] == "complete"


def test_not_applicable_requires_analyzer_evidence_of_zero_inputs():
    with_evidence = derive_capability_coverage(
        [_run("checkov", outcome="skipped_unapplicable", coverage={"inputs_found": 0, "inputs_supported": 0})],
        expected_scanners=["checkov"],
    )
    iac = _by_cap(with_evidence)["iac"]
    assert iac["state"] == "not_applicable"
    assert iac["scanners"][0]["inputs_found"] == 0

    without_evidence = derive_capability_coverage(
        [_run("checkov", outcome="skipped_unapplicable")], expected_scanners=["checkov"]
    )
    assert _by_cap(without_evidence)["iac"]["state"] == "unknown"

    # Zero inputs reported by a run that did not complete is not evidence either.
    failed = derive_capability_coverage(
        [_run("checkov", status="failed", coverage={"inputs_found": 0})], expected_scanners=["checkov"]
    )
    assert _by_cap(failed)["iac"]["state"] == "unknown"


def test_failed_timed_out_and_missing_scanners_are_unknown_with_reason():
    failed = derive_capability_coverage([_run("gitleaks", status="failed")], expected_scanners=["gitleaks"])
    assert _by_cap(failed)["secrets"]["state"] == "unknown"
    assert "scanner_failed" in _by_cap(failed)["secrets"]["scanners"][0]["reasons"]

    timed_out = derive_capability_coverage(
        [_run("semgrep", status="failed", outcome="timed_out")], expected_scanners=["semgrep"]
    )
    assert "scanner_timed_out" in _by_cap(timed_out)["sast"]["scanners"][0]["reasons"]
    assert _by_cap(timed_out)["sast"]["state"] == "unknown"

    missing = derive_capability_coverage([], expected_scanners=["semgrep"])
    assert _by_cap(missing)["sast"]["state"] == "unknown"
    assert "no_scanner_run" in _by_cap(missing)["sast"]["scanners"][0]["reasons"]


def test_multi_scanner_capability_is_partial_when_only_some_scanners_are_complete():
    full = {"inputs_found": 2, "inputs_supported": 2}
    result = derive_capability_coverage(
        [_run("trivy", coverage=full), _run("syft", status="failed")],
        expected_scanners=["trivy", "syft"],
    )
    assert _by_cap(result)["dependencies"]["state"] == "partial"

    both = derive_capability_coverage(
        [_run("trivy", coverage=full), _run("syft", coverage=full)], expected_scanners=["trivy", "syft"]
    )
    assert _by_cap(both)["dependencies"]["state"] == "complete"


def test_capabilities_without_an_expected_scanner_are_not_declared():
    result = derive_capability_coverage(
        [_run("gitleaks", coverage={"inputs_found": 1, "inputs_supported": 1})], expected_scanners=["gitleaks"]
    )
    assert [c["capability"] for c in result] == ["secrets"]


def test_malformed_reports_are_ignored_not_trusted():
    cov = {"inputs_found": -3, "inputs_supported": "many", "parse_failures": True, "truncated": "yes"}
    result = derive_capability_coverage([_run("trivy", coverage=cov)], expected_scanners=["trivy"])
    scanner = _by_cap(result)["dependencies"]["scanners"][0]
    assert scanner["inputs_found"] is None
    assert scanner["inputs_supported"] is None
    assert scanner["parse_failures"] is None
    assert scanner["truncated"] is None
    assert _by_cap(result)["dependencies"]["state"] == "unknown"


def test_scan_detail_exposes_coverage_from_scanner_runs_and_contract_scope():
    scan_id = uuid4()
    now = datetime.now(UTC)
    scan = SimpleNamespace(
        id=scan_id,
        project_id=uuid4(),
        repository_id=uuid4(),
        trigger_type="manual",
        scan_type="full",
        status="completed",
        branch_name="main",
        commit_sha="deadbeef",
        pull_request_number=None,
        requested_by_user_id=None,
        error_message=None,
        summary_json={"scanner_health": {"expected": ["gitleaks", "checkov"]}},
        created_at=now,
        updated_at=now,
        scanner_runs=[
            SimpleNamespace(
                id=uuid4(),
                scan_id=scan_id,
                scanner_name="gitleaks",
                scanner_version="8",
                status="completed",
                duration_ms=1,
                exit_code=0,
                error_message=None,
                artifact_uri=None,
                metadata_json={"coverage": {"inputs_found": 5, "inputs_supported": 5}},
                created_at=now,
                updated_at=now,
            )
        ],
    )

    payload = scans._apply_scan_download_urls(scan, org_id=uuid4(), project_id=scan.project_id)

    states = {c.capability: c.state for c in payload.capability_coverage}
    assert states == {"secrets": "complete", "iac": "unknown"}
