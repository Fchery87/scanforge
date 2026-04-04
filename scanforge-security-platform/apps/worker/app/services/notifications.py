import httpx


class NotificationDispatcher:
    def __init__(self, api_base_url: str, internal_api_key: str = ""):
        self.api_base_url = api_base_url
        self.internal_api_key = internal_api_key

    async def send_scan_completed(
        self,
        user_id: str,
        scan_id: str,
        org_id: str,
        project_id: str,
        finding_count: int,
        critical_count: int,
        has_failures: bool,
    ) -> None:
        title = "Scan completed"
        if has_failures:
            title = f"Scan completed with {critical_count} critical findings"
        elif finding_count > 0:
            title = f"Scan found {finding_count} new findings"

        body = None
        if critical_count > 0:
            body = f"Critical issue detected: {critical_count} critical finding(s) need immediate attention."

        await self._create_notification(
            user_id=user_id,
            notification_type="scan_completed",
            title=title,
            body=body,
            link=self._scan_link(org_id, project_id, scan_id),
            target_type="scan",
            target_id=scan_id,
            metadata={
                "finding_count": finding_count,
                "critical_count": critical_count,
                "has_failures": has_failures,
            },
        )

    async def send_secret_found(
        self,
        user_id: str,
        scan_id: str,
        org_id: str,
        project_id: str,
        finding_title: str,
    ) -> None:
        await self._create_notification(
            user_id=user_id,
            notification_type="secret_found",
            title="Secret detected in repository",
            body=f"A secret exposure was detected: {finding_title}. This is a critical security risk.",
            link=self._scan_link(org_id, project_id, scan_id),
            target_type="scan",
            target_id=scan_id,
            metadata={"category": "secret"},
        )

    async def send_scan_failed(
        self,
        user_id: str,
        scan_id: str,
        org_id: str,
        project_id: str,
        error: str,
        retry_count: int,
    ) -> None:
        if retry_count >= 3:
            await self._create_notification(
                user_id=user_id,
                notification_type="scan_failed",
                title="Scan failed after multiple retries",
                body=f"Scan has failed and will not be retried automatically. Error: {error[:200]}",
                link=self._scan_link(org_id, project_id, scan_id),
                target_type="scan",
                target_id=scan_id,
                metadata={"retry_count": retry_count},
            )

    async def _create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str | None = None,
        link: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "title": title,
                    "body": body,
                    "link": link,
                    "metadata_json": metadata,
                }
                if target_type:
                    payload["target_type"] = target_type
                if target_id:
                    payload["target_id"] = target_id

                await client.post(
                    f"{self.api_base_url}/api/v1/internal/notifications",
                    json=payload,
                    headers={"X-Service-Key": self.internal_api_key},
                    timeout=15.0,
                )
        except Exception as e:
            print(f"[notifications] Failed to send notification: {e}")

    def _scan_link(self, org_id: str, project_id: str, scan_id: str) -> str:
        return f"/dashboard/{org_id}/projects/{project_id}/scans/{scan_id}"
