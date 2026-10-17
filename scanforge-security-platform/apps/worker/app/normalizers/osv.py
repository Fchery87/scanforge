import hashlib
import re

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
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
    components = [
        package_name.lower(),
        installed_version,
        advisory_id,
        repo_id,
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def _extract_fixed_version_from_vuln(vuln: dict, package_name: str) -> str | None:
    for affected in vuln.get("affected", []) or []:
        aff_pkg = (affected.get("package") or {}).get("name", "")
        if aff_pkg and aff_pkg.lower() != package_name.lower():
            continue
        for range_info in affected.get("ranges", []) or []:
            for event in range_info.get("events", []) or []:
                fixed = event.get("fixed")
                if fixed:
                    return str(fixed)
    return None


def normalize_osv_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("results", []) if isinstance(raw_output, dict) else []
    if isinstance(raw_output, list):
        results = raw_output

    for result in results:
        if not isinstance(result, dict):
            continue
        source_path = _normalize_repo_path((result.get("source") or {}).get("path"))
        packages = result.get("packages", []) or []
        if packages:
            for package_entry in packages:
                pkg = package_entry.get("package", {}) or {}
                package_name = pkg.get("name", "")
                ecosystem = pkg.get("ecosystem", "unknown")
                installed_version = str(
                    pkg.get("version") or package_entry.get("version") or "unknown"
                )
                for vuln in package_entry.get("vulnerabilities", []) or []:
                    fixed_version = _extract_fixed_version_from_vuln(vuln, package_name)
                    finding = _build_osv_finding(
                        repository_id=repository_id,
                        package_name=package_name,
                        installed_version=installed_version,
                        ecosystem=ecosystem,
                        vuln=vuln,
                        fixed_version=fixed_version,
                        source_path=source_path,
                    )
                    if finding:
                        findings.append(finding)
            continue

        for vuln in result.get("vulnerabilities", []) or []:
            package_name = vuln.get("package", {}).get("name", "")
            affected_list = vuln.get("affected", []) or []
            emitted = False

            for affected in affected_list:
                ecosystem = affected.get("package", {}).get("ecosystem", "unknown")

                for range_info in affected.get("ranges", []) or []:
                    events = range_info.get("events", []) or []
                    for index, event in enumerate(events):
                        fixed_version = event.get("fixed")
                        if not fixed_version:
                            continue

                        installed_version = "unknown"
                        if index > 0:
                            installed_version = events[index - 1].get("introduced", "") or "unknown"

                        finding = _build_osv_finding(
                            repository_id=repository_id,
                            package_name=package_name,
                            installed_version=str(installed_version),
                            ecosystem=ecosystem,
                            vuln=vuln,
                            fixed_version=fixed_version,
                            source_path=source_path,
                        )
                        if finding:
                            findings.append(finding)
                            emitted = True

            if not emitted:
                ecosystem = "unknown"
                if affected_list:
                    ecosystem = affected_list[0].get("package", {}).get("ecosystem", "unknown")
                finding = _build_osv_finding(
                    repository_id=repository_id,
                    package_name=package_name,
                    installed_version="unknown",
                    ecosystem=ecosystem,
                    vuln=vuln,
                    fixed_version=None,
                    source_path=source_path,
                )
                if finding:
                    findings.append(finding)

    return findings


def _get_severity(vuln: dict) -> str:
    severity = vuln.get("severity", [])
    if severity:
        if isinstance(severity, list) and severity:
            severity_entry = severity[0]
            if isinstance(severity_entry, dict):
                severity_type = severity_entry.get("type", "UNKNOWN").upper()
                if severity_type.startswith("CVSS"):
                    cvss_severity = _severity_from_cvss(severity_entry.get("score", ""))
                    if cvss_severity:
                        return cvss_severity
                return SEVERITY_MAP.get(severity_type, "medium")
        elif isinstance(severity, dict):
            severity_type = severity.get("type", "UNKNOWN").upper()
            if severity_type.startswith("CVSS"):
                cvss_severity = _severity_from_cvss(severity.get("score", ""))
                if cvss_severity:
                    return cvss_severity
            return SEVERITY_MAP.get(severity_type, "medium")

    database_specific = vuln.get("database_specific", {})
    severity_str = database_specific.get("severity", "")
    if severity_str:
        return SEVERITY_MAP.get(severity_str.upper(), "medium")

    return "medium"


def _build_osv_finding(
    repository_id: str,
    package_name: str,
    installed_version: str,
    ecosystem: str,
    vuln: dict,
    fixed_version: str | None,
    source_path: str | None = None,
) -> dict | None:
    vuln_id = vuln.get("id", "")
    if not vuln_id or not package_name:
        return None

    severity = _get_severity(vuln)
    description = vuln.get("summary", "") or vuln.get("details", "")
    fingerprint = compute_vulnerability_fingerprint(
        package_name=package_name,
        installed_version=installed_version,
        advisory_id=vuln_id,
        repo_id=repository_id,
    )

    instance = {
        "package_name": package_name,
        "installed_version": installed_version,
        "fixed_version": fixed_version,
        "ecosystem": ecosystem,
    }
    if source_path:
        instance["path"] = source_path

    return {
        "category": "vulnerability",
        "severity": severity,
        "title": f"Vulnerable dependency: {package_name}@{installed_version}",
        "description": description,
        "canonical_fingerprint": fingerprint,
        "primary_scanner": "osv",
        "confidence_score": 0.9,
        "fixed_version": fixed_version,
        "advisory_id": vuln_id,
        "package_name": package_name,
        "package_ecosystem": ecosystem,
        "metadata_json": {
            "severity_source": "osv",
            "raw_severity": severity.upper(),
            "remediation_source": "osv" if fixed_version else None,
        },
        "instance": instance,
        "references": [
            {
                "type": "advisory",
                "value": vuln_id,
                "url": f"https://osv.dev/vulnerability/{vuln_id}",
            }
        ],
    }


def _severity_from_cvss(score: str) -> str | None:
    if not score:
        return None

    numeric_match = re.search(r"(\d+\.\d+|\d+)$", score)
    if numeric_match:
        return _map_cvss_numeric(float(numeric_match.group(1)))

    if score.startswith("CVSS:"):
        return _map_cvss_vector(score)

    return None


def _map_cvss_numeric(score: float) -> str:
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0:
        return "low"
    return "info"


def _map_cvss_vector(vector: str) -> str:
    high_impacts = vector.count("/C:H") + vector.count("/I:H") + vector.count("/A:H")
    if all(token in vector for token in ("/AV:N", "/AC:L", "/PR:N", "/UI:N")) and high_impacts >= 2:
        return "critical"
    if high_impacts >= 1:
        return "high"
    if any(token in vector for token in ("/C:L", "/I:L", "/A:L")):
        return "medium"
    return "low"
