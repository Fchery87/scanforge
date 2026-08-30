import hmac
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.worker_identities import WorkerIdentityService


@dataclass(frozen=True)
class WorkerPrincipal:
    worker_id: UUID
    organization_id: UUID
    capabilities: frozenset[str]


async def require_service_auth(
    x_service_key: Annotated[
        str | None,
        Header(alias="X-Worker-Credential"),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> WorkerPrincipal:
    """Authenticate an organization-scoped dedicated worker credential."""
    if not settings.WORKER_CREDENTIAL_PEPPER:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker authentication is not configured",
        )
    identity = await WorkerIdentityService(db, settings.WORKER_CREDENTIAL_PEPPER).authenticate(
        x_service_key
    )
    if identity is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing worker credential",
        )
    return WorkerPrincipal(
        worker_id=UUID(str(identity.id)),
        organization_id=UUID(str(identity.organization_id)),
        capabilities=frozenset(identity.capabilities_json),
    )


async def require_scheduler_auth(
    x_scheduler_key: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.SCHEDULER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler authentication is not configured",
        )
    if not x_scheduler_key or not hmac.compare_digest(x_scheduler_key, settings.SCHEDULER_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing scheduler credential",
        )
