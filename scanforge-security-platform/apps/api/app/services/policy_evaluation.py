def evaluate_advisory_policy(
    *,
    risk_score_average: float | None,
    sla_overdue: int,
    scanner_health: dict,
) -> dict:
    reasons = []

    if risk_score_average is not None and risk_score_average >= 70:
        reasons.append("risk_score_high")
    if sla_overdue > 0:
        reasons.append("sla_overdue")
    if scanner_health.get("partial_scans", 0) > 0:
        reasons.append("partial_scanner_health")

    return {
        "status": "fail" if reasons else "pass",
        "blocking": False,
        "reasons": reasons,
    }
