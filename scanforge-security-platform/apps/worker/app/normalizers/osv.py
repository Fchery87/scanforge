import hashlib

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "info",
}


def compute_vulnerability_fingerprint(
    package_name: str,
    installed_version: str,
    advisory_id: str,
    repo_id: str,
) -> str:
    components = [
        package_name.lower(),
        installed_version,
        advisory_id,
        repo_id,
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_osv_output(raw_output: dict, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("results", [])
    if isinstance(raw_output, list):
        results = raw_output

    for result in results:
        vulns = result.get("vulnerabilities", [])
        if not vulns:
            continue

        for vuln in vulns:
            pkg_name = vuln.get("package", {}).get("name", "")
            vuln_id = vuln.get("id", "")
            severity = _get_severity(vuln)
            description = vuln.get("summary", "")

            affected_list = vuln.get("affected", []) or []
            for affected in affected_list:
                ecosystem = (
                    affected.get("package", {})
                    .get("ecosystem_specific", {})
                    .get("ecosystem", "unknown")
                )

                for range_info in affected.get("ranges", []) or []:
                    events = range_info.get("events", []) or []
                    for i, event in enumerate(events):
                        fixed = event.get("fixed")
                        introduced = event.get("introduced", "")

                        if not fixed:
                            continue

                        installed = ""
                        if i > 0:
                            prev = events[i - 1]
                            introduced = prev.get("introduced", "")
                            installed = introduced or "unknown"

                        fingerprint = compute_vulnerability_fingerprint(
                            package_name=pkg_name,
                            installed_version=str(installed),
                            advisory_id=vuln_id,
                            repo_id=repository_id,
                        )

                        finding = {
                            "category": "vulnerability",
                            "severity": severity,
                            "title": f"Vulnerable dependency: {pkg_name}@{installed}",
                            "description": description,
                            "canonical_fingerprint": fingerprint,
                            "primary_scanner": "osv",
                            "confidence_score": 0.9,
                            "fixed_version": fixed,
                            "instance": {
                                "package_name": pkg_name,
                                "installed_version": str(installed),
                                "fixed_version": fixed,
                                "ecosystem": ecosystem,
                            },
                            "references": [
                                {
                                    "type": "advisory",
                                    "value": vuln_id,
                                    "url": f"https://osv.dev/vulnerability/{vuln_id}",
                                }
                            ],
                        }
                        findings.append(finding)

    return findings


def _get_severity(vuln: dict) -> str:
    severity = vuln.get("severity", [])
    if severity:
        if isinstance(severity, list) and severity:
            return SEVERITY_MAP.get(severity[0].get("type", "UNKNOWN").upper(), "medium")
        elif isinstance(severity, dict):
            return SEVERITY_MAP.get(severity.get("type", "UNKNOWN").upper(), "medium")

    database_specific = vuln.get("database_specific", {})
    severity_str = database_specific.get("severity", "")
    if severity_str:
        return SEVERITY_MAP.get(severity_str.upper(), "medium")

    return "medium"
