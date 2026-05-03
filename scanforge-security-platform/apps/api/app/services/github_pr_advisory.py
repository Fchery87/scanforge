def build_pr_advisory_payload(*, scan_id: str, policy_evaluation: dict) -> dict:
    status = policy_evaluation.get("status", "pass")
    reasons = policy_evaluation.get("reasons") or []
    if status == "pass":
        summary = "Advisory policy evaluation passed"
    else:
        summary = f"Advisory policy evaluation failed: {', '.join(reasons)}"

    return {
        "scan_id": scan_id,
        "state": "neutral",
        "blocking": False,
        "summary": summary,
    }
