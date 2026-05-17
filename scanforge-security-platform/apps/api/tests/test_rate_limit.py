import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.middleware.redis_rate_limit import RateLimitState, UpstashRateLimiter, per_route_limiter


def test_rate_limit_state_initialization():
    state = RateLimitState()
    assert state.store == {}


def test_rate_limit_allows_under_limit():
    state = RateLimitState()
    limited, remaining = state.check("1.2.3.4", limit=60)
    assert limited is False
    assert remaining == 59


def test_rate_limit_blocks_over_limit():
    state = RateLimitState()
    for _ in range(60):
        state.check("1.2.3.4", limit=60)
    limited, remaining = state.check("1.2.3.4", limit=60)
    assert limited is True
    assert remaining >= 0


def test_rate_limit_different_ips():
    state = RateLimitState()
    for _ in range(60):
        state.check("1.2.3.4", limit=60)
    # Different IP should not be limited
    limited, remaining = state.check("5.6.7.8", limit=60)
    assert limited is False
    assert remaining == 59


@pytest.mark.asyncio
async def test_upstash_rate_limiter_sets_expiry_on_first_hit(monkeypatch):
    limiter = UpstashRateLimiter("https://redis.example", "token")
    calls = []

    async def fake_command(*args):
        calls.append(args)
        if args[0] == "INCR":
            return {"result": 1}
        if args[0] == "EXPIRE":
            return {"result": 1}
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(limiter, "_command", fake_command)

    limited, remaining = await limiter.check("1.2.3.4", limit=60)

    assert limited is False
    assert remaining == 59
    assert calls == [
        ("INCR", "rate-limit:1.2.3.4"),
        ("EXPIRE", "rate-limit:1.2.3.4", 60),
    ]


@pytest.mark.asyncio
async def test_upstash_rate_limiter_blocks_when_over_limit(monkeypatch):
    limiter = UpstashRateLimiter("https://redis.example", "token")

    async def fake_command(*args):
        if args[0] == "INCR":
            return {"result": 61}
        if args[0] == "TTL":
            return {"result": 12}
        raise AssertionError(f"Unexpected command: {args}")

    monkeypatch.setattr(limiter, "_command", fake_command)

    limited, remaining = await limiter.check("1.2.3.4", limit=60)

    assert limited is True
    assert remaining == 12


@pytest.mark.asyncio
async def test_per_route_limiter_allows_under_limit(monkeypatch):
    monkeypatch.setattr("app.middleware.redis_rate_limit._ROUTE_LIMITER.enabled", False)
    dep = per_route_limiter(limit=3, window=60, key_prefix="test:allow")
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("10.0.0.51", 1)})
    # Three calls within limit should not raise
    for _ in range(3):
        await dep(request)


@pytest.mark.asyncio
async def test_per_route_limiter_blocks_over_limit(monkeypatch):
    monkeypatch.setattr("app.middleware.redis_rate_limit._ROUTE_LIMITER.enabled", False)
    dep = per_route_limiter(limit=3, window=60, key_prefix="test:block")
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("10.0.0.52", 1)})
    for _ in range(3):
        await dep(request)
    with pytest.raises(HTTPException) as exc_info:
        await dep(request)
    assert exc_info.value.status_code == 429
    assert "Retry-After" in (exc_info.value.headers or {})
