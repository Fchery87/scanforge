import re

from app.normalizers.identity import (
    SOURCE_FINGERPRINT_VERSION,
    location_stable_fingerprint,
    occurrence_indices,
)

HIGH_RISK_SECRET_TYPES = {
    "aws_access_key",
    "aws_access_token",
    "aws_secret_key",
    "private_key",
    "ssh_key",
    "database_url",
    "api_key",
    "generic_api_key",
    "github_token",
    "github_pat",
    "github_fine_grained_pat",
    "github_oauth",
    "slack_token",
    "slack_access_token",
}


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned


def normalize_gitleaks_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    results = []
    if isinstance(raw_output, list):
        results = raw_output
    elif isinstance(raw_output, dict):
        results = raw_output.get("results", [])

    valid = [r for r in results if isinstance(r, dict)]
    rules = [r.get("RuleID") or r.get("rule_id") or "unknown" for r in valid]
    file_paths = [_normalize_repo_path(r.get("File") or r.get("path") or "") for r in valid]
    # Identity is rule + path + occurrence index only: nothing derived from the
    # matched value or the line number ever enters a secret fingerprint.
    indices = occurrence_indices(
        [(rule.lower(), path.lower()) for rule, path in zip(rules, file_paths, strict=True)],
        [
            (r.get("StartLine") or r.get("line_start") or 1, r.get("StartColumn") or r.get("column_start") or 1)
            for r in valid
        ],
    )

    for result, secret_type, file_path, occurrence_index in zip(valid, rules, file_paths, indices, strict=True):
        line_start = result.get("StartLine") or result.get("line_start") or 1
        line_end = result.get("EndLine") or result.get("line_end") or line_start
        commit_val = result.get("Commit") if "Commit" in result else result.get("commit")

        fingerprint = location_stable_fingerprint(
            scanner="gitleaks",
            repo_id=repository_id,
            rule=secret_type.lower(),
            path=file_path.lower(),
            occurrence_index=occurrence_index,
        )

        normalized_rule = secret_type.lower().replace("-", "_")
        severity = "high"
        if normalized_rule in HIGH_RISK_SECRET_TYPES:
            severity = "critical"

        finding = {
            "category": "secret",
            "severity": severity,
            "title": f"Exposed secret: {secret_type}",
            "description": "A secret was detected by the scanner.",
            "canonical_fingerprint": fingerprint,
            "fingerprint_version": SOURCE_FINGERPRINT_VERSION,
            "primary_scanner": "gitleaks",
            "confidence_score": 0.95,
            "metadata_json": {
                "severity_source": "gitleaks",
                "raw_severity": severity.upper(),
                "rule_id": secret_type,
            },
            "instance": {
                "path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "commit": commit_val,
            },
            "references": [
                {
                    "type": "documentation",
                    "value": f"https://github.com/gitleaks/gitleaks/blob/master/docs/rules/{secret_type.lower()}.md",
                }
            ],
        }
        findings.append(finding)

    return findings
