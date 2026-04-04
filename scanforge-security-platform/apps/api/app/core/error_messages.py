GENERIC_INTERNAL_ERROR = "An internal error occurred. Please try again later."
GENERIC_EXTERNAL_SERVICE_ERROR = "Upstream service request failed. Please try again later."
GENERIC_QUEUE_ERROR = "Scan could not be queued. Please try again later."


def safe_error_message(message: str | None, fallback: str = GENERIC_INTERNAL_ERROR) -> str:
    if not message:
        return fallback
    lowered = message.lower()
    sensitive_markers = (
        "token",
        "secret",
        "authorization",
        "password",
        "traceback",
        "github",
        "jwt",
        "key",
        "credential",
        "access denied",
        "connection refused",
    )
    if any(marker in lowered for marker in sensitive_markers):
        return fallback
    return message[:200]
