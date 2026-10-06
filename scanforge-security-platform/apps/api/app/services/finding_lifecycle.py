from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum

ABSENCE_THRESHOLD = 2
POLICY_VERSION = "scan-evidence-v1"
SERIES_KEY = "absence_series"
OBSERVED_BRANCHES_KEY = "observed_branches"
REOPEN_CHECKPOINT_KEY = "manual_reopen_checkpoint"
AUTO_ABSENCE_STATES = ("open", "not_observed")
SCANNER_EVIDENCE_KEY = "scanner_evidence_by_branch"
LIFECYCLE_METADATA_KEYS = frozenset({SERIES_KEY, OBSERVED_BRANCHES_KEY, REOPEN_CHECKPOINT_KEY, SCANNER_EVIDENCE_KEY})
PROVENANCE_FIELDS = ("scanner_version", "configuration_digest", "rules_version", "database_version")


def comparable_scanner_evidence(prior: Mapping[str, object], current: Mapping[str, object]) -> bool:
    if not prior.get("scanner_version") or not current.get("scanner_version"):
        return False
    if not any(prior.get(key) for key in PROVENANCE_FIELDS[1:]):
        return False
    return all(prior.get(key) == current.get(key) for key in PROVENANCE_FIELDS)


def record_scanner_evidence(metadata, *, branch, scanner, provenance) -> dict:
    result = dict(metadata or {})
    if not branch or not scanner or not provenance:
        return result
    branches = dict(result.get(SCANNER_EVIDENCE_KEY) or {})
    branch_evidence = dict(branches.get(branch) or {})
    branch_evidence[scanner] = {key: provenance.get(key) for key in PROVENANCE_FIELDS}
    branches[branch] = branch_evidence
    result[SCANNER_EVIDENCE_KEY] = branches
    return result


class AbsenceBlockReason(StrEnum):
    SCAN_TYPE_NOT_FULL = "scan_type_not_full"
    MISSING_COMMIT_SHA = "missing_commit_sha"
    MISSING_BRANCH_REF = "missing_branch_ref"
    SCANNER_EVIDENCE_INCOMPLETE = "scanner_evidence_incomplete"
    SCANNER_PROVENANCE_INCOMPLETE = "scanner_provenance_incomplete"
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


HUMAN_ACTIVE_STATES = frozenset({
    FindingWorkflowState.OPEN,
    FindingWorkflowState.REVIEWING,
    FindingWorkflowState.TO_FIX,
    FindingWorkflowState.NOT_OBSERVED,
})
HUMAN_TARGET_STATES = frozenset(FindingWorkflowState) - {FindingWorkflowState.NOT_OBSERVED}
HUMAN_TRANSITIONS = {
    state: HUMAN_TARGET_STATES if state in HUMAN_ACTIVE_STATES else frozenset({FindingWorkflowState.OPEN})
    for state in FindingWorkflowState
}


def validate_transition(current_state: str, next_state: str) -> FindingWorkflowState:
    current = validate_workflow_state(current_state)
    target = validate_workflow_state(next_state)
    if current == target:
        return target
    if target not in HUMAN_TRANSITIONS[current]:
        raise ValueError(f"Unsupported finding transition: {current.value} to {target.value}")
    return target


def transition_event_for_state(state: str) -> str:
    return TRANSITION_EVENTS[validate_workflow_state(state)]


def evaluate_scan_absence_evidence(scan_context: Mapping[str, object] | None) -> tuple[bool, list[str]]:
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
        expected = set(health.get("expected") or [])
        completed = set(health.get("completed") or [])
        failed = set(health.get("failed") or [])
        missing = set(health.get("missing") or [])
        if (
            not expected
            or failed
            or missing
            or not expected.issubset(completed)
            or health.get("complete") is not True
        ):
            reasons.append(AbsenceBlockReason.SCANNER_EVIDENCE_INCOMPLETE)
    if context.get("coverage_comparable") is not True:
        reasons.append(AbsenceBlockReason.SCANNER_PROVENANCE_INCOMPLETE)
    return not reasons, reasons


def observed_branches(metadata: Mapping[str, object] | None) -> list[str]:
    return [str(branch) for branch in (metadata or {}).get(OBSERVED_BRANCHES_KEY, [])]


def record_observed_branch(metadata: Mapping[str, object] | None, *, branch: str | None) -> dict:
    result = dict(metadata or {})
    if not branch:
        return result
    branches = [str(item) for item in result.get(OBSERVED_BRANCHES_KEY, [])]
    if branch not in branches:
        branches.append(branch)
    result[OBSERVED_BRANCHES_KEY] = branches
    series = dict(result.get(SERIES_KEY) or {})
    series.setdefault(branch, {"qualifying_absences": []})
    result[SERIES_KEY] = series
    return result


def reset_branch_series(metadata: Mapping[str, object] | None, *, branch: str) -> dict:
    result = dict(metadata or {})
    series = dict(result.get(SERIES_KEY) or {})
    series[branch] = {"qualifying_absences": []}
    result[SERIES_KEY] = series
    return result


def clear_absence_series(metadata: Mapping[str, object] | None) -> dict:
    result = dict(metadata or {})
    result[SERIES_KEY] = {
        branch: {"qualifying_absences": []} for branch in observed_branches(result)
    }
    return result


def record_manual_reopen_checkpoint(metadata: Mapping[str, object] | None, *, checkpoint: datetime) -> dict:
    result = clear_absence_series(metadata)
    result[REOPEN_CHECKPOINT_KEY] = checkpoint.astimezone(UTC).isoformat()
    return result


def _absence_entry(metadata: Mapping[str, object], branch: str) -> dict:
    series = metadata.get(SERIES_KEY)
    entry = series.get(branch) if isinstance(series, Mapping) else None
    if not isinstance(entry, Mapping):
        return {"qualifying_absences": []}
    return {
        "qualifying_absences": [
            dict(item) for item in entry.get("qualifying_absences", []) if isinstance(item, Mapping)
        ]
    }


def record_qualifying_absence(
    metadata: Mapping[str, object] | None,
    *,
    branch: str,
    scan_id: str,
    commit_sha: str,
) -> tuple[dict, bool]:
    result = dict(metadata or {})
    entry = _absence_entry(result, branch)
    if any(item.get("commit_sha") == commit_sha for item in entry["qualifying_absences"]):
        result[SERIES_KEY] = {**dict(result.get(SERIES_KEY) or {}), branch: entry}
        return result, False
    entry["qualifying_absences"].append({"scan_id": str(scan_id), "commit_sha": str(commit_sha)})
    result[SERIES_KEY] = {**dict(result.get(SERIES_KEY) or {}), branch: entry}
    return result, True


def branch_obligation_counts(metadata: Mapping[str, object] | None) -> dict[str, int]:
    return {
        branch: len(_absence_entry(metadata or {}, branch)["qualifying_absences"])
        for branch in observed_branches(metadata)
    }


def absence_transition_target(
    current_state: str, *, min_branch_absences: int, threshold: int = ABSENCE_THRESHOLD
) -> str | None:
    if current_state not in AUTO_ABSENCE_STATES:
        return None
    if min_branch_absences >= threshold:
        return FindingWorkflowState.FIXED.value
    if min_branch_absences >= 1 and current_state == FindingWorkflowState.OPEN.value:
        return FindingWorkflowState.NOT_OBSERVED.value
    return None


def scan_precedes_checkpoint(created_at: datetime | None, checkpoint: str | None) -> bool:
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
