"""Finding lifecycle policy domain rules (ADR-004, R03 D2/D3/D7).

This module owns the ordered-series disappearance rules:

- Absence evidence is only valid for a full, healthy, comparable scan on a
  concrete branch ref with a resolved commit (D2/D3).
- Qualifying absences form a branch-local series.  Two distinct-commit
  absences on the same branch satisfy that branch's obligation (D2).
- Presence resets a branch series (D2).
- A manual reopen clears every series and records a checkpoint; scans issued
  at or before the checkpoint can never reclose the finding (D7).

Commit ancestry between consecutive absences is verified through the
provider-compare receipts owned by the scan lifecycle (D1); this module
requires distinct commits and arrival order and must be handed ordered,
already-ancestry-checked scan context.
"""
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum

ABSENCE_THRESHOLD = 2
POLICY_VERSION = "scan-evidence-v1"

SERIES_KEY = "absence_series"
OBSERVED_BRANCHES_KEY = "observed_branches"
REOPEN_CHECKPOINT_KEY = "manual_reopen_checkpoint"

# States where machine absence transitions are allowed at all.
AUTO_ABSENCE_STATES = ("open", "not_observed")
# Human triage states that record observations but never auto-transition.
HUMAN_BLOCK_STATES = ("reviewing", "to_fix")


class AbsenceBlockReason(StrEnum):
    SCAN_TYPE_NOT_FULL = "scan_type_not_full"
    MISSING_COMMIT_SHA = "missing_commit_sha"
    MISSING_BRANCH_REF = "missing_branch_ref"
    SCANNER_EVIDENCE_INCOMPLETE = "scanner_evidence_incomplete"
    UNKNOWN_BRANCH_PROVENANCE = "unknown_branch_provenance"
    BRANCH_NOT_OBSERVED = "branch_not_observed"
    MANUAL_REOPEN_CHECKPOINT = "manual_reopen_checkpoint"
    UNRESOLVED_BRANCH_OBLIGATION = "unresolved_branch_obligation"
    HUMAN_BLOCK_STATE = "human_block_state"


