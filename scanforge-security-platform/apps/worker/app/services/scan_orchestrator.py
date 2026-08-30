from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

from app.clients.queue import QueueClient, QueueJob
from app.clients.r2 import R2Client
from app.core.alerts import send_slack_alert
from app.core.logging import get_logger
from app.security.redaction import redact_sensitive_text
from app.services.ai_investigation.stage import AIInvestigationStage
from app.services.scan_pipeline.context import ScanContext
from app.services.scan_pipeline.execution import ScanExecutionStage
from app.services.scan_pipeline.normalization import NormalizationStage
from app.services.scan_pipeline.persistence import PersistenceStage

if TYPE_CHECKING:
    from app.services.notifications import NotificationDispatcher

_log = get_logger(__name__)


class ScanOrchestrator:
    MAX_RETRIES = 3

    def __init__(
        self,
        queue: QueueClient,
        r2: R2Client,
        api_base_url: str = "http://localhost:8000",
        worker_credential: str = "",
        runtime=None,
    ):
        self.queue = queue
        self.r2 = r2
        self.api_base_url = api_base_url
        self._worker_credential = worker_credential or os.environ.get("WORKER_CREDENTIAL", "")
        self._notifier: NotificationDispatcher | None = None

        self._execution = ScanExecutionStage(
            r2,
            api_base_url,
            self._worker_credential,
            runtime=runtime,
        )
        self._normalization = NormalizationStage()
        self._ai_investigation = AIInvestigationStage()
        self._persistence = PersistenceStage(api_base_url, self._worker_credential)

    def set_notifier(self, notifier: NotificationDispatcher) -> None:
        self._notifier = notifier

    def _redact_sensitive_text(self, value: str) -> str:
        return redact_sensitive_text(value, (self._worker_credential,))

    async def _is_canceled(self, context: ScanContext) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/execution-context",
                headers={"X-Worker-Credential": self._worker_credential},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json().get("status") == "canceled"

    async def _stop_if_canceled(self, context: ScanContext, job: QueueJob) -> bool:
        if not await self._is_canceled(context):
            return False
        await self._update_status(context, "canceled")
        await self.queue.ack(job)
        return True

    async def process_job(self, job: QueueJob) -> bool:
        context = await self._load_scan_context(job)
        _log.info("scan job started", extra={"scan_id": context.scan_id, "job_id": context.job_id})

        try:
            await self._update_status(context, "claimed")
            await self._update_scan_status(context, "running")
            if await self._stop_if_canceled(context, job):
                return True

            # Stage 1 — Execution: clone, scan, upload
            await self._update_status(context, "repo_preparing")
            context.repo_path = await self._execution.prepare_repository(context)
            if await self._stop_if_canceled(context, job):
                return True

            if job.job_type == "scan.repo.diff":
                context.changed_files = await self._execution.collect_changed_files(context.repo_path)

            await self._update_status(context, "scanners_running")
            context.scanner_results = await self._execution.run_scanners(context, job.job_type)
            if await self._stop_if_canceled(context, job):
                return True

            await self._update_status(context, "artifacts_uploading")
            context.artifact_uris = await self._execution.upload_artifacts(context)
            if await self._stop_if_canceled(context, job):
                return True

            # Stage 2 — Normalization
            await self._update_status(context, "normalizing")
            context.findings = self._normalization.normalize_results(context)
            if job.job_type == "scan.repo.diff":
                context.findings = self._normalization.filter_to_changed_files(
                    context.findings, context.changed_files or []
                )
            context.critical_count = sum(1 for f in context.findings if f.get("severity") == "critical")
            context.high_count = sum(1 for f in context.findings if f.get("severity") == "high")

            # Stage 3 — AI investigation (non-blocking)
            await self._update_status(context, "ai_investigating")
            await self._ai_investigation.run(context, job_type=job.job_type)

            # Atomic completion is the only operation that can mark the scan complete.
            duration = (datetime.now(UTC) - context.start_time.replace(tzinfo=UTC)).total_seconds()
            context.summary_json = self._build_completion_summary(
                context,
                job_type=job.job_type,
                duration_seconds=duration,
            )
            await self._update_status(context, "persisting")
            if await self._stop_if_canceled(context, job):
                return True
            await self._persistence.complete_scan(context)

            await self._update_status(context, "done")
            await self._persistence.send_notifications(context, self._notifier)
            await self.queue.ack(job)

            _log.info(
                "scan job completed",
                extra={
                    "scan_id": context.scan_id,
                    "job_id": context.job_id,
                    "finding_count": len(context.findings),
                    "critical_count": context.critical_count,
                },
            )
            return True

        except Exception as exc:
            context.scan_failed = True
            safe_error = self._redact_sensitive_text(str(exc))
            context.error_message = safe_error
            _log.error(
                "scan job failed",
                extra={"scan_id": context.scan_id, "job_id": context.job_id, "error": safe_error},
            )
            await self._update_status(context, "failed", {"error": safe_error})

            retry_count = await self.queue.increment_retry(context.job_id)
            await self._update_scan_status(
                context, "failed", error=safe_error, summary={"retry_count": retry_count},
            )

            if retry_count >= self.MAX_RETRIES:
                await self.queue.move_to_dlq(job)
                await self._update_scan_status(context, "failed", error=f"Max retries exceeded: {safe_error}")
                await self._persistence.send_failure_notification(context, self._notifier, retry_count)
                await send_slack_alert(
                    f"Scan `{context.scan_id}` failed after {retry_count} retries.\nError: {safe_error}",
                    title="ScanForge: Scan Failure",
                )
                return False

            await self.queue.requeue(job, delay_seconds=min(retry_count * 30, 300))
            return False

        finally:
            if context.repo_path and context.repo_path.exists():
                shutil.rmtree(context.repo_path, ignore_errors=True)

    async def _load_scan_context(self, job: QueueJob) -> ScanContext:
        scan_id = job.payload.get("scan_id")
        if not scan_id:
            raise RuntimeError("scan job payload missing scan_id")
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.api_base_url}/api/v1/internal/scans/{scan_id}/execution-context",
                headers={"X-Worker-Credential": self._worker_credential},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return ScanContext(
            scan_id=data["scan_id"],
            organization_id=data["org_id"],
            repository_id=data["repository_id"],
            project_id=data["project_id"],
            branch=data.get("branch"),
            commit_sha=data.get("commit_sha"),
            user_id=data.get("user_id"),
            job_id=job.job_id,
            expected_scanners=data.get("expected_scanners"),
            coverage_scope=data.get("coverage_scope"),
        )

    def _build_completion_summary(
        self, context: ScanContext, *, job_type: str, duration_seconds: float
    ) -> dict:
        expected = context.expected_scanners or list(context.scanner_results.keys())
        completed = [n for n, r in context.scanner_results.items() if r.success]
        failed = [n for n, r in context.scanner_results.items() if not r.success]
        missing = [n for n in expected if n not in context.scanner_results]
        return {
            "finding_count": len(context.findings),
            "critical_count": context.critical_count,
            "high_count": context.high_count,
            "scanners_run": list(context.scanner_results.keys()),
            "scanner_health": {
                "expected": expected,
                "completed": completed,
                "failed": failed,
                "missing": missing,
                "complete": not failed and not missing,
            },
            "seen_fingerprints": [
                f["canonical_fingerprint"] for f in context.findings if f.get("canonical_fingerprint")
            ],
            "scope": "diff" if job_type == "scan.repo.diff" else "full",
            "changed_files": context.changed_files or [],
            "duration_ms": int(duration_seconds * 1000),
            "duration_seconds": round(duration_seconds, 1),
            "artifact_uris": context.artifact_uris,
            "ai_annotated_count": context.ai_annotated_count,
            "ai_skipped_count": context.ai_skipped_count,
        }

    def _get_scanners_for_type(self, scan_type: str) -> list[str]:
        from app.scanners.registry import scanners_for_scan_type
        return scanners_for_scan_type(scan_type)

    async def _update_status(self, context: ScanContext, stage: str, metadata: dict | None = None) -> None:
        await self.queue.update_job_status(context.job_id, stage, metadata)

    async def _update_scan_status(
        self,
        context: ScanContext,
        status: str,
        error: str | None = None,
        summary: dict | None = None,
    ) -> None:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.patch(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/status",
                    json={"status": status, "error_message": error, "summary_json": summary},
                    headers={"X-Worker-Credential": self._worker_credential},
                    timeout=30.0,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                _log.error(
                    "failed to update scan status",
                    extra={
                        "scan_id": context.scan_id,
                        "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                    },
                )
            except Exception as exc:
                _log.error(
                    "failed to update scan status",
                    extra={"scan_id": context.scan_id, "error": str(exc)},
                )
