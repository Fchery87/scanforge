from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.enums import DispatchObligationStatus
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScanDispatchObligation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scan_dispatch_obligations"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "business_identity_key",
            name="uq_dispatch_repo_business_identity",
        ),
        UniqueConstraint(
            "organization_id",
            "repository_id",
            "request_idempotency_key",
            name="uq_dispatch_org_repo_idempotency_key",
        ),
    )

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scan_id: Mapped[str] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scan_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full")
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default="scan.repo.full")
    business_identity_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    request_idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    full_ref_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch_generation_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DispatchObligationStatus.AWAITING_DISPATCH.value,
        index=True,
    )
    queue_job_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_scan_id: Mapped[str | None] = mapped_column(
        ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    supersession_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    webhook_delivery_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
