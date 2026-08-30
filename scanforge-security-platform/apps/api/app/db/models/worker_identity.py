from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkerIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "worker_identities"
    __table_args__ = (
        Index(
            "uq_worker_identities_active_org_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text("disabled_at IS NULL"),
        ),
    )

    organization_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    credential_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    capabilities_json: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
