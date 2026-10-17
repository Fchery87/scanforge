import hashlib
import re

from app.security.secret_evidence import sanitize_trivy_output

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "UNKNOWN": "info",
}


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned


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


def normalize_trivy_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    raw_output = sanitize_trivy_output(raw_output)
    findings = []

    results = raw_output.get("Results", []) if isinstance(raw_output, dict) else []
    if isinstance(raw_output, list):
        results = raw_output

    for result in results:
        if not isinstance(result, dict):
            continue
        target = _normalize_repo_path(result.get("Target", ""))
        result_type = result.get("Type", "")

        for vuln in result.get("Vulnerabilities", []) or []:
            pkg_name = vuln.get("PkgName", "")
            installed = vuln.get("InstalledVersion", "")
            fixed = vuln.get("FixedVersion", "")
            vuln_id = vuln.get("VulnerabilityID", "")
            raw_severity = str(vuln.get("Severity", "UNKNOWN")).upper()
            severity = SEVERITY_MAP.get(raw_severity, "info")

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
                "fixed_version": fixed or None,
                "advisory_id": vuln_id,
                "package_name": pkg_name,
                "package_ecosystem": result_type or None,
                "metadata_json": {
                    "severity_source": "trivy",
                    "raw_severity": raw_severity,
                    "remediation_source": "trivy" if fixed else None,
                },
                "instance": {
                    "package_name": pkg_name,
                    "installed_version": installed,
                    "fixed_version": fixed,
                    "target": target,
                    "path": target or None,
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
            rule_id = secret.get("RuleID") or secret.get("rule_id") or "unknown"
            file_path = _normalize_repo_path(
                secret.get("File") or secret.get("path") or target or ""
            )
            line = secret.get("StartLine") or secret.get("line_start") or 1
            line_end = secret.get("EndLine") or secret.get("line_end") or line
            secret_type = secret.get("Category") or secret.get("secret_type")

            fingerprint = hashlib.sha256(
                f"{rule_id}|{repository_id}|{file_path}|{line}".encode()
            ).hexdigest()

            instance_payload = {
                "path": file_path,
                "line_start": line,
                "line_end": line_end,
                "rule_id": rule_id,
            }
            if secret_type:
                instance_payload["secret_type"] = secret_type
            if secret.get("Commit") or secret.get("commit"):
                instance_payload["commit"] = secret.get("Commit") or secret.get("commit")

            finding = {
                "category": "secret",
                "severity": "high",
                "title": f"Exposed secret: {rule_id}",
                "description": "A secret was detected by the scanner.",
                "canonical_fingerprint": fingerprint,
                "primary_scanner": "trivy",
                "confidence_score": 0.85,
                "metadata_json": {
                    "severity_source": "trivy",
                    "raw_severity": "HIGH",
                    "rule_id": rule_id,
                },
                "instance": instance_payload,
            }
            findings.append(finding)

        for misconfig in result.get("Misconfigurations", []) or []:
            rule_id = misconfig.get("ID", "unknown")
            title = misconfig.get("Title", rule_id)
            raw_severity = str(misconfig.get("Severity", "UNKNOWN")).upper()
            severity = SEVERITY_MAP.get(raw_severity, "info")

            fingerprint = hashlib.sha256(
                f"{rule_id}|{repository_id}|{target}".encode()
            ).hexdigest()

            findings.append(
                {
                    "category": "iac_misconfiguration",
                    "severity": severity,
                    "title": title,
                    "description": misconfig.get("Description", ""),
                    "canonical_fingerprint": fingerprint,
                    "primary_scanner": "trivy",
                    "confidence_score": 0.9,
                    "metadata_json": {
                        "severity_source": "trivy",
                        "raw_severity": raw_severity,
                        "rule_id": rule_id,
                    },
                    "instance": {
                        "path": target,
                        "rule_id": rule_id,
                        "type": result_type,
                        "resolution": misconfig.get("Resolution"),
                    },
                    "references": (
                        [
                            {
                                "type": "documentation",
                                "value": rule_id,
                                "url": misconfig.get("PrimaryURL"),
                            }
                        ]
                        if misconfig.get("PrimaryURL")
                        else []
                    ),
                }
            )

    return findings
