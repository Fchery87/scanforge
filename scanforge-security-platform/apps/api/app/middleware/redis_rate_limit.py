import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class RateLimitState:
    """In-memory state for rate limiting. Replace with Redis for multi-instance."""

    def __init__(self):
        self.store: dict[str, tuple[int, float]] = {}

    def check(self, key: str, limit: int, window: int = 60) -> tuple[bool, int]:
        now = time.time()
        if key not in self.store:
            self.store[key] = (1, now)
            return False, limit - 1

        count, window_start = self.store[key]
        if now - window_start >= window:
            self.store[key] = (1, now)
            return False, limit - 1

        if count >= limit:
            retry_after = int(window - (now - window_start))
            return True, retry_after

        self.store[key] = (count + 1, window_start)
        return False, limit - count - 1

    def cleanup(self, cutoff: float = 120) -> None:
        now = time.time()
        expired = [k for k, (_, ts) in self.store.items() if now - ts > cutoff]
        for k in expired:
            del self.store[k]


IN_MEMORY_STATE = RateLimitState()


def get_client_ip(request: Request, trusted_proxies: set[str] | None = None) -> str:
    """Extract client IP with trusted proxy validation."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Only trust first IP if request comes from a known proxy
        client_host = request.client.host if request.client else None
        if trusted_proxies and client_host in trusted_proxies:
            return forwarded.split(",")[0].strip()
        # Without trusted proxy config, ignore X-Forwarded-For
    return request.client.host if request.client else "unknown"


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 10,
        exclude_paths: list[str] | None = None,
        trusted_proxies: set[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.exclude_paths = set(exclude_paths or [])
        self.trusted_proxies = trusted_proxies

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/api/v1/health") or path in self.exclude_paths:
            return await call_next(request)

        key = get_client_ip(request, self.trusted_proxies)
        limited, remaining = IN_MEMORY_STATE.check(key, self.requests_per_minute)

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
