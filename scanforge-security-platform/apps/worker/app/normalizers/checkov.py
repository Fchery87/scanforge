import hashlib
import re

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFO": "info",
}


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned.lstrip("/")


def compute_checkov_fingerprint(
    check_id: str,
    resource: str,
    path: str,
    repo_id: str,
) -> str:
    components = [check_id, resource, path, repo_id]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_checkov_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []
    results = raw_output.get("results", {}) if isinstance(raw_output, dict) else {}
    failed_checks = results.get("failed_checks", []) if isinstance(results, dict) else []

    if isinstance(raw_output, list):
        failed_checks = []
        for item in raw_output:
            if isinstance(item, dict):
                if "results" in item and isinstance(item["results"], dict):
                    failed_checks.extend(item["results"].get("failed_checks", []) or [])
                else:
                    failed_checks.append(item)

    for failed in failed_checks:
        if not isinstance(failed, dict):
            continue
        check_id = failed.get("check_id", "")
        massage_path = failed.get("file_path", "") or failed.get("repo_file_path", "")
        path = _normalize_repo_path(massage_path)
        resource = failed.get("resource", "")
        line_range = failed.get("file_line_range", []) or []
        raw_severity = str(failed.get("severity") or "MEDIUM").upper()
        severity = SEVERITY_MAP.get(raw_severity, "medium")

        if not check_id:
            continue

        fingerprint = compute_checkov_fingerprint(check_id, resource, path, repository_id)
        guideline = failed.get("guideline")

        findings.append(
            {
                "category": "iac_misconfiguration",
                "severity": severity,
                "title": failed.get("check_name", check_id),
                "description": failed.get("details") or failed.get("description", ""),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "checkov",
                "confidence_score": 0.9,
                "metadata_json": {
                    "severity_source": "checkov",
                    "raw_severity": raw_severity,
                    "check_id": check_id,
                },
                "instance": {
                    "path": path,
                    "line_start": line_range[0] if len(line_range) >= 1 else None,
                    "line_end": line_range[1] if len(line_range) >= 2 else None,
                    "resource": resource,
                    "check_id": check_id,
                    "check_type": failed.get("check_type"),
                },
                "references": ([{"type": "guideline", "value": check_id, "url": guideline}] if guideline else []),
            }
        )

    return findings
