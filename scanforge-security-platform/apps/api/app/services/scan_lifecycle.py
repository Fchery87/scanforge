import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.queue import QueueClient
from app.core.config import settings
from app.core.error_messages import GENERIC_QUEUE_ERROR
from app.schemas.scans import ScanCreate
from app.services.scans import ScanService

logger = logging.getLogger(__name__)


@dataclass
class ScanLifecycleOutcome:
    scan: object
    enqueued: bool


class ScanLifecycleService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        scan_service: ScanService | None = None,
        queue: QueueClient | None = None,
    ):
        self.db = db
        self.scan_service = scan_service or ScanService(db)
        self.queue = queue or QueueClient(
            redis_url=settings.UPSTASH_REDIS_REST_URL,
            redis_token=settings.UPSTASH_REDIS_REST_TOKEN,
        )

    async def create_manual_scan(self, *, org_id: UUID, data, user_id: UUID):
        outcome = await self._create_and_enqueue_scan(org_id=org_id, data=data, user_id=user_id)
        return outcome.scan

    async def create_scheduled_scan(self, schedule) -> ScanLifecycleOutcome:
        data = ScanCreate(
            repository_id=schedule.repository_id,
            trigger_type="scheduled",
            scan_type=schedule.scan_type,
        )
        scan, _, project = await self.scan_service.create(schedule.repository_id, data, user_id=None)
        return await self._enqueue_existing_scan(scan, org_id=project.organization_id, scan_type=data.scan_type, user_id=None)

    async def _create_and_enqueue_scan(self, *, org_id: UUID, data, user_id: UUID | None) -> ScanLifecycleOutcome:
        scan, _, _ = await self.scan_service.create(data.repository_id, data, user_id)
        return await self._enqueue_existing_scan(scan, org_id=org_id, scan_type=data.scan_type, user_id=user_id)

    async def _enqueue_existing_scan(
        self,
        scan,
        *,
        org_id: UUID,
        scan_type: str,
        user_id: UUID | None,
    ) -> ScanLifecycleOutcome:
        job_type = self._job_type_for_scan_type(scan_type)

        try:
            job_id = await self.queue.enqueue(job_type, self._queue_payload(scan, org_id=org_id, user_id=user_id))
            logger.info("Enqueued scan %s as job %s (%s)", scan.id, job_id, job_type)
            return ScanLifecycleOutcome(scan=scan, enqueued=True)
        except Exception:
            logger.error("Failed to enqueue scan %s", scan.id, exc_info=True)
            scan.status = "failed"
            scan.error_message = GENERIC_QUEUE_ERROR
            await self.db.commit()
            await self.db.refresh(scan)
            return ScanLifecycleOutcome(scan=scan, enqueued=False)

    def _job_type_for_scan_type(self, scan_type: str) -> str:
        return {
            "full": "scan.repo.full",
            "diff": "scan.repo.diff",
            "dependencies": "scan.dependencies",
            "secrets": "scan.secrets",
        }.get(scan_type, "scan.repo.full")

    def _queue_payload(self, scan, *, org_id: UUID, user_id: UUID | None) -> dict:
        return {
            "scan_id": str(scan.id),
        }
