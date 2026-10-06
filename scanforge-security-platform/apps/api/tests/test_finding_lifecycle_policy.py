from datetime import UTC, datetime, timedelta

from app.services.finding_lifecycle import (
    ABSENCE_THRESHOLD,
    AbsenceBlockReason,
    absence_transition_target,
    branch_obligation_counts,
    clear_absence_series,
    evaluate_scan_absence_evidence,
    record_observed_branch,
    record_qualifying_absence,
    reset_branch_series,
    scan_precedes_checkpoint,
)

FULL_HEALTH = {
    "expected": ["trivy", "gitleaks"],
    "completed": ["trivy", "gitleaks"],
    "failed": [],
    "missing": [],
    "complete": True,
}


def _context(**overrides):
    context = {
        "scan_type": "full",
        "branch_name": "refs/heads/main",
        "commit_sha": "a" * 40,
        "scanner_health": dict(FULL_HEALTH),
        "coverage_comparable": True,
    }
    context.update(overrides)
    return context


def test_full_healthy_scan_is_eligible_for_absence():
    assert evaluate_scan_absence_evidence(_context()) == (True, [])


def test_diff_partial_and_unknown_scan_evidence_is_ineligible():
    eligible, reasons = evaluate_scan_absence_evidence(_context(scan_type="diff"))
    assert not eligible
    assert AbsenceBlockReason.SCAN_TYPE_NOT_FULL in reasons

    eligible, reasons = evaluate_scan_absence_evidence(
        _context(scanner_health={**FULL_HEALTH, "complete": False, "failed": ["gitleaks"]})
    )
    assert not eligible
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons

    eligible, reasons = evaluate_scan_absence_evidence(_context(scanner_health=None))
    assert not eligible
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons

    eligible, reasons = evaluate_scan_absence_evidence(_context(coverage_comparable=False))
    assert not eligible
    assert AbsenceBlockReason.SCANNER_PROVENANCE_INCOMPLETE in reasons


def test_missing_ref_or_commit_is_ineligible():
    assert not evaluate_scan_absence_evidence(_context(branch_name=None))[0]
    assert not evaluate_scan_absence_evidence(_context(commit_sha=None))[0]


def test_absence_series_need_distinct_commits_and_reset_on_presence():
    metadata = record_observed_branch({}, branch="refs/heads/main")
    metadata, first = record_qualifying_absence(
        metadata, branch="refs/heads/main", scan_id="scan-1", commit_sha="a"
    )
    metadata, rerun = record_qualifying_absence(
        metadata, branch="refs/heads/main", scan_id="scan-2", commit_sha="a"
    )
    assert first is True
    assert rerun is False
    assert branch_obligation_counts(metadata)["refs/heads/main"] == 1

    metadata = reset_branch_series(metadata, branch="refs/heads/main")
    assert branch_obligation_counts(metadata)["refs/heads/main"] == 0


def test_branch_obligations_and_transition_threshold():
    metadata = record_observed_branch({}, branch="refs/heads/main")
    metadata = record_observed_branch(metadata, branch="refs/heads/dev")
    metadata, _ = record_qualifying_absence(
        metadata, branch="refs/heads/main", scan_id="scan-1", commit_sha="a"
    )
    metadata, _ = record_qualifying_absence(
        metadata, branch="refs/heads/main", scan_id="scan-2", commit_sha="b"
    )
    assert branch_obligation_counts(metadata) == {"refs/heads/main": 2, "refs/heads/dev": 0}
    assert absence_transition_target("open", min_branch_absences=0) is None
    assert absence_transition_target("open", min_branch_absences=1) == "not_observed"
    assert absence_transition_target("open", min_branch_absences=ABSENCE_THRESHOLD) == "fixed"
    assert absence_transition_target("reviewing", min_branch_absences=ABSENCE_THRESHOLD) is None


def test_manual_reopen_clears_series_and_old_scans_cannot_reclose():
    metadata = record_observed_branch({}, branch="refs/heads/main")
    metadata, _ = record_qualifying_absence(
        metadata, branch="refs/heads/main", scan_id="scan-1", commit_sha="a"
    )
    cleared = clear_absence_series(metadata)
    assert branch_obligation_counts(cleared)["refs/heads/main"] == 0

    checkpoint = datetime.now(UTC)
    assert scan_precedes_checkpoint(checkpoint - timedelta(minutes=1), checkpoint.isoformat())
    assert scan_precedes_checkpoint(checkpoint, checkpoint.isoformat())
    assert not scan_precedes_checkpoint(checkpoint + timedelta(minutes=1), checkpoint.isoformat())
    assert scan_precedes_checkpoint(None, checkpoint.isoformat())
