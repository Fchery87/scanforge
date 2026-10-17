import hashlib
import re

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "NEGLIGIBLE": "low",
    "UNKNOWN": "info",
}


def _normalize_repo_path(path: str | None) -> str | None:
    if not path:
        return None
    cleaned = str(path).strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned or None


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

        raw_severity = str(vulnerability.get("severity", "UNKNOWN")).upper()
        severity = SEVERITY_MAP.get(raw_severity, "info")
        fix_versions = ((vulnerability.get("fix") or {}).get("versions")) or []
        fixed_version = fix_versions[0] if fix_versions else None
        locations = artifact.get("locations", []) or []
        path = _normalize_repo_path(locations[0].get("path")) if locations else None

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
                "fixed_version": fixed_version,
                "advisory_id": vuln_id,
                "package_name": package_name,
                "package_ecosystem": artifact.get("type") or None,
                "metadata_json": {
                    "severity_source": "grype",
                    "raw_severity": raw_severity,
                    "remediation_source": "grype" if fixed_version else None,
                },
                "instance": {
                    "package_name": package_name,
                    "installed_version": installed_version,
                    "fixed_version": fixed_version,
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
