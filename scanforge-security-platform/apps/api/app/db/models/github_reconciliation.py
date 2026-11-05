from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class GitHubReconciliationReceipt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One reconciliation run against GitHub's current state (#54).

    Stores provider-derived outcomes (heads, ancestry receipts, lifecycle state) and a
    redacted operational error. Never stores tokens, request headers or response bodies.
    """

    __tablename__ = "github_reconciliation_receipts"

    installation_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
