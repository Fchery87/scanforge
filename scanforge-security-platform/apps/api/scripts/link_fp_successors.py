"""Repeatable fp.v2 -> fp.v3 successor link step (#40, ADR-014).

Links only exact matches, never transfers dispositions, and prints per-repository
linked / unlinked / preserved counts. Safe to run any number of times.
"""

import asyncio

from sqlalchemy import select

from app.db.models import Repository
from app.db.session import AsyncSessionLocal
from app.services.finding_successors import link_fp_successors


async def main() -> None:
    totals = {"newly_linked": 0, "linked": 0, "unlinked": 0, "preserved": 0}
    async with AsyncSessionLocal() as db:
        for repository_id in (await db.execute(select(Repository.id))).scalars().all():
            counts = await link_fp_successors(db, repository_id=str(repository_id))
            await db.commit()
            for key, value in counts.items():
                totals[key] += value
            print(f"{repository_id} {counts}")
    print(f"total {totals}")


if __name__ == "__main__":
    asyncio.run(main())
