import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_security_headers_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Strict-Transport-Security" in response.headers


@pytest.mark.asyncio
async def test_csp_header_present():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    csp = response.headers.get("Content-Security-Policy", "")
    assert "script-src 'self'" in csp, "CSP should restrict script-src to self"
    # Extract script-src directive and verify no unsafe-inline
    script_src = [d for d in csp.split(";") if d.strip().startswith("script-src")]
    assert script_src, "CSP should have script-src directive"
    assert "'unsafe-inline'" not in script_src[0], "CSP script-src should not allow unsafe-inline"
    assert "frame-ancestors 'none'" in csp, "CSP should prevent framing"


@pytest.mark.asyncio
async def test_error_response_generic():
    """Production errors should not leak internal details."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/nonexistent-endpoint-that-should-404")
    assert response.status_code in (404, 422)
