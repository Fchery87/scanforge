import hashlib

SEVERITY_MAP = {
    "ERROR": "high",
    "WARNING": "medium",
    "INFO": "low",
}

CONFIDENCE_MAP = {
    "HIGH": 0.95,
    "MEDIUM": 0.8,
    "LOW": 0.6,
}

CATEGORY_MAP = {
    "security": "vulnerability",
}


def compute_semgrep_fingerprint(
    check_id: str,
    path: str,
    line_start: int,
    line_end: int,
    repo_id: str,
) -> str:
    components = [
        check_id,
        path,
        str(line_start),
        str(line_end),
        repo_id,
    ]
    return hashlib.sha256("|".join(components).encode()).hexdigest()


def normalize_semgrep_output(raw_output: dict, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("results", [])

    for result in results:
        check_id = result.get("check_id", "")
        path = result.get("path", "")
        start = result.get("start", {})
        end = result.get("end", {})
        extra = result.get("extra", {})

        if not check_id:
            continue

        raw_severity = extra.get("severity", "INFO").upper()
        metadata = extra.get("metadata", {})
        raw_confidence = metadata.get("confidence", "MEDIUM")
        if isinstance(raw_confidence, str):
            raw_confidence = raw_confidence.upper()
        else:
            raw_confidence = "MEDIUM"

        # Base severity mapping
        severity = SEVERITY_MAP.get(raw_severity, "low")

        # Boost to critical if severity=ERROR AND confidence=HIGH
        if raw_severity == "ERROR" and raw_confidence == "HIGH":
            severity = "critical"

        # Category mapping: "security" -> "vulnerability", everything else -> "code_quality"
        raw_category = metadata.get("category", "")
        if isinstance(raw_category, str):
            raw_category = raw_category.lower()
        category = CATEGORY_MAP.get(raw_category, "code_quality")

        confidence_score = CONFIDENCE_MAP.get(raw_confidence, 0.8)

        fingerprint = compute_semgrep_fingerprint(
            check_id=check_id,
            path=path,
            line_start=start.get("line", 1),
            line_end=end.get("line", 1),
            repo_id=repository_id,
        )

        # Build references from CWE list and metadata.references
        references = []
        cwe_list = metadata.get("cwe", [])
        if isinstance(cwe_list, list):
            for cwe in cwe_list:
                cwe_id = cwe.split(":")[0].strip() if ":" in cwe else cwe.strip()
                references.append({
                    "type": "cwe",
                    "value": cwe,
                    "url": f"https://cwe.mitre.org/data/definitions/{cwe_id.replace('CWE-', '')}.html",
                })

        meta_refs = metadata.get("references", [])
        if isinstance(meta_refs, list):
            for ref in meta_refs:
                references.append({
                    "type": "reference",
                    "value": ref,
                    "url": ref,
                })

        finding = {
            "category": category,
            "severity": severity,
            "title": check_id,
            "description": extra.get("message", ""),
            "canonical_fingerprint": fingerprint,
            "primary_scanner": "semgrep",
            "confidence_score": confidence_score,
            "instance": {
                "path": path,
                "line_start": start.get("line", 1),
                "line_end": end.get("line", 1),
                "check_id": check_id,
                "lines": extra.get("lines", ""),
            },
            "references": references,
        }
        findings.append(finding)

    return findings
