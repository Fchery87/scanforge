import hashlib

HIGH_RISK_SECRET_TYPES = {
    "aws_access_key", "aws_secret_key", "private_key", "ssh_key",
    "database_url", "api_key", "github_token", "slack_token",
}


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
        secret_type = result.get("RuleID", "unknown")
        file_path = result.get("File", "")
        line_start = result.get("StartLine", 1)
        line_end = result.get("EndLine", line_start)

        fingerprint = compute_secret_fingerprint(
            secret_type=secret_type,
            repo_id=repository_id,
            path=file_path,
            line=line_start,
        )

        severity = "high"
        if secret_type.lower() in HIGH_RISK_SECRET_TYPES:
            severity = "critical"

        finding = {
            "category": "secret",
            "severity": severity,
            "title": f"Exposed secret: {secret_type}",
            "description": "A secret was detected by the scanner.",
            "canonical_fingerprint": fingerprint,
            "primary_scanner": "gitleaks",
            "confidence_score": 0.95,
            "instance": {
                "path": file_path,
                "line_start": line_start,
                "line_end": line_end,
                "commit": result.get("Commit"),
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
