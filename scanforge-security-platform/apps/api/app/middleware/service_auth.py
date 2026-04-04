import hmac

from fastapi import Header, HTTPException, status

from app.core.config import settings


async def require_service_auth(x_service_key: str | None = Header(None)):
    """Validate service-to-service API key for internal endpoints."""
    if not settings.INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API not configured",
        )
    if not x_service_key or not hmac.compare_digest(x_service_key, settings.INTERNAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service key",
        )
    return True
