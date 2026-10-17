from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScanArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scan_artifacts"
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    scanner_run_id: Mapped[str | None] = mapped_column(ForeignKey("scanner_runs.id", ondelete="SET NULL"))
    organization_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scanner_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    staging_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    storage_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    verification_state: Mapped[str] = mapped_column(String(32), nullable=False, default="staged")
    redaction_policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

