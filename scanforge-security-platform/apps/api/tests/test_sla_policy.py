from datetime import date

from app.services.sla_policy import preview_sla_status


def test_sla_preview_reports_exempt_workflow_states():
    assert preview_sla_status(workflow_state="false_positive", due_date=date(2026, 1, 1), today=date(2026, 1, 10)) == {
        "status": "not_applicable",
        "days_remaining": None,
        "reason": "workflow_state_exempt",
    }


def test_sla_preview_reports_due_date_pressure():
    assert preview_sla_status(workflow_state="open", due_date=date(2026, 1, 1), today=date(2026, 1, 3))["status"] == "overdue"
    assert preview_sla_status(workflow_state="open", due_date=date(2026, 1, 5), today=date(2026, 1, 3))["status"] == "due_soon"
    assert preview_sla_status(workflow_state="open", due_date=date(2026, 1, 20), today=date(2026, 1, 3))["status"] == "on_track"


def test_sla_preview_reports_missing_policy():
    assert preview_sla_status(workflow_state="open", due_date=None, today=date(2026, 1, 3)) == {
        "status": "no_sla",
        "days_remaining": None,
        "reason": "missing_due_date",
    }
