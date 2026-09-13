"""Scan execution lease: issue, renew, and reclaim visibility (R09).

R03 policy: the API is the only issuer, renewer, revoker, and replacer of
execution authority.  Candidate operational defaults are a 120-second lease
with renewal every 30 seconds (R03 decision D1 -- tunable, not yet proven).
Reclaim visibility must distinguish a dead worker (lease held and expired)
from an idle claim (no lease ever granted).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.db.models.scan import Scan

logger = logging.getLogger(__name__)

# R03 D1 candidate defaults; measuring them against real infrastructure is
# exactly what this unit exists to make observable.
LEASE_SECONDS = 120
RENEWAL_SECONDS = 30

RECLAIM_FRESH = "fresh_start"
RECLAIM_EXPIRED = "expired_lease_reclaim"


class LeaseConflict(Exception):
    """Raised when lease authority cannot be granted or renewed."""

    def __init__(self, reason: str, *, current_owner: str | None = None, remaining_seconds: float | None = None):
        super().__init__(reason)
        self.reason = reason
        self.current_owner = current_owner
        self.remaining_seconds = remaining_seconds


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    """Normalize stored timestamps to aware UTC (SQLite returns naive values)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class ScanLeaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _locked_scan(self, scan_id: str) -> Scan:
        result = await self.db.execute(select(Scan).where(Scan.id == scan_id).with_for_update())
        return result.scalar_one()

    async def acquire(
        self,
        scan_id: str,
        *,
        terminal_statuses: frozenset,
        worker_owner: str,
    ) -> tuple[Scan, str]:
        """Grant execution authority for a non-terminal scan.

        Returns ``(scan, reclaim_reason)`` where the reason distinguishes a
        dead worker's expired lease from an idle first claim.  A live lease
        held by another claimant is rejected: the new claimant keeps pending
        recovery state and must not start scanners or acknowledge.
        """
        scan = await self._locked_scan(scan_id)
        now = _utcnow()

        if scan.status in terminal_statuses:
            return scan, RECLAIM_FRESH

        previous_owner = scan.lease_owner
        lease_expires_at = _aware(scan.lease_expires_at)
        lease_valid = (
            lease_expires_at is not None and lease_expires_at > now and scan.current_attempt_id is not None
        )
        if lease_valid:
            if previous_owner == worker_owner:
                # The live owner refetching its context keeps its identity:
                # authority is idempotent, never re-minted.
                return scan, "active_lease_returned"
            remaining = (lease_expires_at - now).total_seconds()
            logger.info(
                "scan.lease.acquire_rejected",
                extra={
                    "scan_id": scan_id,
                    "current_owner": previous_owner,
                    "requesting_owner": worker_owner,
                    "remaining_seconds": remaining,
                },
            )
            raise LeaseConflict(
                "lease_active",
                current_owner=previous_owner,
                remaining_seconds=remaining,
            )

        reclaim_reason = RECLAIM_EXPIRED if previous_owner else RECLAIM_FRESH
        scan.current_attempt_id = str(uuid4())
        scan.execution_revision = (scan.execution_revision or 0) + 1
        scan.lease_owner = worker_owner
        scan.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        scan.last_heartbeat_at = now
        await self.db.commit()
        await self.db.refresh(scan)

        if reclaim_reason == RECLAIM_EXPIRED:
            # Dead-worker visibility: the previous holder never renewed past
            # its deadline.  An idle claim (no previous owner) is logged only
            # at debug so alerts can key on expired_lease_reclaim alone.
            logger.warning(
                "scan.lease.reclaimed",
                extra={
                    "scan_id": scan_id,
                    "reason": "lease_expired",
                    "previous_owner": previous_owner,
                    "new_owner": worker_owner,
                    "new_attempt_id": scan.current_attempt_id,
                    "execution_revision": scan.execution_revision,
                },
            )
        else:
            logger.debug(
                "scan.lease.acquired",
                extra={"scan_id": scan_id, "owner": worker_owner, "attempt_id": scan.current_attempt_id},
            )
        return scan, reclaim_reason

    async def renew(
        self,
        scan_id: str,
        *,
        attempt_id: str | None,
        execution_revision: int | None,
        worker_owner: str,
    ) -> Scan:
        """Renew a live lease.  An expired lease cannot be renewed (R03)."""
        scan = await self._locked_scan(scan_id)
        now = _utcnow()

        if (
            scan.current_attempt_id is None
            or attempt_id is None
            or scan.current_attempt_id != str(attempt_id)
            or (scan.execution_revision or 0) != (execution_revision or -1)
        ):
            logger.warning(
                "scan.lease.heartbeat_rejected",
                extra={
                    "scan_id": scan_id,
                    "reason": "stale_attempt",
                    "owner": worker_owner,
                    "presented_attempt_id": str(attempt_id) if attempt_id else None,
                    "presented_revision": execution_revision,
                },
            )
            raise LeaseConflict("stale_attempt", current_owner=scan.lease_owner)

        lease_expires_at = _aware(scan.lease_expires_at)
        if lease_expires_at is not None and lease_expires_at <= now:
            logger.warning(
                "scan.lease.heartbeat_rejected",
                extra={
                    "scan_id": scan_id,
                    "reason": "lease_expired",
                    "owner": worker_owner,
                    "expired_at": lease_expires_at.isoformat(),
                },
            )
            raise LeaseConflict("lease_expired", current_owner=scan.lease_owner)

        scan.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
        scan.last_heartbeat_at = now
        await self.db.commit()
        await self.db.refresh(scan)
        logger.info(
            "scan.lease.renewed",
            extra={
                "scan_id": scan_id,
                "owner": worker_owner,
                "attempt_id": scan.current_attempt_id,
                "lease_expires_at": scan.lease_expires_at.isoformat(),
            },
        )
        return scan
