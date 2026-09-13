# ruff: noqa: TC002, TC003
from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ScanStatus
from app.db.models import Project, Scan, ScanCompletionReceipt, ScannerRun
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.findings import FindingService


class ScanCompletionConflict(Exception):
    """Completion cannot be applied to the current terminal scan state."""

    code = "completion_state_conflict"


class CompletionPayloadConflict(ScanCompletionConflict):
    """Same completion identity replayed with a different evidence payload."""

    code = "completion_payload_conflict"


class CompletionSuperseded(ScanCompletionConflict):
    """A different (stale or superseded) attempt or revision lost the race."""

    code = "completion_superseded"


def canonical_evidence_digest(data: ScanCompletionRequest) -> str:
    """Stable digest of the completion evidence payload."""
    payload = {
        "artifact_uris": data.artifact_uris,
        "execution_revision": data.execution_revision,
        "findings": [finding.model_dump(mode="json") for finding in data.findings],
        "scanner_runs": [run.model_dump(mode="json") for run in data.scanner_runs],
        "summary_json": data.summary_json,
        "winning_attempt_id": str(data.winning_attempt_id),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
                .where(
                    Scan.id == str(scan_id),
                    Project.organization_id == str(organization_id),
                )
                .with_for_update()
            )
            scan = result.scalar_one_or_none()
            if not scan:
                raise LookupError("Scan not found")
            if scan.status == ScanStatus.CANCELED:
                raise ScanCompletionConflict("Canceled scans cannot be completed")

            digest = canonical_evidence_digest(data)
            receipt = (
                await self.db.execute(
                    select(ScanCompletionReceipt).where(ScanCompletionReceipt.scan_id == str(scan_id))
                )
            ).scalar_one_or_none()
            if receipt is not None:
                return self._replay_response(receipt, data, digest)

            issued_attempt_id = getattr(scan, "current_attempt_id", None)
            if issued_attempt_id is not None and (
                issued_attempt_id != str(data.winning_attempt_id)
                or getattr(scan, "execution_revision", None) != data.execution_revision
            ):
                # The scan row holds the latest server-issued identity; anything
                # else lost the race before a receipt could exist.
                raise CompletionSuperseded(
                    "Completion was superseded by another attempt or execution revision"
                )

            if scan.status == ScanStatus.COMPLETED:
                # Legacy completed scan without a server-owned receipt.
                return {
                    "scan_id": scan.id,
                    "status": scan.status.value,
                    "inserted_findings": 0,
                    "updated_findings": 0,
                    "scanner_runs": 0,
                    "scanner_runs_complete": False,
                    "winning_attempt_id": None,
                    "execution_revision": None,
                    "evidence_digest": None,
                    "replayed": True,
                }

            return await self._commit_completion(scan, data, digest)
        except Exception:
            await self.db.rollback()
            raise

    def _replay_response(self, receipt: ScanCompletionReceipt, data: ScanCompletionRequest, digest: str) -> dict:
        if (
            receipt.winning_attempt_id != str(data.winning_attempt_id)
            or receipt.execution_revision != data.execution_revision
        ):
            raise CompletionSuperseded(
                "Completion was superseded by another attempt or execution revision"
            )
        if receipt.evidence_digest != digest:
            raise CompletionPayloadConflict(
                "Completion evidence differs from the accepted completion for this identity"
            )
        response = dict(receipt.response_json or {})
        response.update(
            {
                "scan_id": receipt.scan_id,
                "status": receipt.terminal_status,
                "inserted_findings": receipt.inserted_findings,
                "updated_findings": receipt.updated_findings,
                "scanner_runs": receipt.scanner_runs_total,
                "scanner_runs_complete": receipt.scanner_runs_complete,
                "winning_attempt_id": receipt.winning_attempt_id,
                "execution_revision": receipt.execution_revision,
                "evidence_digest": receipt.evidence_digest,
                "replayed": True,
            }
        )
        return response

    async def _commit_completion(self, scan: Scan, data: ScanCompletionRequest, digest: str) -> dict:
        scan_id = scan.id
        existing_runs = await self.db.execute(
            select(ScannerRun).where(ScannerRun.scan_id == str(scan_id))
        )
        runs_by_name = {run.scanner_name: run for run in existing_runs.scalars()}
        for run_data in data.scanner_runs:
            run = runs_by_name.get(run_data.scanner_name)
            if run is None:
                run = ScannerRun(
                    scan_id=str(scan_id),
                    scanner_name=run_data.scanner_name,
                )
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
        receipt = ScanCompletionReceipt(
            scan_id=str(scan_id),
            winning_attempt_id=str(data.winning_attempt_id),
            execution_revision=data.execution_revision,
            evidence_digest=digest,
            terminal_status=ScanStatus.COMPLETED.value,
            inserted_findings=inserted,
            updated_findings=updated,
            scanner_runs_total=len(data.scanner_runs),
            scanner_runs_complete=bool(
                (data.summary_json.get("scanner_health") or {}).get("complete")
            ),
            response_json={
                "scan_id": str(scan_id),
                "status": ScanStatus.COMPLETED.value,
                "inserted_findings": inserted,
                "updated_findings": updated,
                "scanner_runs": len(data.scanner_runs),
                "scanner_runs_complete": bool(
                    (data.summary_json.get("scanner_health") or {}).get("complete")
                ),
                "winning_attempt_id": str(data.winning_attempt_id),
                "execution_revision": data.execution_revision,
                "evidence_digest": digest,
            },
        )
        self.db.add(receipt)
        await self.db.flush()
        await self.db.commit()
        return {
            **receipt.response_json,
            "replayed": False,
        }

