from app.services.github_pr_advisory import build_pr_advisory_payload


def test_pr_advisory_payload_is_non_blocking_and_uses_policy_evaluation():
    payload = build_pr_advisory_payload(
        scan_id="scan-1",
        policy_evaluation={"status": "fail", "blocking": False, "reasons": ["risk_score_high"]},
    )

    assert payload == {
        "scan_id": "scan-1",
        "state": "neutral",
        "blocking": False,
        "summary": "Advisory policy evaluation failed: risk_score_high",
    }
