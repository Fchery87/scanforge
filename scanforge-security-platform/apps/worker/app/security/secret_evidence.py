from __future__ import annotations

import os
import re
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
        "code",
        "codeblock",
        "code_block",
        "snippet",
    }
)

_NON_TRIVY_STRIP_KEYS = frozenset(
    {
        "match",
        "secret",
        "secretvalue",
        "secret_value",
        "plaintext",
        "decoded",
        "linecontent",
        "lines",
        "code",
        "codeblock",
        "code_block",
        "snippet",
    }
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class SecretBoundaryViolation(Exception):
    boundary: str
    detail: str


def _is_secret_key(key: str) -> bool:
    return key.replace("_", "").replace("-", "").lower() in _SECRET_KEYS


def _is_non_trivy_strip_key(key: str) -> bool:
    return key.replace("_", "").replace("-", "").lower() in _NON_TRIVY_STRIP_KEYS


def redact_secret_patterns(value: str) -> str:
    redacted = value
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("[REDACTED_SECRET]", redacted)
    return redacted


def sanitize_secret_record(
    record: dict[str, Any],
    *,
    default_path: str | None = None,
) -> dict[str, Any]:
    """Keep only non-sensitive rule, location, and commit metadata (idempotent)."""
    field_sources: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("rule_id", ("RuleID", "rule_id")),
        ("secret_type", ("Category", "category", "secret_type")),
        ("path", ("File", "file", "path")),
        ("line_start", ("StartLine", "start_line", "line_start")),
        ("line_end", ("EndLine", "end_line", "line_end")),
        ("commit", ("Commit", "commit")),
    )
    sanitized: dict[str, Any] = {}
    for target, candidates in field_sources:
        for key in candidates:
            if key in record and record[key] is not None:
                sanitized[target] = record[key]
                break
    if "path" not in sanitized and default_path:
        sanitized["path"] = default_path
    return sanitized


def sanitize_gitleaks_output(raw_output: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    """Strip matched secret values from Gitleaks output while preserving safe location metadata."""
    records: list[Any] = []
    if isinstance(raw_output, list):
        records = raw_output
    elif isinstance(raw_output, dict):
        records = raw_output.get("results", []) or []

    sanitized_records: list[dict[str, Any]] = []
    for item in records:
        if not isinstance(item, dict):
            continue
        rec = sanitize_secret_record(item)
        if rec:
            sanitized_records.append(rec)
    return sanitized_records


def sanitize_trivy_output(raw_output: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    """Remove secret values from Trivy output without removing vulnerability data."""
    if isinstance(raw_output, list):
        return [
            sanitize_trivy_output(value)
            if isinstance(value, (dict, list))
            else (redact_secret_patterns(value) if isinstance(value, str) else value)
            for value in raw_output
        ]
    if not isinstance(raw_output, dict):
        return redact_secret_patterns(raw_output) if isinstance(raw_output, str) else raw_output

    default_target = raw_output.get("Target") if isinstance(raw_output.get("Target"), str) else None
    sanitized: dict[str, Any] = {}
    for key, value in raw_output.items():
        if key == "Secrets" and isinstance(value, list):
            sanitized[key] = [
                sanitize_secret_record(item, default_path=default_target)
                for item in value
                if isinstance(item, dict)
            ]
        elif _is_secret_key(key):
            continue
        elif isinstance(value, (dict, list)):
            sanitized[key] = sanitize_trivy_output(value)
        elif isinstance(value, str):
            sanitized[key] = redact_secret_patterns(value)
        else:
            sanitized[key] = value
    return sanitized


def sanitize_scanner_output(scanner_name: str, raw_output: Any) -> Any:
    """Sanitize any scanner report before durable storage or downstream processing."""
    normalized_name = (scanner_name or "").strip().lower()
    if normalized_name == "gitleaks":
        return sanitize_gitleaks_output(raw_output if isinstance(raw_output, (dict, list)) else [])
    if normalized_name == "trivy":
        return sanitize_trivy_output(raw_output)
    return _sanitize_generic_scanner_value(raw_output)


def _sanitize_generic_scanner_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_sanitize_generic_scanner_value(item) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and _is_non_trivy_strip_key(k):
                continue
            cleaned[k] = _sanitize_generic_scanner_value(v)
        return cleaned
    if isinstance(value, str):
        return redact_secret_patterns(value)
    return value


def sanitize_secret_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Remove prohibited secret evidence and source snippets before any durable or external boundary."""
    sanitized = dict(finding)
    if sanitized.get("category") == "secret":
        sanitized["description"] = "A secret was detected by the scanner."
        if isinstance(sanitized.get("title"), str):
            sanitized["title"] = redact_secret_patterns(sanitized["title"])
        instance = dict(sanitized.get("instance") or {})
        safe_instance_keys = {"path", "line_start", "line_end", "commit", "rule_id", "secret_type"}
        sanitized["instance"] = {
            key: (redact_secret_patterns(value) if isinstance(value, str) else value)
            for key, value in instance.items()
            if key in safe_instance_keys and not _is_secret_key(key)
        }
        metadata = sanitized.get("metadata_json")
        if isinstance(metadata, dict):
            sanitized["metadata_json"] = {
                key: _sanitize_generic_scanner_value(value)
                for key, value in metadata.items()
                if not _is_secret_key(key)
            }
        return sanitized

    if isinstance(sanitized.get("title"), str):
        sanitized["title"] = redact_secret_patterns(sanitized["title"])
    if isinstance(sanitized.get("description"), str):
        sanitized["description"] = redact_secret_patterns(sanitized["description"])

    instance = sanitized.get("instance")
    if isinstance(instance, dict):
        sanitized["instance"] = {
            key: _sanitize_generic_scanner_value(value)
            for key, value in instance.items()
            if not _is_non_trivy_strip_key(key)
        }

    metadata = sanitized.get("metadata_json")
    if isinstance(metadata, dict):
        sanitized["metadata_json"] = {
            key: _sanitize_generic_scanner_value(value)
            for key, value in metadata.items()
            if not _is_non_trivy_strip_key(key)
        }
    return sanitized


def sanitize_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_secret_finding(finding) for finding in findings]


def _valid_artifact_component(value: str) -> bool:
    return (
        bool(value)
        and value not in {".", ".."}
        and "/" not in value
        and "\\" not in value
        and "\x00" not in value
    )


def safe_artifact_key(organization_id: str, scan_id: str, scanner_name: str, filename: str) -> str:
    """Build the required tenant-scoped object key and reject traversal.

    Every key component must be a single path-safe segment, so one tenant
    can never reach another organization's or scan's artifact prefix.
    """
    if not _valid_artifact_component(organization_id):
        raise ValueError("invalid artifact organization")
    if not _valid_artifact_component(scan_id):
        raise ValueError("invalid artifact scan")
    if not _valid_artifact_component(scanner_name):
        raise ValueError("invalid artifact scanner")
    if not _valid_artifact_component(Path(filename).name) or Path(filename).name != filename:
        raise ValueError("invalid artifact filename")
    return f"scan-artifacts/{organization_id}/{scan_id}/{scanner_name}/{filename}"


def assert_ai_disabled_for_private_beta() -> None:
    if (
        os.environ.get("APP_ENV", "development").lower() in {"private-beta", "managed-beta", "production"}
        and os.environ.get("AI_ENABLED", "false").lower() == "true"
    ):
        raise RuntimeError("AI investigation must remain disabled in private-beta")
