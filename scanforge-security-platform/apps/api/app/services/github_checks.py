"""Advisory GitHub Check-run payload builder (R10).

Pure module: deterministic output, no I/O and no clock reads, so rebuilding the
payload for the same scan evidence always yields an identical Check payload.
That keeps Check publication retryable without creating duplicate Checks
(plan R10: "one persisted Check identity per scan", never a required merge gate).
"""


class CheckPublicationNotAllowed(ValueError):
    """Raised when the acting principal may not publish historical scan evidence."""


def ensure_check_publication_allowed(*, principal_enabled: bool, principal_is_replacement: bool) -> None:
    """Gate Check publication on principal authority.

    D6 (spec/2026-09-13-scan-evidence-decisions.md): "Historical winning attempt may
    retrieve after lease expiry only with enabled principal. Replacement has
    read/recovery capability, not historical write authority."

    Publishing a Check writes scan evidence history to GitHub, so only the enabled
    original principal may publish. Disabled principals and replacement principals
    are rejected here before any GitHub call is attempted.
    """
    if not principal_enabled:
        raise CheckPublicationNotAllowed("check publication requires an enabled principal")
    if principal_is_replacement:
        raise CheckPublicationNotAllowed(
            "replacement principal has read/recovery capability only, not historical write authority"
        )


def build_check_run_payload(
    *,
    scan_id: str,
    head_sha: str,
    scan_status: str,
    details_url: str,
    policy_status: str = "pass",
    policy_reasons: list[str] | None = None,
    scanner_summary: dict | None = None,
    name: str = "scanforge-security-scan",
) -> dict:
    """Build the GitHub Check-run create payload for one scan.

    status/conclusion mapping (advisory: never a required merge gate):
    - queued          -> status queued, no conclusion
    - running         -> status in_progress, no conclusion
    - completed/pass  -> completed + success
    - completed/fail  -> completed + neutral (policy failure is advisory information)
    - partial         -> completed + neutral (scanner gaps reported in output)
    - failed          -> completed + failure
    - canceled        -> completed + cancelled
    """
    reasons = policy_reasons or []
    summary_data = scanner_summary or {}

    if scan_status == "queued":
        status = "queued"
        conclusion = None
    elif scan_status == "running":
        status = "in_progress"
        conclusion = None
    elif scan_status == "completed":
        status = "completed"
        conclusion = "success" if policy_status == "pass" else "neutral"
    elif scan_status == "partial":
        status = "completed"
        conclusion = "neutral"
    elif scan_status == "failed":
        status = "completed"
        conclusion = "failure"
    elif scan_status == "canceled":
        status = "completed"
        conclusion = "cancelled"
    else:  # unknown statuses keep the Check in progress rather than guessing
        status = "in_progress"
        conclusion = None

    payload: dict = {
        "name": name,
        "head_sha": head_sha,
        "status": status,
        "details_url": details_url,
        "output": {
            "title": f"ScanForge security scan {scan_id}",
            "summary": _summary_text(
                scan_id=scan_id,
                scan_status=scan_status,
                policy_status=policy_status,
                reasons=reasons,
                scanner_summary=summary_data,
            ),
        },
    }
    if conclusion is not None:
        payload["conclusion"] = conclusion
    return payload


def _summary_text(
    *, scan_id: str, scan_status: str, policy_status: str, reasons: list[str], scanner_summary: dict
) -> str:
    scanners_total = scanner_summary.get("scanners_total")
    scanners_complete = scanner_summary.get("scanners_complete")
    if scanners_total is not None and scanners_complete is not None:
        scanner_part = f"; scanners: {scanners_complete}/{scanners_total}"
        if scanners_complete != scanners_total:
            scanner_part += " (scanner gap)"
    else:
        scanner_part = ""

    findings = scanner_summary.get("findings_total")
    findings_part = f"; findings: {findings}" if findings is not None else ""

    policy_part = f"policy {policy_status}"
    if reasons:
        policy_part += f" ({', '.join(reasons)})"

    return f"Scan {scan_id} {scan_status}: {policy_part}{findings_part}{scanner_part}"
