from __future__ import annotations

import re
from typing import Any

_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*(?:basic|bearer)\s+)\S+"),
    re.compile(r"(?i)(https://x-access-token:)[^@\s]+@github\.com"),
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
