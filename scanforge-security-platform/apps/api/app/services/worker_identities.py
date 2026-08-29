import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import WorkerIdentity


@dataclass(frozen=True)
class WorkerPrincipal:
    worker_id: UUID
    organization_id: UUID
    capabilities: frozenset[str]


def hash_worker_credential(credential: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), credential.encode(), hashlib.sha256).hexdigest()


def generate_worker_credential() -> str:
    return secrets.token_urlsafe(32)


class WorkerIdentityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        organization_id: UUID,
        name: str,
        capabilities: set[str],
    ) -> tuple[WorkerIdentity, str]:
        credential = generate_worker_credential()
        identity = WorkerIdentity(
            organization_id=str(organization_id),
            name=name,
            credential_hash=hash_worker_credential(credential, settings.WORKER_CREDENTIAL_PEPPER),
            capabilities_json=sorted(capabilities),
        )
        self.db.add(identity)
        await self.db.commit()
        await self.db.refresh(identity)
        return identity, credential

    async def rotate(self, worker_id: UUID) -> tuple[WorkerIdentity, str] | None:
        identity = await self.db.get(WorkerIdentity, worker_id)
        if not identity or identity.disabled_at is not None:
            return None
        credential = generate_worker_credential()
        identity.credential_hash = hash_worker_credential(credential, settings.WORKER_CREDENTIAL_PEPPER)
        await self.db.commit()
        await self.db.refresh(identity)
        return identity, credential

    async def disable(self, worker_id: UUID) -> bool:
        identity = await self.db.get(WorkerIdentity, worker_id)
        if not identity:
            return False
        identity.disabled_at = datetime.now(UTC)
        await self.db.commit()
        return True

    async def authenticate(self, credential: str | None) -> WorkerPrincipal | None:
        if not credential or not settings.WORKER_CREDENTIAL_PEPPER:
            return None
        digest = hash_worker_credential(credential, settings.WORKER_CREDENTIAL_PEPPER)
        result = await self.db.execute(
            select(WorkerIdentity).where(
                WorkerIdentity.credential_hash == digest,
                WorkerIdentity.disabled_at.is_(None),
            )
        )
        identity = result.scalar_one_or_none()
        if not identity:
            return None
        identity.last_seen_at = datetime.now(UTC)
        await self.db.commit()
        return WorkerPrincipal(
            worker_id=identity.id,
            organization_id=UUID(str(identity.organization_id)),
            capabilities=frozenset(identity.capabilities_json),
        )
