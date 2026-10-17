import hashlib
import re

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


def compute_secret_fingerprint(
    secret_type: str,
    repo_id: str,
    path: str,
    line: int,
) -> str:
    components = [
        secret_type.lower(),
        repo_id,
        path.lower(),
        str(line),
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_gitleaks_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    results = []
    if isinstance(raw_output, list):
        results = raw_output
    elif isinstance(raw_output, dict):
        results = raw_output.get("results", [])

    for result in results:
        if not isinstance(result, dict):
            continue
        secret_type = result.get("RuleID") or result.get("rule_id") or "unknown"
        file_path = _normalize_repo_path(result.get("File") or result.get("path") or "")
        line_start = result.get("StartLine") or result.get("line_start") or 1
        line_end = result.get("EndLine") or result.get("line_end") or line_start
        commit_val = result.get("Commit") if "Commit" in result else result.get("commit")

        fingerprint = compute_secret_fingerprint(
            secret_type=secret_type,
            repo_id=repository_id,
            path=file_path,
            line=line_start,
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
