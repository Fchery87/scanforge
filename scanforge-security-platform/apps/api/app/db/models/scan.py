from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
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
    current_attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # R09 execution lease (candidate defaults from R03 D1: 120 s lease / 30 s renewal).
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
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


class ScanCompletionReceipt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "scan_completion_receipts"
    scan_id: Mapped[str] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    winning_attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    terminal_status: Mapped[str] = mapped_column(String(50), nullable=False)
    inserted_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanner_runs_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanner_runs_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_json: Mapped[dict | None] = mapped_column(JSONB)
