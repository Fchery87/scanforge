from __future__ import annotations

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import ScanStatus
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Scan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scans"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scan_type: Mapped[str] = mapped_column(String(50), nullable=False, default="full")
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=ScanStatus.QUEUED,
    )
    branch_name: Mapped[str | None] = mapped_column(String(255))
    commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSONB)
    scanner_runs: Mapped[list[ScannerRun]] = relationship("ScannerRun", back_populates="scan", lazy="noload")

class ScannerRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scanner_runs"
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    scanner_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    scanner_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=ScanStatus.QUEUED,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    artifact_uri: Mapped[str | None] = mapped_column(String(2048))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    scan: Mapped[Scan] = relationship("Scan", back_populates="scanner_runs", lazy="noload")
