# ruff: noqa: TC002, TC003
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import ScanStatus
from app.db.models import Project, Scan, ScanCompletionReceipt, ScannerRun
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.evidence_contract import (
    compute_canonical_evidence_digest,
    derive_scan_evidence_decision,
)
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
    """Stable digest of validated evidence with order-independent collections."""
    return compute_canonical_evidence_digest(data)


class ScanCompletionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def complete(
        self,
        scan_id: UUID,
        organization_id: UUID,
        data: ScanCompletionRequest,
        *,
        worker_principal_id: str | None = None,
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
                or getattr(scan, "worker_incarnation_id", None) != data.worker_incarnation_id
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

            return await self._commit_completion(
                scan,
                data,
                digest,
                worker_principal_id=worker_principal_id,
            )
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

    async def _commit_completion(
        self,
        scan: Scan,
        data: ScanCompletionRequest,
        digest: str,
        *,
        worker_principal_id: str | None,
    ) -> dict:
        scan_id = scan.id
        decision = derive_scan_evidence_decision(
            data,
            expected_scanners=getattr(scan, "expected_scanners_json", None),
            commit_sha=getattr(scan, "commit_sha", None),
            full_ref_name=getattr(scan, "full_ref_name", None),
            branch_generation_number=getattr(scan, "branch_generation_number", 1),
            ancestry_status=getattr(scan, "ancestry_status", "unknown"),
            cleanup_state=getattr(scan, "cleanup_state", "unknown"),
            superseded_by_scan_id=getattr(scan, "superseded_by_scan_id", None),
        )
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
                    attempt_id=str(data.winning_attempt_id),
                    execution_revision=data.execution_revision,
                )
                self.db.add(run)
            run.attempt_id = str(data.winning_attempt_id)
            run.execution_revision = data.execution_revision
            run.scanner_version = run_data.scanner_version
            run.status = ScanStatus(run_data.status)
            run.outcome_status = run_data.outcome_status or run_data.status
            run.parser_version = run_data.parser_version
            run.rules_digest = run_data.rules_digest
            run.db_digest = run_data.db_digest
            run.db_published_at = run_data.db_published_at
            run.db_freshness_state = run_data.db_freshness_state
            run.image_digest = run_data.image_digest
            run.artifact_availability = run_data.artifact_availability
            run.closure_eligible = decision.closure_eligible
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
        seen_fingerprints = {finding.canonical_fingerprint for finding in data.findings}
        scanner_health = {
            "expected": list(decision.expected_scanners),
            "completed": list(decision.completed_scanners),
            "failed": list(decision.failed_scanners),
            "missing": list(decision.missing_scanners),
            "complete": decision.scanner_runs_complete,
        }
        scan.summary_json = {
            **data.summary_json,
            "scanner_health": scanner_health,
            "seen_fingerprints": sorted(seen_fingerprints),
            "coverage_completeness": decision.coverage_completeness,
            "closure_eligible": decision.closure_eligible,
            "artifact_availability": decision.artifact_availability,
            "severity_counts": decision.severity_counts,
            "ineligibility_reasons": list(decision.ineligibility_reasons),
        }
        scan.contract_version = decision.contract_version
        scan.coverage_completeness = decision.coverage_completeness
        scan.closure_eligible = decision.closure_eligible
        scan.artifact_availability = decision.artifact_availability
        if decision.closure_eligible:
            await finding_service.mark_not_observed_after_scan(
                repository_id=str(scan.repository_id),
                scan_id=str(scan.id),
                seen_fingerprints=seen_fingerprints,
                scan_summary=scan.summary_json,
                commit=False,
            )
        scan.status = ScanStatus.COMPLETED
        receipt = ScanCompletionReceipt(
            scan_id=str(scan_id),
            worker_principal_id=worker_principal_id,
            worker_incarnation_id=data.worker_incarnation_id,
            winning_attempt_id=str(data.winning_attempt_id),
            execution_revision=data.execution_revision,
            evidence_digest=digest,
            terminal_status=ScanStatus.COMPLETED.value,
            inserted_findings=inserted,
            updated_findings=updated,
            scanner_runs_total=len(data.scanner_runs),
            scanner_runs_complete=decision.scanner_runs_complete,
            coverage_completeness=decision.coverage_completeness,
            closure_eligible=decision.closure_eligible,
            artifact_availability=decision.artifact_availability,
            response_json={
                "scan_id": str(scan_id),
                "status": ScanStatus.COMPLETED.value,
                "inserted_findings": inserted,
                "updated_findings": updated,
                "scanner_runs": len(data.scanner_runs),
                "scanner_runs_complete": decision.scanner_runs_complete,
                "coverage_completeness": decision.coverage_completeness,
                "closure_eligible": decision.closure_eligible,
                "artifact_availability": decision.artifact_availability,
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

