import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.worker_identities import WorkerIdentityService, WorkerPrincipal


async def require_scheduler_auth(
    x_scheduler_key: Annotated[str | None, Header()] = None,
) -> None:
    """Authenticate the trusted shared scheduler separately from customer workers."""
    expected = settings.SCHEDULER_API_KEY
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler auth not configured")
    if not x_scheduler_key or not hmac.compare_digest(x_scheduler_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing scheduler credential")


async def require_service_auth(
    x_worker_credential: Annotated[str | None, Header()] = None,
) -> WorkerPrincipal:
    """Authenticate organization-scoped worker credentials."""
    if not settings.WORKER_CREDENTIAL_PEPPER:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Worker auth not configured")
    async with AsyncSessionLocal() as db:
        principal = await WorkerIdentityService(db).authenticate(x_worker_credential)
    if not principal:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing worker credential")
    return principal
