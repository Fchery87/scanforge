import os

import httpx

from app.core.logging import get_logger

_log = get_logger(__name__)


async def send_slack_alert(message: str, *, title: str = "ScanForge Alert") -> None:
    """Post a best-effort alert to the configured Slack webhook."""
    webhook_url = os.environ.get("SLACK_ALERT_WEBHOOK_URL", "")
    if not webhook_url:
        return

    payload = {"text": f"*{title}*\n{message}"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(webhook_url, json=payload, timeout=5.0)
            resp.raise_for_status()
    except Exception as exc:
        _log.warning("slack alert delivery failed", extra={"error": str(exc)})
