import re

from app.normalizers.identity import (
    SOURCE_FINGERPRINT_VERSION,
    location_stable_fingerprint,
    occurrence_indices,
)

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "ERROR": "high",
    "HIGH": "high",
    "WARNING": "medium",
    "MEDIUM": "medium",
    "INFO": "low",
    "LOW": "low",
}

CONFIDENCE_MAP = {
    "HIGH": 0.95,
    "MEDIUM": 0.8,
    "LOW": 0.6,
}

CATEGORY_MAP = {
    "security": "vulnerability",
}


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned


def _snippet_digest(result: dict) -> str | None:
    digest = result.get("snippet_sha256")
    return digest if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None


def normalize_semgrep_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []

    results = raw_output.get("results", []) if isinstance(raw_output, dict) else []

    if isinstance(raw_output, list):
        results = raw_output

    valid = [r for r in results if isinstance(r, dict) and r.get("check_id")]
    paths = [_normalize_repo_path(r.get("path", "")) for r in valid]
    digests = [_snippet_digest(r) for r in valid]
    # Identical snippets for one rule in one file are told apart by source order.
    indices = occurrence_indices(
        [(r["check_id"], path, digest) for r, path, digest in zip(valid, paths, digests, strict=True)],
        [((r.get("start") or {}).get("line", 1), (r.get("start") or {}).get("col", 1)) for r in valid],
    )

    for result, path, digest, occurrence_index in zip(valid, paths, digests, indices, strict=True):
        check_id = result["check_id"]
        start = result.get("start", {})
        end = result.get("end", {})
        extra = result.get("extra", {})

        raw_severity = str(extra.get("severity", "INFO")).upper()
        metadata = extra.get("metadata", {}) or {}
        raw_confidence = metadata.get("confidence", "MEDIUM")
        if isinstance(raw_confidence, str):
            raw_confidence = raw_confidence.upper()
        else:
            raw_confidence = "MEDIUM"

        # ADR-014: Keep severity and confidence strictly separate.
        # Confidence alone never promotes ERROR (high) to critical.
        severity = SEVERITY_MAP.get(raw_severity, "low")

        raw_category = metadata.get("category", "")
        if isinstance(raw_category, str):
            raw_category = raw_category.lower()
        category = CATEGORY_MAP.get(raw_category, "code_quality")

        confidence_score = CONFIDENCE_MAP.get(raw_confidence, 0.8)

        fingerprint = location_stable_fingerprint(
            scanner="semgrep",
            repo_id=repository_id,
            rule=check_id,
            path=path,
            snippet_sha256=digest or "",
            occurrence_index=occurrence_index,
        )

        references = []
        cwe_list = metadata.get("cwe", [])
        if isinstance(cwe_list, list):
            for cwe in cwe_list:
                cwe_id = cwe.split(":")[0].strip() if ":" in cwe else cwe.strip()
                references.append(
                    {
                        "type": "cwe",
                        "value": cwe,
                        "url": f"https://cwe.mitre.org/data/definitions/{cwe_id.replace('CWE-', '')}.html",
                    }
                )

        meta_refs = metadata.get("references", [])
        if isinstance(meta_refs, list):
            for ref in meta_refs:
                references.append(
                    {
                        "type": "reference",
                        "value": ref,
                        "url": ref,
                    }
                )

        finding = {
            "category": category,
            "severity": severity,
            "title": check_id,
            "description": extra.get("message", ""),
            "canonical_fingerprint": fingerprint,
            "fingerprint_version": SOURCE_FINGERPRINT_VERSION,
            "primary_scanner": "semgrep",
            "confidence_score": confidence_score,
            "metadata_json": {
                "severity_source": "semgrep",
                "raw_severity": raw_severity,
                "raw_confidence": raw_confidence,
                "check_id": check_id,
                **({} if digest else {"snippet_unavailable": True}),
            },
            "instance": {
                "path": path,
                "line_start": start.get("line", 1),
                "line_end": end.get("line", 1),
                "check_id": check_id,
            },
            "references": references,
        }
        findings.append(finding)

    return findings
