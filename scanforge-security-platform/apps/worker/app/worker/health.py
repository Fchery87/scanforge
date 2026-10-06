from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path


def health_path() -> Path:
    return Path(os.environ.get("WORKER_HEALTH_FILE", str(Path(tempfile.gettempdir()) / "scanforge-worker-health.json")))


def write_health(*, queue_available: bool, queue_failures: int) -> None:
    path = health_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "pid": os.getpid(), "updated_at": time.time(),
        "organization_id": os.environ.get("WORKER_ORGANIZATION_ID"),
        "queue_available": queue_available, "queue_failures": queue_failures,
    }))
    temporary.replace(path)


def ready() -> bool:
    try:
        status = json.loads(health_path().read_text())
        os.kill(status["pid"], 0)
        return bool(
            status["queue_available"] is True
            and 0 <= time.time() - status["updated_at"] <= 90
            and status["organization_id"] == os.environ.get("WORKER_ORGANIZATION_ID")
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if ready() else 1)
