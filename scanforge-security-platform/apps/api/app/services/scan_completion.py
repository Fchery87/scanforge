# ruff: noqa: TC002, TC003
from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.enums import ScanStatus
from app.db.models import Project, Scan, ScanCompletionReceipt, ScannerRun
from app.schemas.scan_completion import ScanCompletionRequest
from app.services.findings import FindingService

ARTIFACT_KEY_SEGMENTS = 5

EXPECTED_SCANNERS: dict[str, tuple[str, ...]] = {
    "full": ("trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"),
    "diff": ("gitleaks", "semgrep", "checkov"),
    "dependencies": ("trivy", "osv", "syft", "grype"),
    "secrets": ("gitleaks",),
}


class ScanCompletionConflict(Exception):
    """Completion cannot be applied to the current terminal or execution state."""

    code = "completion_state_conflict"


class CompletionPayloadConflict(ScanCompletionConflict):
    code = "completion_payload_conflict"


class CompletionSuperseded(ScanCompletionConflict):
    code = "completion_superseded"


def canonical_evidence_digest(data: ScanCompletionRequest) -> str:
    payload = {
        "contract_version": data.contract_version,
        "observed_commit_sha": data.observed_commit_sha,
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

    @classmethod
    def _scanner_provenance_is_comparable(cls, run) -> bool:
        metadata = run.metadata_json if isinstance(run.metadata_json, dict) else {}
        return bool(run.scanner_version and any(
            isinstance(metadata.get(key), str) and metadata[key].strip()
            for key in ("configuration_digest", "rules_version", "database_version")
        ))

    @staticmethod
    def _validate_artifacts(scan, organization_id, data: ScanCompletionRequest, expected: set[str]) -> None:
        def validate(value):
            if isinstance(value, dict):
                for item in value.values():
                    validate(item)
                return
            if not isinstance(value, str):
                raise ScanCompletionConflict("Invalid artifact reference")
            parts = value.split("/")
            if (
                len(parts) != ARTIFACT_KEY_SEGMENTS
                or parts[:3] != ["scan-artifacts", str(organization_id), str(scan.id)]
                or parts[3] not in expected
                or parts[3] == "gitleaks"
                or not parts[4]
                or any(part in {".", ".."} or "\\" in part or "\x00" in part for part in parts)
            ):
                raise ScanCompletionConflict("Invalid artifact ownership")

        validate(data.artifact_uris)
        ScanCompletionService._validate_artifact_aliases(data.artifact_uris, expected)
        for run in data.scanner_runs:
            if run.artifact_uri:
                validate(run.artifact_uri)
                if run.artifact_uri.split("/")[3] != run.scanner_name:
                    raise ScanCompletionConflict("Invalid artifact scanner ownership")
            for key in ("artifact_uri", "raw_output_uri"):
                value = (run.metadata_json or {}).get(key)
                if value is not None:
                    validate(value)
                    if value.split("/")[3] != run.scanner_name:
                        raise ScanCompletionConflict("Invalid artifact scanner ownership")

    @staticmethod
    def _validate_artifact_aliases(artifacts: dict, expected: set[str]) -> None:
        for alias, value in artifacts.items():
            if alias == "scanner_runs":
                if not isinstance(value, dict):
                    raise ScanCompletionConflict("Invalid artifact scanner ownership")
                for scanner, refs in value.items():
                    if scanner not in expected or not isinstance(refs, dict):
                        raise ScanCompletionConflict("Invalid artifact scanner ownership")
                    for ref in refs.values():
                        if not isinstance(ref, str) or ref.split("/")[3] != scanner:
                            raise ScanCompletionConflict("Invalid artifact scanner ownership")
            else:
                scanner = next((name for name in expected if alias.startswith(f"{name}_")), None)
                if scanner is None or not isinstance(value, str) or value.split("/")[3] != scanner:
                    raise ScanCompletionConflict("Invalid artifact scanner ownership")

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

            current_attempt_id = getattr(scan, "current_attempt_id", None)
            if current_attempt_id is None or (
                current_attempt_id != str(data.winning_attempt_id)
                or getattr(scan, "execution_revision", 0) != data.execution_revision
            ):
                raise CompletionSuperseded("Completion requires the current server-issued execution attempt")

            if scan.status == ScanStatus.COMPLETED:
                raise CompletionSuperseded("Completed scan has no matching completion receipt")

            expected = set(EXPECTED_SCANNERS.get(scan.scan_type or "full", EXPECTED_SCANNERS["full"]))
            self._validate_artifacts(scan, organization_id, data, expected)
            recorded_commit = getattr(scan, "head_commit_sha", None) or getattr(scan, "commit_sha", None)
            if data.observed_commit_sha:
                if recorded_commit and recorded_commit.lower() != data.observed_commit_sha.lower():
                    raise ScanCompletionConflict("Observed commit differs from the recorded scan context")
                scan.commit_sha = data.observed_commit_sha.lower()
            elif settings.APP_ENV == "private-beta":
                raise ScanCompletionConflict("Completion requires the observed repository commit")
            return await self._commit_completion(scan, data, digest)
        except Exception:
            await self.db.rollback()
            raise

    def _replay_response(
        self,
        receipt: ScanCompletionReceipt,
        data: ScanCompletionRequest,
        digest: str,
    ) -> dict:
        if (
            receipt.winning_attempt_id != str(data.winning_attempt_id)
            or receipt.execution_revision != data.execution_revision
        ):
            raise CompletionSuperseded("Completion was superseded by another execution attempt")
        if receipt.evidence_digest != digest:
            raise CompletionPayloadConflict("Completion evidence differs from the accepted completion")
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
    ) -> dict:
        expected = set(EXPECTED_SCANNERS.get(scan.scan_type or "full", EXPECTED_SCANNERS["full"]))
        provided = [run.scanner_name for run in data.scanner_runs]
        provided_set = set(provided)
        if len(provided) != len(provided_set):
            raise ScanCompletionConflict("Completion contains duplicate scanner names")
        unknown = provided_set - expected
        if unknown:
            raise ScanCompletionConflict(f"Completion contains unknown scanners: {sorted(unknown)}")

        missing = sorted(expected - provided_set)
        failed = sorted(
            run.scanner_name for run in data.scanner_runs if run.status == ScanStatus.FAILED.value
        )
        invalid_statuses = [
            run.scanner_name
            for run in data.scanner_runs
            if run.status not in {ScanStatus.COMPLETED.value, ScanStatus.FAILED.value}
        ]
        if invalid_statuses:
            raise ScanCompletionConflict("Scanner runs must be completed or failed")

        existing_runs = await self.db.execute(
            select(ScannerRun).where(ScannerRun.scan_id == str(scan.id))
        )
        runs_by_name = {run.scanner_name: run for run in existing_runs.scalars()}
        for run_data in data.scanner_runs:
            run = runs_by_name.get(run_data.scanner_name)
            if run is None:
                run = ScannerRun(scan_id=str(scan.id), scanner_name=run_data.scanner_name)
                self.db.add(run)
                runs_by_name[run_data.scanner_name] = run
            run.scanner_version = run_data.scanner_version
            run.status = ScanStatus(run_data.status)
            run.duration_ms = run_data.duration_ms
            run.exit_code = run_data.exit_code
            run.error_message = run_data.error_message
            run.artifact_uri = run_data.artifact_uri
            run.metadata_json = dict(run_data.metadata_json or {})

        await self.db.flush()
        finding_service = FindingService(self.db)
        inserted, updated = await finding_service.upsert_from_scan(
            scan_id=str(scan.id),
            repository_id=str(scan.repository_id),
            project_id=str(scan.project_id),
            normalized_findings=data.findings,
            commit=False,
            scanner_provenance={
                name: {**(run.metadata_json or {}), "scanner_version": run.scanner_version}
                for name, run in runs_by_name.items()
                if run.status == ScanStatus.COMPLETED
            },
        )
        seen_fingerprints = {
            finding.canonical_fingerprint
            for finding in data.findings
            if finding.canonical_fingerprint
        }
        scanner_health = {
            "expected": sorted(expected),
            "completed": sorted(provided_set - set(failed)),
            "failed": failed,
            "missing": missing,
            "complete": not failed and not missing,
        }
        summary = dict(data.summary_json)
        summary["artifact_uris"] = data.artifact_uris
        summary["seen_fingerprints"] = sorted(seen_fingerprints)
        summary["scanner_health"] = scanner_health
        summary["coverage_complete"] = scanner_health["complete"]
        summary["coverage_comparable"] = bool(
            scan.scan_type == "full"
            and scanner_health["complete"]
            and all(
                self._scanner_provenance_is_comparable(runs_by_name[name])
                for name in expected
                if name in runs_by_name
            )
            and len(runs_by_name) >= len(expected)
        )
        scan.summary_json = summary
        await finding_service.mark_not_observed_after_scan(
            repository_id=str(scan.repository_id),
            scan_id=str(scan.id),
            seen_fingerprints=seen_fingerprints,
            scan_summary=summary,
            commit=False,
        )
        scan.status = ScanStatus.COMPLETED
        if getattr(scan, "trigger_type", None) == "pull_request":
            scan.github_check_pending = True
        scanner_runs_complete = scanner_health["complete"]
        response = {
            "scan_id": str(scan.id),
            "status": ScanStatus.COMPLETED.value,
            "inserted_findings": inserted,
            "updated_findings": updated,
            "scanner_runs": len(data.scanner_runs),
            "scanner_runs_complete": scanner_runs_complete,
            "winning_attempt_id": str(data.winning_attempt_id),
            "execution_revision": data.execution_revision,
            "evidence_digest": digest,
        }
        self.db.add(
            ScanCompletionReceipt(
                scan_id=str(scan.id),
                winning_attempt_id=str(data.winning_attempt_id),
                execution_revision=data.execution_revision,
                evidence_digest=digest,
                terminal_status=ScanStatus.COMPLETED.value,
                inserted_findings=inserted,
                updated_findings=updated,
                scanner_runs_total=len(data.scanner_runs),
                scanner_runs_complete=scanner_runs_complete,
                response_json=response,
            )
        )
        await self.db.flush()
        await self.db.commit()
        return {**response, "replayed": False}
