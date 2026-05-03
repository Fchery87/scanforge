import httpx
import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.redis_rate_limit import RedisRateLimitMiddleware


@pytest.mark.asyncio
async def test_rate_limit_middleware_falls_back_when_redis_is_unavailable(monkeypatch):
    middleware = RedisRateLimitMiddleware(
        app=lambda scope, receive, send: None,
        requests_per_minute=10,
        redis_url="https://unreachable.example",
        redis_token="token",
    )

    async def fail_check(key, limit):
        raise httpx.ConnectError("redis unavailable")

    monkeypatch.setattr(middleware.rate_limiter, "check", fail_check)

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("127.0.0.1", 1)})

    async def call_next(_request):
        return Response("ok")

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "10"
