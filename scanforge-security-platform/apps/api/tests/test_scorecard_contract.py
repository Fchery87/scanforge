from app.api.v1.routes.scorecard import ScorecardResponse


def test_scorecard_response_uses_open_critical_field():
    payload = ScorecardResponse.model_validate(
        {
            "project_id": "project-1",
            "overall_score": 91,
            "security_score": 88,
            "secrets_score": 100,
            "dependency_score": 90,
            "grade": "A",
            "open_critical": 2,
            "open_high": 4,
            "open_medium": 6,
            "open_low": 1,
            "open_total": 13,
            "fixed_30d": 3,
            "new_this_week": 5,
            "scan_count": 7,
            "last_scan_at": "2026-03-30T00:00:00Z",
        }
    )

    assert payload.open_critical == 2
