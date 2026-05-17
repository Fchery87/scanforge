from datetime import UTC, date, datetime

EXEMPT_WORKFLOW_STATES = {"accepted_risk", "false_positive", "duplicate", "fixed"}
SLA_DUE_SOON_DAYS = 3


def preview_sla_status(
    *,
    workflow_state: str,
    due_date: date | None,
    today: date | None = None,
) -> dict:
    if workflow_state in EXEMPT_WORKFLOW_STATES:
        return {"status": "not_applicable", "days_remaining": None, "reason": "workflow_state_exempt"}

    if due_date is None:
        return {"status": "no_sla", "days_remaining": None, "reason": "missing_due_date"}

    current_date = today or datetime.now(UTC).date()
    days_remaining = (due_date - current_date).days
    if days_remaining < 0:
        status = "overdue"
    elif days_remaining <= SLA_DUE_SOON_DAYS:
        status = "due_soon"
    else:
        status = "on_track"

    return {"status": status, "days_remaining": days_remaining, "reason": None}
