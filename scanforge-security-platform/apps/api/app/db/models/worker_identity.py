from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkerIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "worker_identities"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_worker_identity_org_name"),
    )

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    capabilities_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
