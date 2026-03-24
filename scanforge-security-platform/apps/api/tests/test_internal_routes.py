import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
