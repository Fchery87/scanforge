from app.services.policy_evaluation import evaluate_advisory_policy


def test_advisory_policy_passes_when_risk_sla_and_scanner_health_are_acceptable():
    result = evaluate_advisory_policy(
        risk_score_average=40,
        sla_overdue=0,
        scanner_health={"complete_scans": 3, "partial_scans": 0},
    )

    assert result == {"status": "pass", "blocking": False, "reasons": []}


def test_advisory_policy_fails_without_blocking_when_signals_are_unhealthy():
    result = evaluate_advisory_policy(
        risk_score_average=80,
        sla_overdue=2,
        scanner_health={"complete_scans": 1, "partial_scans": 2},
    )

    assert result["status"] == "fail"
    assert result["blocking"] is False
    assert result["reasons"] == ["risk_score_high", "sla_overdue", "partial_scanner_health"]
