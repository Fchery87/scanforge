from unittest.mock import AsyncMock

import pytest

from app.worker import scheduler


@pytest.mark.asyncio
async def test_trigger_due_scan_schedules_calls_internal_api(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"found": 2, "queued": 1, "failed": 1}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, timeout):
            requests.append({"url": url, "headers": headers, "timeout": timeout})
            return Response()

    monkeypatch.setattr(scheduler.httpx, "AsyncClient", Client)

    result = await scheduler.trigger_due_scan_schedules(
        api_base_url="http://api.local/",
        internal_api_key="secret",
    )

    assert result == {"found": 2, "queued": 1, "failed": 1}
    assert requests == [
        {
            "url": "http://api.local/api/v1/internal/scan-schedules/run-due",
            "headers": {"X-Service-Key": "secret"},
            "timeout": 60.0,
        }
    ]


@pytest.mark.asyncio
async def test_run_scheduled_scans_uses_trigger_adapter(monkeypatch):
    trigger = AsyncMock(return_value={"found": 1, "queued": 1, "failed": 0})
    monkeypatch.setattr(scheduler, "trigger_due_scan_schedules", trigger)

    await scheduler.run_scheduled_scans()

    trigger.assert_awaited_once_with()
