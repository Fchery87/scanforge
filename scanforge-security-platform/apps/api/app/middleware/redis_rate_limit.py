import time

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitState:
    """Local fallback state for development when Redis is unavailable."""

    def __init__(self):
        self.store: dict[str, tuple[int, float]] = {}

    def check(self, key: str, limit: int, window: int = 60) -> tuple[bool, int]:
        now = time.time()
        if key not in self.store:
            self.store[key] = (1, now)
            return False, limit - 1

        count, window_start = self.store[key]
        elapsed = now - window_start
        if elapsed >= window:
            self.store[key] = (1, now)
            return False, limit - 1

        if count >= limit:
            retry_after = max(1, int(window - elapsed))
            return True, retry_after

        self.store[key] = (count + 1, window_start)
        return False, limit - count - 1


class UpstashRateLimiter:
    PREFIX = "rate-limit"

    def __init__(self, redis_url: str, redis_token: str):
        self.redis_url = redis_url
        self.redis_token = redis_token
        self.enabled = bool(redis_url and redis_token)
        self._headers = {
            "Authorization": f"Bearer {redis_token}",
            "Content-Type": "application/json",
        }

    async def _command(self, *args: str | int) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.redis_url,
                headers=self._headers,
                json=list(args),
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()

    async def check(self, key: str, limit: int, window: int = 60) -> tuple[bool, int]:
        namespaced = f"{self.PREFIX}:{key}"
        count_result = await self._command("INCR", namespaced)
        count = int(count_result.get("result") or 0)

        if count == 1:
            await self._command("EXPIRE", namespaced, window)
            return False, limit - 1

        ttl_result = await self._command("TTL", namespaced)
        ttl = int(ttl_result.get("result") or 0)
        if ttl < 0:
            await self._command("EXPIRE", namespaced, window)
            ttl = window

        if count > limit:
            return True, max(1, ttl)

        return False, max(0, limit - count)


LOCAL_STATE = RateLimitState()


def get_client_ip(request: Request, trusted_proxies: set[str] | None = None) -> str:
    """Extract client IP with trusted proxy validation."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_host = request.client.host if request.client else None
        if trusted_proxies and client_host in trusted_proxies:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 10,
        exclude_paths: list[str] | None = None,
        trusted_proxies: set[str] | None = None,
        redis_url: str = "",
        redis_token: str = "",
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.exclude_paths = set(exclude_paths or [])
        self.trusted_proxies = trusted_proxies
        self.rate_limiter = UpstashRateLimiter(redis_url, redis_token)

    async def _check_limit(self, key: str) -> tuple[bool, int]:
        if self.rate_limiter.enabled:
            return await self.rate_limiter.check(key, self.requests_per_minute)
        return LOCAL_STATE.check(key, self.requests_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/api/v1/health") or path in self.exclude_paths:
            return await call_next(request)

        key = get_client_ip(request, self.trusted_proxies)
        limited, remaining = await self._check_limit(key)

        if limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": remaining,
                },
                headers={
                    "Retry-After": str(remaining),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + remaining),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        return response
