import json
import logging
from datetime import UTC, datetime

_SAFE_FIELDS = {
    "scan_id", "job_id", "org_id", "scanner", "error", "request_id",
    "queue_length", "active_tasks", "workers", "previous_status", "status",
    "backoff_seconds", "degraded_since", "length", "retry_count", "max_retries",
    "timeout", "concurrency", "incarnation_id", "found", "queued", "failed",
    "error_type", "job_type", "reclaimed", "deleted_keys", "reason", "duration_ms",
}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in _SAFE_FIELDS:
            value = getattr(record, key, None)
            if value is not None and isinstance(value, (str, int, float, bool)):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
