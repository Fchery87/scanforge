import asyncio
import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
)

from app.db.session import AsyncSessionLocal
from app.services.scan_schedules import ScanScheduleService
from app.services.scans import ScanService


async def run_scheduled_scans():
    async with AsyncSessionLocal() as db:
        schedule_service = ScanScheduleService(db)
        scan_service = ScanService(db)

        due_schedules = await schedule_service.get_due_schedules(limit=50)

        print(f"[scheduler] Found {len(due_schedules)} due schedules")

        for schedule in due_schedules:
            try:
                from app.db.enums import ScanTriggerType
                from app.schemas.scans import ScanCreate

                scan_data = ScanCreate(
                    repository_id=schedule.repository_id,
                    trigger_type=ScanTriggerType.SCHEDULED,
                    branch_name=None,
                )

                scan, _, _ = await scan_service.create(
                    schedule.repository_id, scan_data, user_id=None
                )

                from app.db.enums import ScanTriggerType

                from app.clients.queue import QueueClient

                queue = QueueClient(
                    redis_url=os.environ["UPSTASH_REDIS_REST_URL"],
                    redis_token=os.environ["UPSTASH_REDIS_REST_TOKEN"],
                )
                await queue.enqueue(
                    "scan.repo.full",
                    {
                        "scan_id": str(scan.id),
                        "repository_id": str(schedule.repository_id),
                        "project_id": str(scan.project_id),
                        "trigger_type": ScanTriggerType.SCHEDULED.value,
                    },
                )

                await schedule_service.mark_run(schedule.id)

                print(f"[scheduler] Queued scan {scan.id} for schedule {schedule.id}")

            except Exception as e:
                print(f"[scheduler] Error processing schedule {schedule.id}: {e}")


if __name__ == "__main__":
    asyncio.run(run_scheduled_scans())
