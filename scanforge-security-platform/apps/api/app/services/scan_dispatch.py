from __future__ import annotations

import hashlib
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.queue import QueueClient
from app.contracts.queue import ScanJobType
from app.core.config import settings
from app.core.error_messages import GENERIC_QUEUE_ERROR
from app.db.enums import DispatchObligationStatus
from app.db.enums import ScanStatus as ScanStatusEnum
from app.db.models import Project, Repository, Scan, ScanDispatchObligation

logger = logging.getLogger(__name__)

DEFAULT_MAX_PENDING_PER_ORG = 25
DEFAULT_MAX_PENDING_MANUAL_PER_REPO = 10
DEFAULT_DISPATCH_LEASE_SECONDS = 30
DEFAULT_DISPATCH_MAX_ATTEMPTS = 5


class ScanCapacityExceededError(ValueError):
    """Raised before accepting manual work when pending obligations exceed capacity."""

    code = "scan_capacity_exceeded"


@dataclass(frozen=True)
class DispatchAttemptResult:
    obligation_id: str
    scan_id: str
    dispatched: bool
    status: str
    job_id: str | None = None
    error_message: str | None = None


def job_type_for_scan_type(scan_type: str) -> ScanJobType:
    mapping: dict[str, ScanJobType] = {
        "full": "scan.repo.full",
        "diff": "scan.repo.diff",
        "dependencies": "scan.dependencies",
        "secrets": "scan.secrets",
    }
    return mapping.get(scan_type, "scan.repo.full")


