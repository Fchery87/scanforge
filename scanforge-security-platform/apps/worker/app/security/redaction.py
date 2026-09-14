from __future__ import annotations

import re
from typing import Any

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*(?:basic|bearer)\s+)\S+"),
    re.compile(r"(?i)(https://x-access-token:)[^@\s]+@github\.com"),
    re.compile(r"(?i)([?&](?:x-amz-signature|signature|token|access_token|api_key|apikey|key)=)[^&\s]+"),
    re.compile(r"(?i)(x-amz-credential=)\S+"),
)

_SENSITIVE_KEY_MARKERS = (
    "token",
    "secret",
    "password",
    "credential",
    "authorization",
    "api_key",
    "apikey",
    "signature",
    "webhook",
)


def safe_exception_message(_error: BaseException) -> str:
    """Return a stable error message without reflecting scanner or credential data."""
    return "Operation failed; see operator logs for the correlation identifier."


def redact_sensitive_text(value: Any, known_secrets: tuple[str, ...] = ()) -> str:
    redacted = str(value or "")
    for secret in known_secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    for pattern in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(r"\1[REDACTED]", redacted)
    return redacted


def _is_sensitive_key(key: str) -> bool:
    normalized = key.replace("-", "_").lower()
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def redact_payload(value: Any, known_secrets: tuple[str, ...] = ()) -> Any:
    """Recursively scrub credential values from structured log/receipt payloads.

    Dictionary keys that name credentials are redacted wholesale; string
    values pass through :func:`redact_sensitive_text`. Safe fields such as
    identifiers, paths, and counters are preserved unchanged.
    """
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if isinstance(key, str) and _is_sensitive_key(key)
                else redact_payload(item, known_secrets)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item, known_secrets) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value, known_secrets)
    return value
