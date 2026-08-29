from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.core.logging import get_logger
from app.services.scan_pipeline.context import ScanContext

if TYPE_CHECKING:
    from app.services.notifications import NotificationDispatcher

_log = get_logger(__name__)


class PersistenceStage:
    def __init__(self, api_base_url: str, worker_credential: str) -> None:
        self.api_base_url = api_base_url
        self.worker_credential = worker_credential

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Worker-Credential": self.worker_credential}

    async def complete_scan(self, context: ScanContext) -> None:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/complete",
                json={
                    "findings": context.findings,
                    "scanner_runs": [
                        {
                            "scanner_name": name,
                            "scanner_version": result.version,
                            "status": "completed" if result.success else "failed",
                            "duration_ms": result.duration_ms,
                            "exit_code": result.exit_code,
                            "error_message": result.error,
                        }
                        for name, result in context.scanner_results.items()
                    ],
                    "summary_json": context.summary_json,
                    "artifact_uris": context.artifact_uris,
                },
                headers=self._headers,
                timeout=60.0,
            )
            response.raise_for_status()
    async def send_notifications(
        self,
        context: ScanContext,
        notifier: NotificationDispatcher | None,
    ) -> None:
        if not notifier or not context.user_id:
            return
        try:
            await notifier.send_scan_completed(
                user_id=context.user_id,
                scan_id=context.scan_id,
                org_id=context.organization_id,
                project_id=context.project_id,
                finding_count=len(context.findings),
                critical_count=context.critical_count,
                has_failures=context.scan_failed,
            )
            for finding in context.findings:
                if finding.get("category") == "secret":
                    await notifier.send_secret_found(
                        user_id=context.user_id,
                        scan_id=context.scan_id,
                        org_id=context.organization_id,
                        project_id=context.project_id,
                        finding_title=finding.get("title", "Unknown secret"),
                    )
                    break
        except Exception as exc:
            _log.warning(
                "failed to send scan notifications",
                extra={"scan_id": context.scan_id, "error": str(exc)},
            )

    async def send_failure_notification(
        self,
        context: ScanContext,
        notifier: NotificationDispatcher | None,
        retry_count: int,
    ) -> None:
        if not notifier or not context.user_id:
            return
        try:
            await notifier.send_scan_failed(
                user_id=context.user_id,
                scan_id=context.scan_id,
                org_id=context.organization_id,
                project_id=context.project_id,
                error=context.error_message or "Unknown error",
                retry_count=retry_count,
            )
        except Exception:
            pass
