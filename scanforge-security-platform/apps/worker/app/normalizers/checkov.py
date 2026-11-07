import re

from app.normalizers.identity import (
    SOURCE_FINGERPRINT_VERSION,
    location_stable_fingerprint,
    occurrence_indices,
)

SEVERITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
    "INFO": "info",
}


def _normalize_repo_path(path: str) -> str:
    cleaned = str(path or "").strip()
    cleaned = re.sub(r"^/workspace/source/?", "", cleaned)
    return cleaned.lstrip("/")


def _snippet_digest(check: dict) -> str | None:
    digest = check.get("snippet_sha256")
    return digest if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) else None


def failed_checks_from(raw_output: dict | list) -> list[dict]:
    results = raw_output.get("results", {}) if isinstance(raw_output, dict) else {}
    failed_checks = results.get("failed_checks", []) if isinstance(results, dict) else []

    if isinstance(raw_output, list):
        failed_checks = []
        for item in raw_output:
            if isinstance(item, dict):
                if "results" in item and isinstance(item["results"], dict):
                    failed_checks.extend(item["results"].get("failed_checks", []) or [])
                else:
                    failed_checks.append(item)
    return [f for f in failed_checks if isinstance(f, dict)]


def normalize_checkov_output(raw_output: dict | list, repository_id: str) -> list[dict]:
    findings = []
    failed_checks = failed_checks_from(raw_output)

    valid = [f for f in failed_checks if isinstance(f, dict) and f.get("check_id")]
    paths = [_normalize_repo_path(f.get("file_path", "") or f.get("repo_file_path", "")) for f in valid]
    digests = [_snippet_digest(f) for f in valid]
    # Identical blocks for one check in one file are told apart by source order.
    indices = occurrence_indices(
        [(f["check_id"], path, digest) for f, path, digest in zip(valid, paths, digests, strict=True)],
        [((f.get("file_line_range") or [1])[0] or 1,) for f in valid],
    )

    for failed, path, digest, occurrence_index in zip(valid, paths, digests, indices, strict=True):
        check_id = failed["check_id"]
        resource = failed.get("resource", "")
        line_range = failed.get("file_line_range", []) or []
        raw_severity = str(failed.get("severity") or "MEDIUM").upper()
        severity = SEVERITY_MAP.get(raw_severity, "medium")

        fingerprint = location_stable_fingerprint(
            scanner="checkov",
            repo_id=repository_id,
            rule=check_id,
            path=path,
            snippet_sha256=digest or "",
            occurrence_index=occurrence_index,
        )
        guideline = failed.get("guideline")

        findings.append(
            {
                "category": "iac_misconfiguration",
                "severity": severity,
                "title": failed.get("check_name", check_id),
                "description": failed.get("details") or failed.get("description", ""),
                "canonical_fingerprint": fingerprint,
                "fingerprint_version": SOURCE_FINGERPRINT_VERSION,
                "primary_scanner": "checkov",
                "confidence_score": 0.9,
                "metadata_json": {
                    "severity_source": "checkov",
                    "raw_severity": raw_severity,
                    "check_id": check_id,
                    **({} if digest else {"snippet_unavailable": True}),
                },
                "instance": {
                    "path": path,
                    "line_start": line_range[0] if len(line_range) >= 1 else None,
                    "line_end": line_range[1] if len(line_range) >= 2 else None,
                    "resource": resource,
                    "check_id": check_id,
                    "check_type": failed.get("check_type"),
                },
                "references": ([{"type": "guideline", "value": check_id, "url": guideline}] if guideline else []),
            }
        )

    return findings
