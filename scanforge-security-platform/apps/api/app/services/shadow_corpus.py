"""Replay evaluation corpus built from labelled shadow candidates (#51, plan P2.7).

Entries are references (see ``ShadowCorpusEntry``), created only from an existing reviewer
label inside the label's own tenant, never from unlabelled candidates and never across
tenants. The tuning / holdout split is a stable hash of repository + pull request, recorded on
the entry at creation. Retention is ``settings.SHADOW_CORPUS_RETENTION_DAYS`` from entry
creation: reads exclude expired entries immediately and ``expire_past_retention`` deletes them.
Nothing here publishes to GitHub or changes candidates, labels or findings.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.models import (
    Project,
    Repository,
    Scan,
    ShadowCorpusEntry,
    ShadowReviewCandidate,
    ShadowReviewCandidateLabel,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

SPLIT_POLICY = "sha256-repo-pr.v1"
HOLDOUT_PERCENT = 20


def assign_split(repository_id: str | UUID, pull_request_number: int) -> str:
    """Stable ``tuning`` / ``holdout`` assignment for a whole pull request (about 20% holdout)."""
    digest = hashlib.sha256(f"{SPLIT_POLICY}:{repository_id}:{pull_request_number}".encode()).digest()
    return "holdout" if int.from_bytes(digest[:8], "big") % 100 < HOLDOUT_PERCENT else "tuning"


class ShadowCorpusService:
    def __init__(self, db: AsyncSession, *, retention_days: int | None = None):
        self.db = db
        days = settings.SHADOW_CORPUS_RETENTION_DAYS if retention_days is None else retention_days
        self.retention = timedelta(days=days)

    async def record_label(self, organization_id: UUID | str, label_id: UUID | str) -> ShadowCorpusEntry:
        """Idempotently record the corpus entry for a label owned by ``organization_id``.

        Raises LookupError when the label, its candidate or its scan is not inside that tenant.
        An existing entry is returned untouched, so the recorded split never changes.
        """
        row = (
            await self.db.execute(
                select(ShadowReviewCandidateLabel, ShadowReviewCandidate, Scan)
                .join(ShadowReviewCandidate, ShadowReviewCandidate.id == ShadowReviewCandidateLabel.candidate_id)
                .join(Scan, Scan.id == ShadowReviewCandidate.last_scan_id)
                .join(Repository, Repository.id == ShadowReviewCandidate.repository_id)
                .join(Project, Project.id == Repository.project_id)
                .where(
                    ShadowReviewCandidateLabel.id == str(label_id),
                    ShadowReviewCandidateLabel.organization_id == str(organization_id),
                    Project.organization_id == str(organization_id),
                )
            )
        ).first()
        if row is None:
            raise LookupError("label is not part of this organization")
        label, candidate, scan = row
        existing = (
            await self.db.execute(select(ShadowCorpusEntry).where(ShadowCorpusEntry.label_id == str(label.id)))
        ).scalar_one_or_none()
        if existing is not None:
            return existing
        entry = ShadowCorpusEntry(
            organization_id=str(organization_id),
            repository_id=str(candidate.repository_id),
            pull_request_number=candidate.pull_request_number,
            scan_id=str(scan.id),
            candidate_id=str(candidate.id),
            label_id=str(label.id),
            fingerprint=candidate.fingerprint,
            # The referenced scan's own head: candidate.head_sha moves to later heads when the
            # candidate goes unobserved, but base / merge-base come from this scan (last_scan_id).
            head_sha=scan.commit_sha,
            base_sha=scan.base_sha,
            merge_base_sha=scan.merge_base_sha,
            split=assign_split(candidate.repository_id, candidate.pull_request_number),
            split_policy=SPLIT_POLICY,
        )
        self.db.add(entry)
        await self.db.flush()
        return entry

    async def entries(self, organization_id: UUID | str, split: str | None = None) -> list[ShadowCorpusEntry]:
        """This tenant's unexpired entries, optionally for one split."""
        query = select(ShadowCorpusEntry).where(
            ShadowCorpusEntry.organization_id == str(organization_id),
            ShadowCorpusEntry.created_at >= self._cutoff(),
        )
        if split is not None:
            query = query.where(ShadowCorpusEntry.split == split)
        return list((await self.db.execute(query.order_by(ShadowCorpusEntry.created_at))).scalars())

    async def expire_past_retention(self, now: datetime | None = None) -> int:
        """Delete entries older than the retention period (all tenants); returns the count."""
        result = await self.db.execute(
            delete(ShadowCorpusEntry).where(ShadowCorpusEntry.created_at < self._cutoff(now))
        )
        await self.db.commit()
        return result.rowcount or 0

    def _cutoff(self, now: datetime | None = None) -> datetime:
        return (now or datetime.now(UTC)) - self.retention
