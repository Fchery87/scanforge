from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ShadowPullRequestHead(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Newest head ScanForge has recorded for one pull request (#49).

    ``head_observed_at`` is the provider's own timestamp for the event that carried the head
    (``pull_request.updated_at``), not receipt time, so a late delivery for an older head can
    be recognised and ignored.
    """

    __tablename__ = "shadow_pull_request_heads"
    __table_args__ = (UniqueConstraint("repository_id", "pull_request_number", name="uq_shadow_pr_head"),)

    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    head_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ShadowReviewCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Private review candidate for one pull request, keyed by fingerprint identity (#49).

    States: active (observed at the current head), superseded (a newer head is recorded and
    not yet analyzed), outdated (absent at the newest analyzed head without comparable
    evidence), resolved (absent under comparable analysis with complete coverage). Only
    ``resolved`` with a ``resolution_basis`` can ever be remediation evidence. Never published.
    """

    __tablename__ = "shadow_review_candidates"
    __table_args__ = (
        UniqueConstraint("repository_id", "pull_request_number", "fingerprint", name="uq_shadow_candidate_identity"),
    )

    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    scanner: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    first_scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    last_scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    path: Mapped[str | None] = mapped_column(String(1024))
    line_start: Mapped[int | None] = mapped_column(Integer)
    resolution_basis: Mapped[str | None] = mapped_column(String(32))