def compute_automatic_business_identity(
    *,
    organization_id: UUID | str,
    repository_id: UUID | str,
    trigger_type: str,
    scan_type: str,
    full_ref_name: str | None,
    branch_generation_number: int,
    commit_sha: str | None,
    contract_version: str = "2026-10-beta.v1",
    coverage_scope: str = "default_branch",
    expected_scanners: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Canonical SHA-256 identity for automatic triggers including immutable scope/coverage context."""
    identity = {
        "branch_generation_number": int(branch_generation_number),
        "commit_sha": str(commit_sha or "").strip().lower(),
        "contract_version": str(contract_version or "2026-10-beta.v1"),
        "coverage_scope": str(coverage_scope or "default_branch"),
        "expected_scanners": sorted(str(scanner) for scanner in (expected_scanners or [])),
        "full_ref_name": str(full_ref_name or ""),
        "organization_id": str(organization_id),
        "repository_id": str(repository_id),
        "scan_type": str(scan_type or "full"),
        "trigger_type": str(trigger_type),
    }
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ScanDispatchService:
    """Durable scan dispatch obligations, admission bounds, supersession, and leased retries."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        queue: QueueClient | None = None,
        max_pending_per_org: int = DEFAULT_MAX_PENDING_PER_ORG,
        max_pending_manual_per_repo: int = DEFAULT_MAX_PENDING_MANUAL_PER_REPO,
        lease_seconds: int = DEFAULT_DISPATCH_LEASE_SECONDS,
        max_attempts: int = DEFAULT_DISPATCH_MAX_ATTEMPTS,
        after_enqueue_before_ack: Callable[[ScanDispatchObligation], Awaitable[None] | None] | None = None,
    ):
        self.db = db
        self.queue = queue or QueueClient(
            redis_url=settings.UPSTASH_REDIS_REST_URL,
            redis_token=settings.UPSTASH_REDIS_REST_TOKEN,
        )
        self.max_pending_per_org = max_pending_per_org
        self.max_pending_manual_per_repo = max_pending_manual_per_repo
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts
        self.after_enqueue_before_ack = after_enqueue_before_ack

    async def enforce_manual_admission_capacity(
        self,
        *,
        organization_id: UUID | str,
        repository_id: UUID | str,
    ) -> None:
        active_statuses = (
            DispatchObligationStatus.AWAITING_DISPATCH.value,
            DispatchObligationStatus.LEASED.value,
            DispatchObligationStatus.DISPATCHED.value,
            DispatchObligationStatus.QUARANTINED.value,
        )
        org_pending_count = (
            await self.db.execute(
                select(func.count())
                .select_from(ScanDispatchObligation)
                .join(Scan, Scan.id == ScanDispatchObligation.scan_id)
                .where(
                    ScanDispatchObligation.organization_id == str(organization_id),
                    ScanDispatchObligation.status.in_(active_statuses),
                    Scan.status.in_((ScanStatusEnum.QUEUED, ScanStatusEnum.RUNNING)),
                )
            )
        ).scalar_one()
        if int(org_pending_count or 0) >= self.max_pending_per_org:
            raise ScanCapacityExceededError(
                f"Organization pending scan capacity ({self.max_pending_per_org}) exceeded; "
                "wait for queued obligations to dispatch or complete before requesting another manual scan."
            )

        repo_manual_pending_count = (
            await self.db.execute(
                select(func.count())
                .select_from(ScanDispatchObligation)
                .join(Scan, Scan.id == ScanDispatchObligation.scan_id)
                .where(
                    ScanDispatchObligation.repository_id == str(repository_id),
                    ScanDispatchObligation.trigger_type == "manual",
                    ScanDispatchObligation.status.in_(active_statuses),
                    Scan.status.in_((ScanStatusEnum.QUEUED, ScanStatusEnum.RUNNING)),
                )
            )
        ).scalar_one()
        if int(repo_manual_pending_count or 0) >= self.max_pending_manual_per_repo:
            raise ScanCapacityExceededError(
                f"Repository manual scan capacity ({self.max_pending_manual_per_repo}) exceeded; "
                "wait for queued manual scans to dispatch or complete before requesting another manual scan."
            )

    async def find_existing_manual_idempotent_scan(
        self,
        *,
        organization_id: UUID | str,
        repository_id: UUID | str,
        request_idempotency_key: str,
    ) -> tuple[Scan, ScanDispatchObligation] | None:
        obligation = (
            await self.db.execute(
                select(ScanDispatchObligation).where(
                    ScanDispatchObligation.organization_id == str(organization_id),
                    ScanDispatchObligation.repository_id == str(repository_id),
                    ScanDispatchObligation.request_idempotency_key == request_idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if obligation is None:
            return None
        scan = await self.db.get(Scan, obligation.scan_id)
        if scan is None:
            return None
        return scan, obligation

    async def find_existing_automatic_scan(
        self,
        *,
        repository_id: UUID | str,
        business_identity_key: str,
    ) -> tuple[Scan, ScanDispatchObligation] | None:
        obligation = (
            await self.db.execute(
                select(ScanDispatchObligation).where(
                    ScanDispatchObligation.repository_id == str(repository_id),
                    ScanDispatchObligation.business_identity_key == business_identity_key,
                )
            )
        ).scalar_one_or_none()
        if obligation is None:
            return None
        scan = await self.db.get(Scan, obligation.scan_id)
        if scan is None:
            return None
        return scan, obligation

    async def supersede_unstarted_automatic_work(
        self,
        *,
        new_scan: Scan,
        repository_id: UUID | str,
        full_ref_name: str,
        branch_generation_number: int,
        ancestry_status: str,
    ) -> list[Scan]:
        """Explicitly supersede unstarted automatic work in the same branch generation on descendant push."""
        if new_scan.trigger_type != "webhook" or ancestry_status != "verified_descendant":
            return []

        stmt = (
            select(Scan, ScanDispatchObligation)
            .join(ScanDispatchObligation, ScanDispatchObligation.scan_id == Scan.id)
            .where(
                Scan.repository_id == str(repository_id),
                Scan.id != str(new_scan.id),
                Scan.trigger_type == "webhook",
                Scan.full_ref_name == full_ref_name,
                Scan.branch_generation_number == int(branch_generation_number),
                Scan.status == ScanStatusEnum.QUEUED,
                Scan.current_attempt_id.is_(None),
                Scan.deleted_at.is_(None),
                ScanDispatchObligation.status.in_(
                    (
                        DispatchObligationStatus.AWAITING_DISPATCH.value,
                        DispatchObligationStatus.LEASED.value,
                    )
                ),
            )
            .order_by(Scan.created_at.asc())
        )
        rows = (await self.db.execute(stmt)).all()
        superseded: list[Scan] = []
        reason = (
            f"Superseded before execution by verified descendant commit {new_scan.commit_sha} "
            f"in generation {branch_generation_number}"
        )
        for older_scan, older_obligation in rows:
            if older_scan.commit_sha == new_scan.commit_sha:
                continue
            skipped_scanners = list(older_scan.expected_scanners_json or [])
            older_scan.status = ScanStatusEnum.CANCELED
            older_scan.dispatch_state = DispatchObligationStatus.SUPERSEDED.value
            older_scan.superseded_by_scan_id = str(new_scan.id)
            older_scan.supersession_reason = reason
            older_scan.coverage_completeness = "skipped_superseded"
            older_scan.closure_eligible = False
            existing_summary = dict(older_scan.summary_json or {})
            existing_summary.update(
                {
                    "superseded": True,
                    "superseded_by_scan_id": str(new_scan.id),
                    "superseded_by_commit_sha": new_scan.commit_sha,
                    "supersession_reason": reason,
                    "skipped_scanners": skipped_scanners,
                    "fabricated_observations": False,
                }
            )
            older_scan.summary_json = existing_summary

            older_obligation.status = DispatchObligationStatus.SUPERSEDED.value
            older_obligation.superseded_by_scan_id = str(new_scan.id)
            older_obligation.supersession_reason = reason
            older_obligation.lease_owner = None
            older_obligation.lease_expires_at = None
            superseded.append(older_scan)

        return superseded

    async def create_obligation_for_scan(
        self,
        *,
        scan: Scan,
        repo: Repository,
        project: Project,
        business_identity_key: str | None = None,
        request_idempotency_key: str | None = None,
        webhook_delivery_id: str | None = None,
        now: datetime | None = None,
    ) -> ScanDispatchObligation:
        current_now = _as_utc(now) or datetime.now(UTC)
        job_type = job_type_for_scan_type(scan.scan_type)
        obligation = ScanDispatchObligation(
            id=str(uuid4()),
            organization_id=str(project.organization_id),
            project_id=str(project.id),
            repository_id=str(repo.id),
            scan_id=str(scan.id),
            trigger_type=scan.trigger_type,
            scan_type=scan.scan_type,
            job_type=job_type,
            business_identity_key=business_identity_key,
            request_idempotency_key=request_idempotency_key,
            full_ref_name=scan.full_ref_name,
            branch_generation_number=int(scan.branch_generation_number or 1),
            commit_sha=scan.commit_sha,
            status=DispatchObligationStatus.AWAITING_DISPATCH.value,
            queue_job_id=str(scan.id),
            attempt_count=0,
            max_attempts=self.max_attempts,
            next_attempt_at=current_now,
            webhook_delivery_id=webhook_delivery_id,
            payload_json={"scan_id": str(scan.id)},
        )
        scan.dispatch_state = DispatchObligationStatus.AWAITING_DISPATCH.value
        self.db.add(obligation)
        return obligation

    async def cancel_obligation_for_scan(self, scan_id: UUID | str, *, reason: str | None = None) -> None:
        obligation = (
            await self.db.execute(
                select(ScanDispatchObligation).where(ScanDispatchObligation.scan_id == str(scan_id))
            )
        ).scalar_one_or_none()
        if obligation is None:
            return
        if obligation.status in (
            DispatchObligationStatus.AWAITING_DISPATCH.value,
            DispatchObligationStatus.LEASED.value,
        ):
            obligation.status = DispatchObligationStatus.CANCELED.value
            obligation.lease_owner = None
            obligation.lease_expires_at = None
            if reason:
                obligation.last_error = reason

    async def claim_due_obligations(
        self,
        *,
        lease_owner: str,
        limit: int = 10,
        lease_seconds: int | None = None,
        scan_id: UUID | str | None = None,
        organization_id: UUID | str | None = None,
        now: datetime | None = None,
    ) -> list[ScanDispatchObligation]:
        current_now = _as_utc(now) or datetime.now(UTC)
        ttl_seconds = lease_seconds if lease_seconds is not None else self.lease_seconds

        conditions: list[Any] = [
            or_(
                ScanDispatchObligation.status == DispatchObligationStatus.AWAITING_DISPATCH.value,
                (
                    (ScanDispatchObligation.status == DispatchObligationStatus.LEASED.value)
                    & (ScanDispatchObligation.lease_expires_at <= current_now)
                ),
            ),
            ScanDispatchObligation.next_attempt_at <= current_now,
        ]
        if scan_id is not None:
            conditions.append(ScanDispatchObligation.scan_id == str(scan_id))
        if organization_id is not None:
            conditions.append(ScanDispatchObligation.organization_id == str(organization_id))

        stmt = (
            select(ScanDispatchObligation)
            .where(*conditions)
            .order_by(ScanDispatchObligation.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        candidates = list((await self.db.execute(stmt)).scalars().all())
        claimed: list[ScanDispatchObligation] = []

        for obligation in candidates:
            scan = await self.db.get(Scan, obligation.scan_id)
            if scan is None or scan.deleted_at is not None:
                obligation.status = DispatchObligationStatus.CANCELED.value
                obligation.lease_owner = None
                obligation.lease_expires_at = None
                continue
            if scan.superseded_by_scan_id is not None:
                obligation.status = DispatchObligationStatus.SUPERSEDED.value
                obligation.superseded_by_scan_id = str(scan.superseded_by_scan_id)
                obligation.supersession_reason = scan.supersession_reason
                obligation.lease_owner = None
                obligation.lease_expires_at = None
                scan.dispatch_state = DispatchObligationStatus.SUPERSEDED.value
                continue
            if scan.status in (
                ScanStatusEnum.CANCELED,
                ScanStatusEnum.COMPLETED,
                ScanStatusEnum.FAILED,
            ):
                obligation.status = (
                    DispatchObligationStatus.CANCELED.value
                    if scan.status == ScanStatusEnum.CANCELED
                    else DispatchObligationStatus.DISPATCHED.value
                )
                obligation.lease_owner = None
                obligation.lease_expires_at = None
                continue

            obligation.status = DispatchObligationStatus.LEASED.value
            obligation.lease_owner = lease_owner
            obligation.lease_expires_at = current_now + timedelta(seconds=ttl_seconds)
            obligation.attempt_count = int(obligation.attempt_count or 0) + 1
            scan.dispatch_state = DispatchObligationStatus.LEASED.value
            claimed.append(obligation)

        await self.db.commit()
        for obligation in claimed:
            await self.db.refresh(obligation)
        return claimed

    async def dispatch_claimed_obligation(
        self,
        obligation_id: UUID | str,
        *,
        lease_owner: str,
        now: datetime | None = None,
    ) -> DispatchAttemptResult:
        current_now = _as_utc(now) or datetime.now(UTC)
        obligation = await self.db.get(ScanDispatchObligation, str(obligation_id))
        if obligation is None:
            return DispatchAttemptResult(
                obligation_id=str(obligation_id),
                scan_id="",
                dispatched=False,
                status="missing",
            )
        if obligation.status != DispatchObligationStatus.LEASED.value or obligation.lease_owner != lease_owner:
            return DispatchAttemptResult(
                obligation_id=str(obligation.id),
                scan_id=str(obligation.scan_id),
                dispatched=False,
                status=obligation.status,
            )

        scan = await self.db.get(Scan, obligation.scan_id)
        if scan is None or scan.deleted_at is not None or scan.status != ScanStatusEnum.QUEUED:
            obligation.status = (
                DispatchObligationStatus.SUPERSEDED.value
                if (scan is not None and scan.superseded_by_scan_id)
                else DispatchObligationStatus.CANCELED.value
            )
            obligation.lease_owner = None
            obligation.lease_expires_at = None
            if scan is not None:
                scan.dispatch_state = obligation.status
            await self.db.commit()
            return DispatchAttemptResult(
                obligation_id=str(obligation.id),
                scan_id=str(obligation.scan_id),
                dispatched=False,
                status=obligation.status,
            )

        payload = dict(obligation.payload_json or {"scan_id": str(obligation.scan_id)})
        payload.setdefault("scan_id", str(obligation.scan_id))

        try:
            job_id = await self._invoke_queue_enqueue(
                job_type=obligation.job_type,  # type: ignore[arg-type]
                payload=payload,
                organization_id=obligation.organization_id,
                job_id=obligation.queue_job_id,
            )
        except Exception:
            logger.error("Failed to dispatch obligation %s for scan %s", obligation.id, obligation.scan_id, exc_info=True)
            locked_obligation = (
                await self.db.execute(
                    select(ScanDispatchObligation)
                    .where(ScanDispatchObligation.id == str(obligation.id))
                    .with_for_update()
                )
            ).scalar_one_or_none() or obligation
            locked_scan = (
                await self.db.execute(
                    select(Scan).where(Scan.id == str(obligation.scan_id)).with_for_update()
                )
            ).scalar_one_or_none() or scan

            if locked_obligation.status == DispatchObligationStatus.SUPERSEDED.value or (
                locked_scan is not None and locked_scan.superseded_by_scan_id is not None
            ):
                await self.db.commit()
                return DispatchAttemptResult(
                    obligation_id=str(locked_obligation.id),
                    scan_id=str(locked_obligation.scan_id),
                    dispatched=False,
                    status=DispatchObligationStatus.SUPERSEDED.value,
                )

            if int(locked_obligation.attempt_count or 0) >= int(locked_obligation.max_attempts or self.max_attempts):
                locked_obligation.status = DispatchObligationStatus.QUARANTINED.value
            else:
                locked_obligation.status = DispatchObligationStatus.AWAITING_DISPATCH.value
                delay_seconds = min(2 ** max(int(locked_obligation.attempt_count or 1) - 1, 0), 60)
                locked_obligation.next_attempt_at = current_now + timedelta(seconds=delay_seconds)

            locked_obligation.lease_owner = None
            locked_obligation.lease_expires_at = None
            locked_obligation.last_error = GENERIC_QUEUE_ERROR

            if locked_scan is not None:
                locked_scan.status = ScanStatusEnum.QUEUED
                locked_scan.dispatch_state = locked_obligation.status
                locked_scan.error_message = GENERIC_QUEUE_ERROR

            await self.db.commit()
            if locked_scan is not None:
                await self.db.refresh(locked_scan)
            await self.db.refresh(locked_obligation)
            return DispatchAttemptResult(
                obligation_id=str(locked_obligation.id),
                scan_id=str(locked_obligation.scan_id),
                dispatched=False,
                status=locked_obligation.status,
                error_message=GENERIC_QUEUE_ERROR,
            )

        if self.after_enqueue_before_ack is not None:
            maybe_awaitable = self.after_enqueue_before_ack(obligation)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

        locked_obligation = (
            await self.db.execute(
                select(ScanDispatchObligation)
                .where(ScanDispatchObligation.id == str(obligation.id))
                .with_for_update()
            )
        ).scalar_one_or_none() or obligation
        locked_scan = (
            await self.db.execute(
                select(Scan).where(Scan.id == str(obligation.scan_id)).with_for_update()
            )
        ).scalar_one_or_none() or scan

        if locked_obligation.status == DispatchObligationStatus.SUPERSEDED.value or (
            locked_scan is not None and locked_scan.superseded_by_scan_id is not None
        ):
            locked_obligation.status = DispatchObligationStatus.SUPERSEDED.value
            locked_obligation.lease_owner = None
            locked_obligation.lease_expires_at = None
            if locked_scan is not None:
                locked_scan.dispatch_state = DispatchObligationStatus.SUPERSEDED.value
            await self.db.commit()
            return DispatchAttemptResult(
                obligation_id=str(locked_obligation.id),
                scan_id=str(locked_obligation.scan_id),
                dispatched=False,
                status=DispatchObligationStatus.SUPERSEDED.value,
                job_id=job_id,
            )

        if locked_scan is not None and locked_scan.status == ScanStatusEnum.CANCELED:
            locked_obligation.status = DispatchObligationStatus.CANCELED.value
            locked_obligation.lease_owner = None
            locked_obligation.lease_expires_at = None
            locked_scan.dispatch_state = DispatchObligationStatus.CANCELED.value
            await self.db.commit()
            return DispatchAttemptResult(
                obligation_id=str(locked_obligation.id),
                scan_id=str(locked_obligation.scan_id),
                dispatched=False,
                status=DispatchObligationStatus.CANCELED.value,
                job_id=job_id,
            )

        locked_obligation.status = DispatchObligationStatus.DISPATCHED.value
        locked_obligation.dispatched_at = current_now
        locked_obligation.lease_owner = None
        locked_obligation.lease_expires_at = None
        locked_obligation.last_error = None

        if locked_scan is not None:
            locked_scan.dispatch_state = DispatchObligationStatus.DISPATCHED.value
            locked_scan.error_message = None

        await self.db.commit()
        if locked_scan is not None:
            await self.db.refresh(locked_scan)
        await self.db.refresh(locked_obligation)
        return DispatchAttemptResult(
            obligation_id=str(locked_obligation.id),
            scan_id=str(locked_obligation.scan_id),
            dispatched=True,
            status=DispatchObligationStatus.DISPATCHED.value,
            job_id=job_id,
        )

    async def dispatch_due_obligations(
        self,
        *,
        lease_owner: str = "api-dispatcher",
        limit: int = 10,
        lease_seconds: int | None = None,
        scan_id: UUID | str | None = None,
        organization_id: UUID | str | None = None,
        now: datetime | None = None,
    ) -> list[DispatchAttemptResult]:
        claimed = await self.claim_due_obligations(
            lease_owner=lease_owner,
            limit=limit,
            lease_seconds=lease_seconds,
            scan_id=scan_id,
            organization_id=organization_id,
            now=now,
        )
        results: list[DispatchAttemptResult] = []
        for obligation in claimed:
            res = await self.dispatch_claimed_obligation(
                obligation.id,
                lease_owner=lease_owner,
                now=now,
            )
            results.append(res)
        return results

    async def dispatch_for_scan(
        self,
        scan_id: UUID | str,
        *,
        lease_owner: str = "api-immediate-dispatcher",
        now: datetime | None = None,
    ) -> DispatchAttemptResult | None:
        results = await self.dispatch_due_obligations(
            lease_owner=lease_owner,
            limit=1,
            scan_id=scan_id,
            now=now,
        )
        return results[0] if results else None

    async def _invoke_queue_enqueue(
        self,
        *,
        job_type: ScanJobType,
        payload: dict,
        organization_id: UUID | str,
        job_id: str,
    ) -> str:
        enqueue_fn = self.queue.enqueue
        try:
            sig = inspect.signature(enqueue_fn)
            supports_job_id = "job_id" in sig.parameters
        except (TypeError, ValueError):
            supports_job_id = False

        if supports_job_id:
            return await enqueue_fn(
                job_type,
                payload,
                organization_id=organization_id,
                job_id=job_id,
            )
        return await enqueue_fn(
            job_type,
            payload,
            organization_id=organization_id,
        )


__all__ = [
    "DEFAULT_DISPATCH_LEASE_SECONDS",
    "DEFAULT_DISPATCH_MAX_ATTEMPTS",
    "DEFAULT_MAX_PENDING_MANUAL_PER_REPO",
    "DEFAULT_MAX_PENDING_PER_ORG",
    "DispatchAttemptResult",
    "ScanCapacityExceededError",
    "ScanDispatchService",
    "compute_automatic_business_identity",
    "job_type_for_scan_type",
]
