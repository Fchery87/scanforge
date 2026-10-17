from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from app.db.session import AsyncSessionLocal
from app.services.scan_dispatch import ScanDispatchService

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.clients.queue import QueueClient

logger = logging.getLogger(__name__)
DISPATCH_BATCH_SIZE = 100


async def dispatch_due_scans(
    *,
    session_factory: Callable = AsyncSessionLocal,
    queue: QueueClient | None = None,
    limit: int = DISPATCH_BATCH_SIZE,
) -> int:
    """Dispatch one bounded batch of accepted scans whose obligations are due."""
    async with session_factory() as session:
        service = ScanDispatchService(session, queue=queue)
        results = await service.dispatch_due_obligations(
            lease_owner=f"api-dispatcher-{uuid4()}",
            limit=limit,
        )

    dispatched = sum(result.dispatched for result in results)
    if results and dispatched != len(results):
        logger.warning(
            "Dispatch batch completed with %s of %s obligations still pending",
            len(results) - dispatched,
            len(results),
        )
    return dispatched


async def main() -> None:
    await dispatch_due_scans()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
