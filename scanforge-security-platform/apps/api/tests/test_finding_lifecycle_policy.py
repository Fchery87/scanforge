import pytest

from app.services.finding_lifecycle import (
    FindingWorkflowState,
    can_mark_not_observed,
    can_promote_to_fixed,
    transition_event_for_state,
    validate_transition,
)


def test_finding_workflow_states_match_domain_policy():
    assert {state.value for state in FindingWorkflowState} == {
        "open",
        "reviewing",
        "to_fix",
        "accepted_risk",
        "false_positive",
        "duplicate",
        "not_observed",
        "fixed",
    }


def test_finding_lifecycle_policy_rejects_unknown_states():
    with pytest.raises(ValueError, match="Unsupported finding workflow state"):
        validate_transition("open", "suppressed")


def test_finding_lifecycle_policy_names_transition_events():
    assert transition_event_for_state("accepted_risk") == "accepted_risk"
    assert transition_event_for_state("false_positive") == "marked_false_positive"
    assert transition_event_for_state("to_fix") == "marked_to_fix"


def test_not_observed_requires_complete_relevant_scanner_coverage():
    complete_summary = {
        "scanner_health": {
            "expected": ["trivy", "gitleaks"],
            "completed": ["trivy", "gitleaks"],
            "failed": [],
            "missing": [],
            "complete": True,
        }
    }
    partial_summary = {
        "scanner_health": {
            "expected": ["trivy", "gitleaks"],
            "completed": ["trivy"],
            "failed": ["gitleaks"],
            "missing": [],
            "complete": False,
        }
    }

    assert can_mark_not_observed(complete_summary, primary_scanner="gitleaks") is True
    assert can_mark_not_observed(partial_summary, primary_scanner="gitleaks") is False
    assert can_mark_not_observed(complete_summary, primary_scanner="semgrep") is False


def test_fixed_promotion_requires_not_observed_threshold():
    assert can_promote_to_fixed("open", not_observed_count=3) is False
    assert can_promote_to_fixed("not_observed", not_observed_count=1) is False
    assert can_promote_to_fixed("not_observed", not_observed_count=2) is True
