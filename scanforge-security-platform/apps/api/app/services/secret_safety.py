from __future__ import annotations

from typing import Any

_SECRET_KEY_PARTS = {
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


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("_", "").replace("-", "").lower()
    return normalized in {part.replace("_", "") for part in _SECRET_KEY_PARTS}


def sanitize_secret_mapping(value: Any, *, secret_context: bool = False) -> Any:
    """Recursively remove secret-value fields while preserving safe metadata."""
    if isinstance(value, list):
        return [sanitize_secret_mapping(item, secret_context=secret_context) for item in value]
    if not isinstance(value, dict):
        return value

    context = secret_context or str(value.get("category", "")).lower() == "secret"
    sanitized: dict[str, Any] = {}
    for key, child in value.items():
        if context and _is_sensitive_key(str(key)):
            continue
        sanitized[str(key)] = sanitize_secret_mapping(child, secret_context=context)
    if context and "description" in sanitized:
        sanitized["description"] = "A secret was detected by the scanner."
    return sanitized
