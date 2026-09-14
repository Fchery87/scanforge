from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WebhookDelivery(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint("provider", "delivery_id", name="uq_webhook_provider_delivery"),
        # R10 replay safety: one delivery per identical business event content per
        # repository (canonical event digest), so replays cannot create duplicate scans.
        UniqueConstraint(
            "provider",
            "repository_id",
            "event_digest",
            name="uq_webhook_provider_repo_event_digest",
        ),
    )

    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # D6 replay convention: SHA-256 over the canonical JSON of scan-relevant event
    # identity. Identical replay returns the original business response.
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_id: Mapped[str | None] = mapped_column(ForeignKey("scans.id", ondelete="SET NULL"))
    # Original business response persisted at creation; replayed verbatim (D6).
    response_json: Mapped[dict | None] = mapped_column(JSONB)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[str | None] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
