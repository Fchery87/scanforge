import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.middleware import redis_rate_limit as limits
from app.middleware.rate_limit import RateLimitMiddleware


def request(peer, forwarded):
    return Request({
        "type": "http", "method": "GET", "path": "/resource",
        "headers": [(b"x-forwarded-for", forwarded.encode())], "client": (peer, 1),
    })


@pytest.mark.parametrize(("peer", "forwarded", "expected"), [
    ("10.0.0.1", "198.51.100.1", "198.51.100.1"),
    ("203.0.113.1", "198.51.100.1", "203.0.113.1"),
    ("10.0.0.1", "192.0.2.99, 198.51.100.1", "198.51.100.1"),
    ("10.0.0.1", "198.51.100.1, 10.0.0.2", "198.51.100.1"),
    ("10.0.0.1", "not-an-ip", "10.0.0.1"),
    ("10.0.0.1", "", "10.0.0.1"),
])
def test_client_identity_requires_a_trusted_proxy_chain(peer, forwarded, expected):
    assert limits.get_client_ip(request(peer, forwarded), {"10.0.0.1", "10.0.0.2"}) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["global", "route"])
@pytest.mark.parametrize("trusted", [True, False])
async def test_limiters_separate_clients_only_behind_trusted_proxy(monkeypatch, kind, trusted):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "10.0.0.1" if trusted else "")
    monkeypatch.setattr(limits, "LOCAL_STATE", limits.RateLimitState())
    monkeypatch.setattr(limits._ROUTE_LIMITER, "enabled", False)
    first = request("10.0.0.1", "198.51.100.1")
    second = request("10.0.0.1", "198.51.100.2")
    if kind == "global":
        middleware = limits.RedisRateLimitMiddleware(
            app=lambda _scope, _receive, _send: None, requests_per_minute=1,
            trusted_proxies=settings.trusted_proxy_ips_set,
        )

        async def next_response(_request):
            return Response("ok")

        assert (await middleware.dispatch(first, next_response)).status_code == 200
        assert (await middleware.dispatch(second, next_response)).status_code == (200 if trusted else 429)
        assert (await middleware.dispatch(first, next_response)).status_code == 429
    else:
        dependency = limits.per_route_limiter(limit=1)
        await dependency(first)
        if trusted:
            await dependency(second)
        else:
            with pytest.raises(HTTPException, match="429"):
                await dependency(second)
        with pytest.raises(HTTPException, match="429"):
            await dependency(first)


def test_legacy_limiter_does_not_trust_unsolicited_forwarded_headers(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "")
    middleware = RateLimitMiddleware(app=lambda _scope, _receive, _send: None)
    assert middleware._get_key(request("203.0.113.1", "198.51.100.1")) == "203.0.113.1"
