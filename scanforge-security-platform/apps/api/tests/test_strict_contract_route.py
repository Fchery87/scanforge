from __future__ import annotations

import httpx
import pytest
from fastapi import APIRouter, FastAPI

from app.api.v1.strict_contract_route import StrictCompletionRoute


@pytest.mark.asyncio
async def test_completion_route_rejects_duplicate_json_keys_before_validation():
    router = APIRouter(route_class=StrictCompletionRoute)

    @router.post("/scans/{scan_id}/complete")
    async def complete_scan(scan_id: str, body: dict):
        return {"scan_id": scan_id, "body": body}

    app = FastAPI()
    app.include_router(router)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/scans/scan-1/complete",
            content=b'{"summary_json":{"scanner_health":{"complete":false,"complete":true}}}',
            headers={"content-type": "application/json"},
        )

    assert response.status_code == 422
    assert "Duplicate JSON key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_completion_route_keeps_valid_json_body_for_fastapi_validation():
    router = APIRouter(route_class=StrictCompletionRoute)

    @router.post("/scans/{scan_id}/complete")
    async def complete_scan(scan_id: str, body: dict):
        return {"scan_id": scan_id, "body": body}

    app = FastAPI()
    app.include_router(router)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/scans/scan-1/complete", json={"findings": []})

    assert response.status_code == 200
    assert response.json() == {"scan_id": "scan-1", "body": {"findings": []}}
