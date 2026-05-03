from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("repository_id", "canonical_fingerprint", name="uq_finding_repo_fingerprint"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default="open")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    canonical_fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_scanner: Mapped[str | None] = mapped_column(String(50))
    confidence_score: Mapped[float | None] = mapped_column(Float)
    risk_score: Mapped[int | None]
    fixed_version: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    assignee_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    due_date: Mapped[date | None] = mapped_column(Date)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    instances: Mapped[list["FindingInstance"]] = relationship("FindingInstance", back_populates="finding", lazy="selectin")
    references: Mapped[list["FindingReference"]] = relationship("FindingReference", back_populates="finding", lazy="selectin")
    events: Mapped[list["FindingEvent"]] = relationship("FindingEvent", back_populates="finding", lazy="selectin")
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_user_id], lazy="selectin")

    @property
    def assignee_name(self) -> str | None:
        assignee = self.__dict__.get("assignee")
        return assignee.name if assignee else None

    @property
    def assignee_email(self) -> str | None:
        assignee = self.__dict__.get("assignee")
        return assignee.email if assignee else None

    @property
    def sla_status(self) -> dict:
        from app.services.sla_policy import preview_sla_status

        return preview_sla_status(workflow_state=self.status, due_date=self.due_date)

    @property
    def remediation_guidance(self) -> dict:
        from app.services.remediation_guidance import build_remediation_guidance

        return build_remediation_guidance(self)

class FindingInstance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "finding_instances"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    scanner_run_id: Mapped[str | None] = mapped_column(ForeignKey("scanner_runs.id", ondelete="SET NULL"))
    path: Mapped[str | None] = mapped_column(String(2048))
    line_start: Mapped[int | None]
    line_end: Mapped[int | None]
    package_name: Mapped[str | None] = mapped_column(String(255), index=True)
    installed_version: Mapped[str | None] = mapped_column(String(128))
    fixed_version: Mapped[str | None] = mapped_column(String(128))
    evidence_json: Mapped[dict | None] = mapped_column(JSONB)
    finding: Mapped["Finding"] = relationship("Finding", back_populates="instances", lazy="noload")

class FindingReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "finding_references"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_value: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    finding: Mapped["Finding"] = relationship("Finding", back_populates="references", lazy="noload")

class FindingEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "finding_events"
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    finding: Mapped["Finding"] = relationship("Finding", back_populates="events", lazy="noload")
