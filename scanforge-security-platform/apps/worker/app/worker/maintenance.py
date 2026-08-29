"""Weekly maintenance tasks — runs on a cron schedule via Render."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))))


def _load_env(current_file: str | Path | None = None):
    current = Path(current_file or __file__).resolve()
    for parent in current.parents:
        env_path = parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv

            load_dotenv(env_path, override=False)
            return


_load_env()

from app.clients.queue import QueueClient  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

_log = get_logger(__name__)


async def run_cleanup(purge_scan_queue: bool = False):
    _log.info("starting weekly maintenance tasks")

    queue = QueueClient(
        redis_url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
        redis_token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", ""),
        organization_id=os.environ.get("WORKER_ORGANIZATION_ID", ""),
        consumer_name=os.environ.get("WORKER_CONSUMER_NAME", "maintenance"),
    )

    reclaimed = await queue.reclaim_stale_jobs()
    _log.info("reclaimed stale scan jobs", extra={"reclaimed": len(reclaimed)})

    if purge_scan_queue:
        deleted_keys = await queue.clear_scan_queues()
        _log.info("purged scan queues", extra={"deleted_keys": deleted_keys})

    _log.info("weekly maintenance complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Worker maintenance tasks")
    parser.add_argument(
        "--purge-scan-queue",
        action="store_true",
        help="Delete the active and dead-letter scan queues from Redis",
    )
    args = parser.parse_args()

    asyncio.run(run_cleanup(purge_scan_queue=args.purge_scan_queue))
