from app.services.risk_scoring import calculate_risk_score


def test_risk_score_is_transparent_and_uses_available_signals():
    critical_open = calculate_risk_score(severity="critical", confidence_score=0.9, workflow_state="open")
    high_false_positive = calculate_risk_score(severity="high", confidence_score=0.9, workflow_state="false_positive")
    low_open = calculate_risk_score(severity="low", confidence_score=0.9, workflow_state="open")
    high_critical_repo = calculate_risk_score(
        severity="high",
        confidence_score=0.9,
        workflow_state="open",
        repository_importance="critical",
    )

    assert critical_open == 95
    assert high_false_positive == 11
    assert high_critical_repo == 90
    assert critical_open > low_open > high_false_positive


def test_risk_score_handles_missing_confidence():
    assert calculate_risk_score(severity="medium", confidence_score=None, workflow_state="reviewing") == 45
