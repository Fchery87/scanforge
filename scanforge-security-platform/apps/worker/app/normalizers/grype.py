import hashlib

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "NEGLIGIBLE": "low",
    "UNKNOWN": "info",
}


def compute_vulnerability_fingerprint(
    package_name: str,
    installed_version: str,
    advisory_id: str,
    repo_id: str,
) -> str:
    components = [package_name.lower(), installed_version, advisory_id, repo_id]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_grype_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    matches = []
    if isinstance(raw_output, dict):
        matches = raw_output.get("matches", []) or []
    elif isinstance(raw_output, list):
        matches = raw_output

    for match in matches:
        if not isinstance(match, dict):
            continue
        artifact = match.get("artifact", {})
        vulnerability = match.get("vulnerability", {})

        package_name = artifact.get("name", "")
        installed_version = artifact.get("version", "")
        vuln_id = vulnerability.get("id", "")
        if not package_name or not vuln_id:
            continue

        severity = SEVERITY_MAP.get(str(vulnerability.get("severity", "UNKNOWN")).upper(), "info")
        fix_versions = ((vulnerability.get("fix") or {}).get("versions")) or []
        locations = artifact.get("locations", []) or []
        path = locations[0].get("path") if locations else None

        findings.append(
            {
                "category": "vulnerability",
                "severity": severity,
                "title": f"Vulnerable dependency: {package_name}@{installed_version}",
                "description": vulnerability.get("description", ""),
                "canonical_fingerprint": compute_vulnerability_fingerprint(
                    package_name=package_name,
                    installed_version=installed_version,
                    advisory_id=vuln_id,
                    repo_id=repository_id,
                ),
                "primary_scanner": "grype",
                "confidence_score": 0.92,
                "fixed_version": fix_versions[0] if fix_versions else None,
                "instance": {
                    "package_name": package_name,
                    "installed_version": installed_version,
                    "fixed_version": fix_versions[0] if fix_versions else None,
                    "package_type": artifact.get("type"),
                    "path": path,
                    "purl": artifact.get("purl"),
                },
                "references": (
                    [
                        {
                            "type": "advisory",
                            "value": vuln_id,
                            "url": vulnerability.get("dataSource"),
                        }
                    ]
                    if vulnerability.get("dataSource")
                    else []
                ),
            }
        )

    return findings
