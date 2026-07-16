import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_messages import GENERIC_INTERNAL_ERROR
from app.middleware.audit import AuditMiddleware
from app.middleware.redis_rate_limit import RedisRateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="ScanForge API",
    version="0.1.0",
    description="Repository security scanning and vulnerability management platform",
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(
    RedisRateLimitMiddleware,
    requests_per_minute=120,
    burst=20,
    redis_url=settings.UPSTASH_REDIS_REST_URL,
    redis_token=settings.UPSTASH_REDIS_REST_TOKEN,
    trusted_proxies=settings.trusted_proxy_ips_set,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=600,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "status": "operational",
    }


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, _exc: Exception):
    logger.error("Unhandled exception", exc_info=True)
    error_detail = GENERIC_INTERNAL_ERROR

    # Include CORS headers in error response
    origin = _request.headers.get("origin")
    headers = {}
    if origin and origin in settings.cors_origins_list:
        headers["access-control-allow-origin"] = origin
        headers["access-control-allow-credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": error_detail},
        headers=headers,
    )
