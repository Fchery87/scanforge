"""R05: ordered-series disappearance rules (R03 D2/D3/D7).

The pure lifecycle layer decides whether a scan can authorize absence and
how per-branch qualifying-absence series move a finding.  Service-level
regressions live in test_findings_disappearance_scope.py.
"""
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
    }
    context.update(overrides)
    return context


def test_threshold_is_exactly_two_with_no_tenant_knob():
    assert ABSENCE_THRESHOLD == 2


def test_full_comparable_scan_evidence_is_eligible():
    eligible, reasons = evaluate_scan_absence_evidence(_context())
    assert eligible is True
    assert reasons == []


def test_diff_scan_never_authorizes_absence():
    eligible, reasons = evaluate_scan_absence_evidence(_context(scan_type="diff"))
    assert eligible is False
    assert AbsenceBlockReason.SCAN_TYPE_NOT_FULL in reasons


def test_failed_or_missing_scanner_evidence_blocks_absence():
    partial = dict(FULL_HEALTH, complete=False, failed=["gitleaks"])
    eligible, reasons = evaluate_scan_absence_evidence(_context(scanner_health=partial))
    assert eligible is False
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons

    missing = dict(FULL_HEALTH, complete=False, missing=["gitleaks"])
    eligible, reasons = evaluate_scan_absence_evidence(_context(scanner_health=missing))
    assert eligible is False
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons


def test_absent_or_unknown_scanner_health_is_ineligible_not_assumed_clean():
    eligible, reasons = evaluate_scan_absence_evidence(_context(scanner_health=None))
    assert eligible is False
    assert AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE in reasons


def test_missing_branch_or_commit_evidence_is_ineligible():
    eligible, reasons = evaluate_scan_absence_evidence(_context(branch_name=None))
    assert eligible is False
    assert AbsenceBlockReason.MISSING_BRANCH_REF in reasons

    eligible, reasons = evaluate_scan_absence_evidence(_context(commit_sha=None))
    assert eligible is False
    assert AbsenceBlockReason.MISSING_COMMIT_SHA in reasons


def test_same_commit_rerun_never_counts_twice():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta, first = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    meta, rerun = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-2", commit_sha="a" * 40
    )

    assert first is True
    assert rerun is False
    assert branch_obligation_counts(meta)["refs/heads/main"] == 1


def test_two_distinct_commit_absences_qualify():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta, first = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    meta, second = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-2", commit_sha="b" * 40
    )

    assert (first, second) == (True, True)
    assert branch_obligation_counts(meta)["refs/heads/main"] == ABSENCE_THRESHOLD


def test_presence_resets_branch_series():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    meta = reset_branch_series(meta, branch="refs/heads/main")

    assert branch_obligation_counts(meta)["refs/heads/main"] == 0


def test_absence_series_are_branch_local():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-2", commit_sha="b" * 40
    )
    meta = record_observed_branch(meta, branch="refs/heads/dev")

    assert branch_obligation_counts(meta)["refs/heads/main"] == 2
    assert branch_obligation_counts(meta)["refs/heads/dev"] == 0


def test_transition_requires_all_observed_branches():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta = record_observed_branch(meta, branch="refs/heads/dev")
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-2", commit_sha="b" * 40
    )

    min_count = min(branch_obligation_counts(meta)[b] for b in ("refs/heads/main", "refs/heads/dev"))
    assert absence_transition_target("open", min_branch_absences=min_count) is None


def test_transition_targets_follow_threshold():
    assert absence_transition_target("open", min_branch_absences=1) == "not_observed"
    assert absence_transition_target("open", min_branch_absences=2) == "fixed"
    assert absence_transition_target("not_observed", min_branch_absences=1) is None
    assert absence_transition_target("not_observed", min_branch_absences=2) == "fixed"


def test_human_block_states_never_auto_transition():
    assert absence_transition_target("reviewing", min_branch_absences=2) is None
    assert absence_transition_target("to_fix", min_branch_absences=2) is None
    assert absence_transition_target("accepted_risk", min_branch_absences=2) is None
    assert absence_transition_target("false_positive", min_branch_absences=2) is None
    assert absence_transition_target("duplicate", min_branch_absences=2) is None


def test_manual_reopen_clears_series_and_checkpoints():
    meta = record_observed_branch({}, branch="refs/heads/main")
    meta, _ = record_qualifying_absence(
        meta, branch="refs/heads/main", scan_id="scan-1", commit_sha="a" * 40
    )
    cleared = clear_absence_series(meta)

    assert branch_obligation_counts(cleared)["refs/heads/main"] == 0
    assert cleared["observed_branches"] == ["refs/heads/main"]


def test_scan_precedes_checkpoint_blocks_older_or_equal_scans():
    checkpoint = datetime.now(UTC)
    older = checkpoint - timedelta(minutes=5)
    newer = checkpoint + timedelta(minutes=5)

    assert scan_precedes_checkpoint(older, checkpoint.isoformat()) is True
    assert scan_precedes_checkpoint(checkpoint, checkpoint.isoformat()) is True
    assert scan_precedes_checkpoint(newer, checkpoint.isoformat()) is False
    assert scan_precedes_checkpoint(newer, None) is False


def test_scan_without_timestamp_cannot_prove_it_postdates_checkpoint():
    checkpoint = datetime.now(UTC).isoformat()
    assert scan_precedes_checkpoint(None, checkpoint) is True
