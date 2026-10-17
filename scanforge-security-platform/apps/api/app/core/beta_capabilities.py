from __future__ import annotations

from fastapi import HTTPException, status

from app.schemas.scans import ScanCreate

BETA_CAPABILITIES: dict[str, bool] = {
    "exports": False,
    "suppression_rules": False,
    "scan_schedules": False,
    "pr_review": False,
    "diff_scans": False,
    "ai_assistance": False,
    "scorecard_grades": False,
    "numeric_risk_scores": False,
    "policy_enforcement": False,
}

SUPPORTED_BETA_SCAN_TRIGGERS: frozenset[str] = frozenset({"manual", "webhook"})
SUPPORTED_BETA_SCAN_TYPES: frozenset[str] = frozenset({"full", "dependencies", "secrets"})


def is_beta_capability_enabled(capability: str) -> bool:
    return bool(BETA_CAPABILITIES.get(capability, False))


def require_beta_capability(capability: str, detail: str | None = None) -> None:
    if is_beta_capability_enabled(capability):
        return
    message = detail or f"Capability '{capability}' is disabled in initial managed beta"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "beta_capability_disabled",
            "capability": capability,
            "message": message,
        },
    )


def assert_scan_request_supported(data: ScanCreate) -> None:
    raw_trigger = getattr(data, "trigger_type", "manual") or "manual"
    raw_scan_type = getattr(data, "scan_type", "full") or "full"
    trigger = getattr(raw_trigger, "value", raw_trigger) or "manual"
    scan_type = getattr(raw_scan_type, "value", raw_scan_type) or "full"

    if trigger == "pull_request":
        require_beta_capability(
            "pr_review",
            "Pull request scans and advisory reviews are disabled in initial managed beta",
        )
    if trigger == "scheduled":
        require_beta_capability(
            "scan_schedules",
            "Scheduled scans are disabled in initial managed beta",
        )
    if trigger not in SUPPORTED_BETA_SCAN_TRIGGERS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "beta_capability_disabled",
                "capability": f"scan_trigger:{trigger}",
                "message": f"Scan trigger '{trigger}' is disabled in initial managed beta",
            },
        )

    if scan_type == "diff":
        require_beta_capability(
            "diff_scans",
            "Diff scans are disabled in initial managed beta",
        )
    if scan_type not in SUPPORTED_BETA_SCAN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "beta_capability_disabled",
                "capability": f"scan_type:{scan_type}",
                "message": f"Scan type '{scan_type}' is disabled in initial managed beta",
            },
        )
