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
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False, default="2026-10-beta.v1")
    branch_name: Mapped[str | None] = mapped_column(String(255))
    full_ref_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    branch_generation_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ancestry_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    commit_sha: Mapped[str | None] = mapped_column(String(64), index=True)
    # R10 recorded base/head diff: base commit recorded alongside commit_sha when the
    # trigger event provides it (pull_request base.sha).
    base_sha: Mapped[str | None] = mapped_column(String(64))
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    requested_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    error_message: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict | None] = mapped_column(JSONB)
    expected_scanners_json: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    coverage_completeness: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    closure_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cleanup_state: Mapped[str] = mapped_column(String(32), nullable=False, default="not_required")
    dispatch_state: Mapped[str] = mapped_column(String(32), nullable=False, default="awaiting_dispatch")
    superseded_by_scan_id: Mapped[str | None] = mapped_column(
        ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    supersession_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_principal_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    worker_incarnation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
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
    attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome_status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rules_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    db_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    db_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    db_freshness_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unverified")
    image_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    artifact_availability: Mapped[str] = mapped_column(String(32), nullable=False, default="unavailable")
    closure_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False, default="2026-10-beta.v1")
    winning_attempt_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_principal_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    worker_incarnation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    terminal_status: Mapped[str] = mapped_column(String(50), nullable=False)
    coverage_completeness: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    closure_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    artifact_availability: Mapped[str] = mapped_column(String(32), nullable=False, default="unavailable")
    inserted_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanner_runs_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scanner_runs_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    response_json: Mapped[dict | None] = mapped_column(JSONB)

