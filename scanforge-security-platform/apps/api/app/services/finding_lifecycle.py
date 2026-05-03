from enum import StrEnum


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


def can_mark_not_observed(scan_summary: dict | None, *, primary_scanner: str | None) -> bool:
    if not primary_scanner:
        return False

    scanner_health = (scan_summary or {}).get("scanner_health") or {}
    completed = scanner_health.get("completed") or []
    return primary_scanner in completed


def can_promote_to_fixed(current_state: str, *, not_observed_count: int, threshold: int = 2) -> bool:
    return current_state == FindingWorkflowState.NOT_OBSERVED and not_observed_count >= threshold
