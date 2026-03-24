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


def normalize_trivy_output(raw_output: dict, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("Results", [])
    if isinstance(raw_output, list):
        results = raw_output

    for result in results:
        target = result.get("Target", "")
        result_type = result.get("Type", "")

        for vuln in result.get("Vulnerabilities", []) or []:
            pkg_name = vuln.get("PkgName", "")
            installed = vuln.get("InstalledVersion", "")
            fixed = vuln.get("FixedVersion", "")
            vuln_id = vuln.get("VulnerabilityID", "")
            severity = SEVERITY_MAP.get(vuln.get("Severity", "UNKNOWN").upper(), "info")

            if not vuln_id:
                continue

            fingerprint = compute_vulnerability_fingerprint(
                package_name=pkg_name,
                installed_version=installed,
                advisory_id=vuln_id,
                repo_id=repository_id,
            )

            finding = {
                "category": "vulnerability",
                "severity": severity,
                "title": f"Vulnerable dependency: {pkg_name}@{installed}",
                "description": vuln.get("Description", ""),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "trivy",
                "confidence_score": 0.9,
                "fixed_version": fixed,
                "instance": {
                    "package_name": pkg_name,
                    "installed_version": installed,
                    "fixed_version": fixed,
                    "target": target,
                    "type": result_type,
                },
                "references": [
                    {
                        "type": "advisory",
                        "value": vuln_id,
                        "url": f"https://nvd.nist.gov/vuln/detail/{vuln_id}",
                    }
                ],
            }
            findings.append(finding)

        for secret in result.get("Secrets", []) or []:
            rule_id = secret.get("RuleID", "unknown")
            file_path = secret.get("File", "")
            line = secret.get("StartLine", 1)

            fingerprint = hashlib.sha256(
                f"{rule_id}|{repository_id}|{file_path}|{line}".encode()
            ).hexdigest()

            finding = {
                "category": "secret",
                "severity": "high",
                "title": f"Exposed secret: {rule_id}",
                "description": secret.get("Match", ""),
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "trivy",
                "confidence_score": 0.85,
                "instance": {
                    "path": file_path,
                    "line_start": line,
                    "rule_id": rule_id,
                },
            }
            findings.append(finding)

    return findings
