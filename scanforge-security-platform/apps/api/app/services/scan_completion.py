from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ScanStatus
from app.db.models import Project, Scan, ScannerRun
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.findings import FindingService


class ScanCompletionConflict(Exception):
    """Completion cannot be applied to the current terminal scan state."""


class ScanCompletionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def complete(
        self,
        scan_id: UUID,
        organization_id: UUID,
        data: ScanCompletionRequest,
    ) -> dict:
        try:
            result = await self.db.execute(
                select(Scan)
                .join(Project, Project.id == Scan.project_id)
                .where(Scan.id == str(scan_id), Project.organization_id == str(organization_id))
                .with_for_update()
            )
            scan = result.scalar_one_or_none()
            if not scan:
                raise LookupError("Scan not found")
            if scan.status == ScanStatus.CANCELED:
                raise ScanCompletionConflict("Canceled scans cannot be completed")
            if scan.status == ScanStatus.COMPLETED:
                return {
                    "scan_id": scan.id,
                    "status": scan.status.value,
                    "inserted_findings": 0,
                    "updated_findings": 0,
                    "scanner_runs": len(data.scanner_runs),
                    "replayed": True,
                }

            existing_runs = await self.db.execute(select(ScannerRun).where(ScannerRun.scan_id == str(scan_id)))
            runs_by_name = {run.scanner_name: run for run in existing_runs.scalars()}
            for run_data in data.scanner_runs:
                run = runs_by_name.get(run_data.scanner_name)
                if run is None:
                    run = ScannerRun(scan_id=str(scan_id), scanner_name=run_data.scanner_name)
                    self.db.add(run)
                run.scanner_version = run_data.scanner_version
                run.status = ScanStatus(run_data.status)
                run.duration_ms = run_data.duration_ms
                run.exit_code = run_data.exit_code
                run.error_message = run_data.error_message
                run.artifact_uri = run_data.artifact_uri
                run.metadata_json = run_data.metadata_json

            await self.db.flush()

            finding_service = FindingService(self.db)
            inserted, updated = await finding_service.upsert_from_scan(
                scan_id=str(scan_id),
                repository_id=str(scan.repository_id),
                project_id=str(scan.project_id),
                normalized_findings=data.findings,
                commit=False,
            )
            scan.summary_json = data.summary_json
            await finding_service.mark_not_observed_after_scan(
                repository_id=str(scan.repository_id),
                scan_id=str(scan.id),
                seen_fingerprints=set(data.summary_json.get("seen_fingerprints") or []),
                scan_summary=data.summary_json,
                commit=False,
            )
            scan.status = ScanStatus.COMPLETED
            await self.db.flush()
            await self.db.commit()
            return {
                "scan_id": scan.id,
                "status": scan.status.value,
                "inserted_findings": inserted,
                "updated_findings": updated,
                "scanner_runs": len(data.scanner_runs),
                "replayed": False,
            }
        except Exception:
            await self.db.rollback()
            raise