class FindingWorkflowState(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    TO_FIX = "to_fix"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"
    DUPLICATE = "duplicate"
    NOT_OBSERVED = "not_observed"
    FIXED = "fixed"


TRANSITION_EVENTS: dict[FindingWorkflowState, str] = {
    FindingWorkflowState.OPEN: "reopened",
    FindingWorkflowState.REVIEWING: "marked_reviewing",
    FindingWorkflowState.TO_FIX: "marked_to_fix",
    FindingWorkflowState.ACCEPTED_RISK: "accepted_risk",
    FindingWorkflowState.FALSE_POSITIVE: "marked_false_positive",
    FindingWorkflowState.DUPLICATE: "duplicate",
    FindingWorkflowState.NOT_OBSERVED: "marked_not_observed",
    FindingWorkflowState.FIXED: "fixed",
}


def validate_workflow_state(state: str) -> FindingWorkflowState:
    try:
        return FindingWorkflowState(state)
    except ValueError as exc:
        raise ValueError(f"Unsupported finding workflow state: {state}") from exc


def validate_transition(_current_state: str, next_state: str) -> FindingWorkflowState:
    return validate_workflow_state(next_state)


def transition_event_for_state(state: str) -> str:
    return TRANSITION_EVENTS[validate_workflow_state(state)]


def evaluate_scan_absence_evidence(scan_context: Mapping[str, object] | None) -> tuple[bool, list[str]]:
    """Decide whether a completed scan may authorize any absence observation.

    Failed or missing scanner evidence is treated as committed evidence (D3):
    a scan without explicit complete, healthy coverage for every expected
    scanner is ineligible and never proves a finding disappeared.
    """
    context = scan_context or {}
    reasons: list[str] = []

    if context.get("scan_type") != "full":
        reasons.append(AbsenceBlockReason.SCAN_TYPE_NOT_FULL)
    if not context.get("commit_sha"):
        reasons.append(AbsenceBlockReason.MISSING_COMMIT_SHA)
    if not context.get("branch_name"):
        reasons.append(AbsenceBlockReason.MISSING_BRANCH_REF)

    health = context.get("scanner_health")
    if not isinstance(health, Mapping):
        reasons.append(AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE)
    else:
        expected = list(health.get("expected") or [])
        completed = set(health.get("completed") or [])
        failed = set(health.get("failed") or [])
        missing = set(health.get("missing") or [])
        if (
            not expected
            or failed
            or missing
            or not set(expected).issubset(completed)
            or health.get("complete") is not True
        ):
            reasons.append(AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE)

    return (not reasons, reasons)


def observed_branches(metadata: Mapping[str, object] | None) -> list[str]:
    meta = metadata or {}
    return [str(branch) for branch in (meta.get(OBSERVED_BRANCHES_KEY) or [])]


def record_observed_branch(metadata: Mapping[str, object] | None, *, branch: str) -> dict:
    """Record positive evidence that the finding exists on a branch ref."""
    meta = dict(metadata or {})
    if not branch:
        return meta
    known = meta.get(OBSERVED_BRANCHES_KEY)
    branches = [str(item) for item in known] if isinstance(known, list) else []
    if branch not in branches:
        branches.append(branch)
    meta[OBSERVED_BRANCHES_KEY] = branches
    series = dict(meta.get(SERIES_KEY) or {})
    series.setdefault(branch, {"qualifying_absences": []})
    meta[SERIES_KEY] = series
    return meta


def reset_branch_series(metadata: Mapping[str, object] | None, *, branch: str) -> dict:
    """Presence wins: clear a branch's qualifying absences (D2)."""
    meta = dict(metadata or {})
    series = dict(meta.get(SERIES_KEY) or {})
    series[branch] = {"qualifying_absences": []}
    meta[SERIES_KEY] = series
    return meta


def clear_absence_series(metadata: Mapping[str, object] | None) -> dict:
    """Manual reopen: clear every branch series, keep branch provenance."""
    meta = dict(metadata or {})
    series: dict[str, dict] = {}
    for branch in observed_branches(meta):
        series[branch] = {"qualifying_absences": []}
    meta[SERIES_KEY] = series
    return meta


def record_manual_reopen_checkpoint(metadata: Mapping[str, object] | None, *, checkpoint: datetime) -> dict:
    meta = clear_absence_series(metadata)
    meta[REOPEN_CHECKPOINT_KEY] = checkpoint.astimezone(UTC).isoformat()
    return meta


def _absence_entry(meta: Mapping[str, object], branch: str) -> dict:
    series = meta.get(SERIES_KEY)
    entry = series.get(branch) if isinstance(series, Mapping) else None
    if not isinstance(entry, Mapping):
        return {"qualifying_absences": []}
    return {
        "qualifying_absences": [
            dict(item) for item in (entry.get("qualifying_absences") or []) if isinstance(item, Mapping)
        ]
    }


def record_qualifying_absence(
    metadata: Mapping[str, object] | None,
    *,
    branch: str,
    scan_id: str,
    commit_sha: str,
) -> tuple[dict, bool]:
    """Append a qualifying absence; a rerun at the same commit never counts."""
    meta = dict(metadata or {})
    entry = _absence_entry(meta, branch)
    if any(item.get("commit_sha") == commit_sha for item in entry["qualifying_absences"]):
        meta[SERIES_KEY] = {**dict(meta.get(SERIES_KEY) or {}), branch: entry}
        return meta, False
    entry["qualifying_absences"].append({"scan_id": str(scan_id), "commit_sha": str(commit_sha)})
    meta[SERIES_KEY] = {**dict(meta.get(SERIES_KEY) or {}), branch: entry}
    return meta, True


def branch_obligation_counts(metadata: Mapping[str, object] | None) -> dict[str, int]:
    meta = metadata or {}
    counts: dict[str, int] = {}
    for branch in observed_branches(meta):
        counts[branch] = len(_absence_entry(meta, branch)["qualifying_absences"])
    return counts


def absence_transition_target(
    current_state: str, *, min_branch_absences: int, threshold: int = ABSENCE_THRESHOLD
) -> str | None:
    """Finding-level target from the weakest branch obligation.

    The repository-level finding may move only when every observed branch
    has reached the same qualifying-absence depth; a branch with no
    qualifying absence keeps the minimum at zero.
    """
    if current_state not in AUTO_ABSENCE_STATES:
        return None
    if min_branch_absences >= threshold:
        return FindingWorkflowState.FIXED.value
    if min_branch_absences >= 1 and current_state == FindingWorkflowState.OPEN.value:
        return FindingWorkflowState.NOT_OBSERVED.value
    return None


def scan_precedes_checkpoint(created_at: datetime | None, checkpoint: str | None) -> bool:
    """True unless the scan provably issued strictly after the checkpoint.

    A scan with no issue timestamp, or one issued at/before a manual reopen
    checkpoint, can never reclose the finding (D7).
    """
    if not checkpoint:
        return False
    try:
        checkpoint_dt = datetime.fromisoformat(str(checkpoint))
    except ValueError:
        return True
    if created_at is None:
        return True
    scan_dt = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    checkpoint_dt = checkpoint_dt if checkpoint_dt.tzinfo else checkpoint_dt.replace(tzinfo=UTC)
    return scan_dt <= checkpoint_dt
