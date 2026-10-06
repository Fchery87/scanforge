from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "match",
        "secret",
        "secretvalue",
        "secret_value",
        "plaintext",
        "raw",
        "decoded",
        "linecontent",
        "lines",
        "value",
    }
)


@dataclass(frozen=True)
class SecretBoundaryViolation(Exception):
    boundary: str
    detail: str


def _is_secret_key(key: str) -> bool:
    return key.replace("_", "").replace("-", "").lower() in _SECRET_KEYS


def sanitize_secret_record(record: dict[str, Any]) -> dict[str, Any]:
    """Keep only non-sensitive rule, location, and commit metadata."""
    allowed = {
        "RuleID": "rule_id",
        "rule_id": "rule_id",
        "Category": "secret_type",
        "category": "secret_type",
        "File": "path",
        "file": "path",
        "StartLine": "line_start",
        "start_line": "line_start",
        "EndLine": "line_end",
        "end_line": "line_end",
        "Commit": "commit",
    }
    return {
        target: record[key]
        for key, target in allowed.items()
        if key in record and record[key] is not None
    }


def sanitize_trivy_output(raw_output: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    """Remove secret values from Trivy output without removing vulnerability data."""
    if isinstance(raw_output, list):
        return [
            sanitize_trivy_output(value) if isinstance(value, (dict, list)) else value
            for value in raw_output
        ]
    if not isinstance(raw_output, dict):
        return raw_output

    sanitized: dict[str, Any] = {}
    for key, value in raw_output.items():
        if key == "Secrets" and isinstance(value, list):
            sanitized[key] = [
                sanitize_secret_record(item) for item in value if isinstance(item, dict)
            ]
        elif _is_secret_key(key):
            continue
        elif isinstance(value, (dict, list)):
            sanitized[key] = sanitize_trivy_output(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_secret_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Remove prohibited secret evidence before any durable or external boundary."""
    if finding.get("category") != "secret":
        return finding

    sanitized = dict(finding)
    sanitized["description"] = "A secret was detected by the scanner."
    instance = dict(sanitized.get("instance") or {})
    safe_instance_keys = {"path", "line_start", "line_end", "commit", "rule_id", "secret_type"}
    sanitized["instance"] = {
        key: value
        for key, value in instance.items()
        if key in safe_instance_keys and not _is_secret_key(key)
    }
    metadata = sanitized.get("metadata_json")
    if isinstance(metadata, dict):
        sanitized["metadata_json"] = {
            key: value for key, value in metadata.items() if not _is_secret_key(key)
        }
    return sanitized


def sanitize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_secret_finding(finding) for finding in findings]


def safe_artifact_key(organization_id: str, scan_id: str, scanner_name: str, filename: str) -> str:
    """Build the required tenant-scoped object key and reject traversal."""
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."} or safe_name != filename:
        raise ValueError("invalid artifact filename")
    return f"scan-artifacts/{organization_id}/{scan_id}/{scanner_name}/{safe_name}"


def assert_ai_disabled_for_private_beta() -> None:
    if (
        os.environ.get("APP_ENV", "development").lower() == "private-beta"
        and os.environ.get("AI_ENABLED", "false").lower() == "true"
    ):
        raise RuntimeError("AI investigation must remain disabled in private-beta")
