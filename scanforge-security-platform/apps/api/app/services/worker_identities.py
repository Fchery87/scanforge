import hashlib
import hmac
import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.worker_identity import WorkerIdentity


class WorkerIdentityService:
    def __init__(self, db: AsyncSession, pepper: str):
        self.db = db
        self.pepper = pepper

    def hash_credential(self, credential: str) -> str:
        return hmac.new(self.pepper.encode(), credential.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def generate_credential() -> str:
        return secrets.token_urlsafe(32)

    def create_identity(
        self,
        *,
        organization_id: UUID,
        name: str,
        capabilities: Iterable[str],
        credential: str | None = None,
    ) -> tuple[WorkerIdentity, str]:
        plaintext_credential = credential or self.generate_credential()
        identity = WorkerIdentity(
            id=uuid4(),
            organization_id=organization_id,
            name=name,
            credential_hash=self.hash_credential(plaintext_credential),
            capabilities_json=sorted(set(capabilities)),
        )
        self.db.add(identity)
        return identity, plaintext_credential

    async def authenticate(self, credential: str | None) -> WorkerIdentity | None:
        if not credential:
            return None

        credential_hash = self.hash_credential(credential)
        result = await self.db.execute(
            select(WorkerIdentity).where(WorkerIdentity.credential_hash == credential_hash)
        )
        identity = result.scalar_one_or_none()
        if identity is None or identity.disabled_at is not None:
            return None
        if not hmac.compare_digest(identity.credential_hash, credential_hash):
            return None
        identity.last_seen_at = datetime.now(UTC)
        await self.db.commit()
        return identity

    async def get_identity(self, worker_id: UUID) -> WorkerIdentity | None:
        return await self.db.get(WorkerIdentity, str(worker_id))

    async def disable_identity(self, worker_id: UUID) -> WorkerIdentity | None:
        identity = await self.get_identity(worker_id)
        if identity is None:
            return None
        if identity.disabled_at is None:
            identity.disabled_at = datetime.now(UTC)
            await self.db.commit()
        return identity

    async def rotate_identity(self, worker_id: UUID) -> tuple[WorkerIdentity, str]:
        identity = await self.get_identity(worker_id)
        if identity is None:
            raise ValueError("Worker identity was not found")
        if identity.disabled_at is not None:
            raise ValueError("Disabled worker identities cannot be rotated")

        identity.disabled_at = datetime.now(UTC)
        await self.db.flush()
        replacement, credential = self.create_identity(
            organization_id=identity.organization_id,
            name=identity.name,
            capabilities=identity.capabilities_json,
        )
        await self.db.commit()
        return replacement, credential
