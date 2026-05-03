SEVERITY_BASE_SCORE = {
    "critical": 90,
    "high": 70,
    "medium": 45,
    "low": 20,
    "info": 5,
}

WORKFLOW_MULTIPLIER = {
    "open": 1.0,
    "reviewing": 1.0,
    "to_fix": 1.0,
    "not_observed": 0.4,
    "accepted_risk": 0.25,
    "false_positive": 0.15,
    "duplicate": 0.15,
    "fixed": 0.0,
}

IMPORTANCE_BONUS = {
    "critical": 15,
    "high": 8,
    "normal": 0,
    "low": -10,
}


def calculate_risk_score(
    *,
    severity: str,
    confidence_score: float | None,
    workflow_state: str,
    repository_importance: str = "normal",
) -> int:
    base = SEVERITY_BASE_SCORE.get(severity, 0)
    confidence_bonus = int(((confidence_score or 0) * 5) + 0.5)
    importance_bonus = IMPORTANCE_BONUS.get(repository_importance, 0)
    multiplier = WORKFLOW_MULTIPLIER.get(workflow_state, 1.0)
    return max(0, min(100, int(((base + confidence_bonus + importance_bonus) * multiplier) + 0.5)))
