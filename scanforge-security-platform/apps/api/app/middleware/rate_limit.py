import time
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

IN_MEMORY_STORE: dict[str, tuple[int, float]] = {}
IN_MEMORY_CLEANUP_INTERVAL = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 10,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.exclude_paths = set(exclude_paths or [])
        self._last_cleanup = time.time()

    def _get_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return ip

    def _cleanup(self) -> None:
        now = time.time()
        if now - self._last_cleanup < IN_MEMORY_CLEANUP_INTERVAL:
            return
        cutoff = now - 60
        keys_to_delete = [
            k for k, (_, ts) in IN_MEMORY_STORE.items() if ts < cutoff
        ]
        for k in keys_to_delete:
            del IN_MEMORY_STORE[k]
        self._last_cleanup = now

    def _is_rate_limited(self, key: str) -> tuple[bool, int]:
        now = time.time()
        self._cleanup()

        if key not in IN_MEMORY_STORE:
            IN_MEMORY_STORE[key] = (1, now)
            return False, self.requests_per_minute - 1

        count, window_start = IN_MEMORY_STORE[key]
        window_elapsed = now - window_start

        if window_elapsed >= 60:
            IN_MEMORY_STORE[key] = (1, now)
            return False, self.requests_per_minute - 1

        if count >= self.requests_per_minute:
            retry_after = int(60 - window_elapsed)
            return True, retry_after

        IN_MEMORY_STORE[key] = (count + 1, window_start)
        return False, self.requests_per_minute - count - 1

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)

        if request.url.path in self.exclude_paths:
            return await call_next(request)

        if request.url.path.startswith("/api/v1/webhooks/"):
            return await call_next(request)

        key = self._get_key(request)
        limited, remaining = self._is_rate_limited(key)

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
