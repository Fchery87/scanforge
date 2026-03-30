import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1.routes.internal import UpdateScannerRunRequest


@pytest.mark.asyncio
async def test_internal_notifications_rejected_without_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/internal/notifications",
            json={"user_id": "test", "notification_type": "info", "title": "Test", "body": "Test"},
        )
    # 503 if key not configured, 401 if configured but missing
    assert response.status_code in (401, 503)


@pytest.mark.asyncio
async def test_internal_notifications_rejected_with_wrong_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/internal/notifications",
            json={"user_id": "test", "notification_type": "info", "title": "Test", "body": "Test"},
            headers={"X-Service-Key": "wrong-key"},
        )
    # 503 if key not configured, 401 if configured but wrong
    assert response.status_code in (401, 503)


@pytest.mark.asyncio
async def test_internal_endpoints_require_service_auth():
    """All internal endpoints should reject requests without proper auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test various internal endpoints
        endpoints = [
            ("POST", "/api/v1/internal/notifications"),
            ("PATCH", "/api/v1/internal/scans/00000000-0000-0000-0000-000000000000/status"),
            ("GET", "/api/v1/internal/onboarding"),
        ]
        for method, path in endpoints:
            response = await client.request(method, path, json={})
            # Should be rejected (401 or 503)
            assert response.status_code in (401, 503), f"{method} {path} should reject unauthorized requests"


def test_update_scanner_run_request_allows_partial_artifact_updates():
    payload = UpdateScannerRunRequest.model_validate(
        {
            "artifact_uri": "https://artifacts.example/scans/123/output.json",
            "metadata_json": {"raw_output_uri": "https://artifacts.example/scans/123/raw.json"},
        }
    )

    assert payload.status is None
    assert payload.artifact_uri == "https://artifacts.example/scans/123/output.json"
