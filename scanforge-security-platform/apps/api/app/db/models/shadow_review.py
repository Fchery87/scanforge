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


SHADOW_LABELS = ("useful", "not_useful", "incorrect", "duplicate", "missing_context")


class ShadowReviewCandidateLabel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A reviewer's judgement of one shadow candidate (#50): evaluation data only.

    One current label per (candidate, reviewer); ``updated_at`` is when it was last set and
    every change is also written to the audit log. A label never suppresses, resolves or
    otherwise changes a candidate or any finding, and is never published.
    """

    __tablename__ = "shadow_review_candidate_labels"
    __table_args__ = (UniqueConstraint("candidate_id", "actor_user_id", name="uq_shadow_label_actor"),)

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("shadow_review_candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    label: Mapped[str] = mapped_column(String(32), nullable=False)


class ShadowCorpusEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One labelled shadow candidate retained for replay evaluation (#51).

    A reference record only: revision SHAs, ids, the fingerprint and the split. It never holds
    source, snippets, titles, paths or secrets, so the corpus is not source storage. ``split`` is
    ``assign_split(repository, pull request)`` fixed at creation and never recomputed, so a pull
    request cannot straddle tuning and holdout. Rows go with their organization / repository
    (foreign-key cascade) and with the retention sweep (``created_at`` + retention days).
    """

    __tablename__ = "shadow_corpus_entries"
    __table_args__ = (UniqueConstraint("label_id", name="uq_shadow_corpus_label"),)

    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[str] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("shadow_review_candidates.id", ondelete="CASCADE"), nullable=False
    )
    label_id: Mapped[str] = mapped_column(
        ForeignKey("shadow_review_candidate_labels.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    base_sha: Mapped[str | None] = mapped_column(String(64))
    merge_base_sha: Mapped[str | None] = mapped_column(String(64))
    split: Mapped[str] = mapped_column(String(16), nullable=False)
    split_policy: Mapped[str] = mapped_column(String(32), nullable=False)
