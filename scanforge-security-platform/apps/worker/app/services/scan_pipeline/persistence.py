from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.core.logging import get_logger
from app.services.scan_pipeline.context import ScanContext

if TYPE_CHECKING:
    from app.services.notifications import NotificationDispatcher

_log = get_logger(__name__)


class PersistenceStage:
    def __init__(self, api_base_url: str, internal_api_key: str) -> None:
        self.api_base_url = api_base_url
        self.internal_api_key = internal_api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-Service-Key": self.internal_api_key}

    async def persist_findings(self, context: ScanContext) -> None:
        if not context.findings:
            return
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.api_base_url}/api/v1/internal/scans/{context.scan_id}/findings",
                    json={"findings": context.findings},
                    headers=self._headers,
                    timeout=60.0,
                )
                resp.raise_for_status()
                data = resp.json()
                _log.info(
                    "findings persisted",
                    extra={"scan_id": context.scan_id, "count": data.get("count", len(context.findings))},
                )
            except httpx.HTTPStatusError as exc:
                _log.error(
                    "failed to persist findings",
                    extra={
                        "scan_id": context.scan_id,
                        "error": f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                    },
                )
            except Exception as exc:
                _log.error(
                    "failed to persist findings",
                    extra={"scan_id": context.scan_id, "error": str(exc)},
                )

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
