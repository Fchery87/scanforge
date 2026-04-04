from pathlib import Path
from unittest.mock import AsyncMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.notifications import NotificationDispatcher


@pytest.mark.asyncio
async def test_notification_dispatcher_posts_to_internal_notifications_endpoint_with_service_key():
    dispatcher = NotificationDispatcher(
        api_base_url="http://api.example",
        internal_api_key="service-key",
    )

    response = AsyncMock()
    response.raise_for_status = AsyncMock()

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False

    with patch("app.services.notifications.httpx.AsyncClient", return_value=client):
        await dispatcher.send_scan_completed(
            user_id="user-1",
            scan_id="scan-1",
            org_id="org-1",
            project_id="project-1",
            finding_count=3,
            critical_count=1,
            has_failures=False,
        )

    client.post.assert_awaited_once()
    _, kwargs = client.post.await_args
    assert kwargs["headers"] == {"X-Service-Key": "service-key"}
    assert kwargs["json"]["notification_type"] == "scan_completed"
    assert kwargs["json"]["link"] == "/dashboard/org-1/projects/project-1/scans/scan-1"
    assert kwargs["json"]["target_type"] == "scan"
    assert kwargs["json"]["target_id"] == "scan-1"
    assert kwargs["timeout"] == 15.0

    called_url = client.post.await_args.args[0]
    assert called_url == "http://api.example/api/v1/internal/notifications"
