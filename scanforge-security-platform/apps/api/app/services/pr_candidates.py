"""Shadow review candidates reconciled across pushes (#49, plan P2.3).

A candidate is a private, PR-scoped record keyed by fingerprint identity: one row per
(repository, pull request, fingerprint) no matter how many pushes, force-pushes, rebases or
webhook redeliveries observe it. Everything is derived server-side from committed per-scan
evidence (``summary_json.result_index`` and scanner runs); nothing is stored on findings and
nothing is published to GitHub.

States:
- active: observed by the analysis of the PR's current head;
- superseded: a newer head is recorded and has not been analyzed yet (transient);
- resolved: absent at the current head under comparable analysis (same analyzer identity and
  fingerprint policy as when last observed) with complete capability coverage;
- outdated: absent at the current head but without that evidence. Never a verified fix.

Only ``resolved`` candidates carry a ``resolution_basis`` and only they are returned by
``remediation_evidence``. Out-of-order guard: the newest head per PR is recorded with the
provider's event timestamp, and a late event for an older head is refused before it can
supersede or displace the newer head's run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.enums import ScanStatus
from app.db.models import Scan, ScannerRun, ShadowPullRequestHead, ShadowReviewCandidate
from app.services.evidence_contract import capability_for_scanner, derive_capability_coverage
from app.services.finding_lifecycle import analyzer_comparability
from app.services.pr_classification import _signature, baseline_ref_name

if TYPE_CHECKING:
    from collections.abc import Iterable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.canonical_findings import CanonicalFindingCandidate

ACTIVE = "active"
SUPERSEDED = "superseded"
OUTDATED = "outdated"
RESOLVED = "resolved"
COMPARABLE_ABSENCE = "comparable_absence"
_OPEN_STATES = (ACTIVE, SUPERSEDED)


class StalePullRequestHead(Exception):
    """A delivery for an older head arrived after a newer head was recorded."""

    def __init__(self, *, recorded_head_sha: str, recorded_observed_at: datetime):
        super().__init__("stale_pull_request_head")
        self.recorded_head_sha = recorded_head_sha
        self.recorded_observed_at = recorded_observed_at


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def build_result_locations(findings: Iterable[CanonicalFindingCandidate]) -> dict[str, dict[str, Any]]:
    """Fingerprint -> {path, line_start}, recorded on the scan summary at ingest."""
    locations: dict[str, dict[str, Any]] = {}
    for finding in findings:
        instance = finding.instance
        if instance is not None and (instance.path or instance.line_start is not None):
            locations[finding.canonical_fingerprint] = {"path": instance.path, "line_start": instance.line_start}
    return locations


class ShadowCandidateService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _head_row(self, repository_id: str, pull_request_number: int) -> ShadowPullRequestHead | None:
        return (
            await self.db.execute(
                select(ShadowPullRequestHead)
                .where(
                    ShadowPullRequestHead.repository_id == str(repository_id),
                    ShadowPullRequestHead.pull_request_number == int(pull_request_number),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def record_head(
        self, *, repository_id: str, pull_request_number: int, head_sha: str, observed_at: datetime
    ) -> None:
        """Record the newest PR head, or refuse an event for an older one.

        ``observed_at`` is the provider's timestamp for the event. Equal timestamps are not
        treated as older. When the head changes, the PR's open candidates become superseded
        until the new head is analyzed.
        """
        repository_id = str(repository_id)
        observed_at = _utc(observed_at)
        row = await self._head_row(repository_id, pull_request_number)
        if row is None:
            row = ShadowPullRequestHead(
                repository_id=repository_id,
                pull_request_number=int(pull_request_number),
                head_sha=head_sha,
                head_observed_at=observed_at,
            )
            try:
                async with self.db.begin_nested():
                    self.db.add(row)
                    await self.db.flush()
            except IntegrityError:
                row = await self._head_row(repository_id, pull_request_number)
                if row is None:
                    raise
            else:
                return
        recorded_at = _utc(row.head_observed_at)
        if observed_at < recorded_at:
            raise StalePullRequestHead(recorded_head_sha=row.head_sha, recorded_observed_at=recorded_at)
        row.head_observed_at = observed_at
        if row.head_sha != head_sha:
            row.head_sha = head_sha
            await self.db.execute(
                update(ShadowReviewCandidate)
                .where(
                    ShadowReviewCandidate.repository_id == repository_id,
                    ShadowReviewCandidate.pull_request_number == int(pull_request_number),
                    ShadowReviewCandidate.state == ACTIVE,
                    ShadowReviewCandidate.head_sha != head_sha,
                )
                .values(state=SUPERSEDED)
            )
        await self.db.flush()

    async def reconcile(self, scan: Scan) -> None:
        """Fold a completed shadow head run into the PR's candidates. Idempotent."""
        summary = scan.summary_json or {}
        index = summary.get("result_index")
        number = getattr(scan, "pull_request_number", None)
        if (
            getattr(scan, "trigger_type", None) != "pull_request"
            or number is None
            or scan.full_ref_name == baseline_ref_name(number)
            or scan.status != ScanStatus.COMPLETED
            or not isinstance(index, dict)
        ):
            return
        repository_id = str(scan.repository_id)
        number = int(number)
        head_row = await self._head_row(repository_id, number)
        if head_row is not None and head_row.head_sha != scan.commit_sha:
            return  # Not the PR's current head: never let an obsolete run rewrite candidates.

        locations = summary.get("result_locations") if isinstance(summary.get("result_locations"), dict) else {}
        existing = {
            row.fingerprint: row
            for row in (
                await self.db.execute(
                    select(ShadowReviewCandidate).where(
                        ShadowReviewCandidate.repository_id == repository_id,
                        ShadowReviewCandidate.pull_request_number == number,
                    )
                )
            ).scalars()
        }

        for fingerprint, scanner in index.items():
            location = locations.get(fingerprint) or {}
            candidate = existing.get(fingerprint)
            if candidate is None:
                self.db.add(
                    ShadowReviewCandidate(
                        repository_id=repository_id,
                        pull_request_number=number,
                        fingerprint=fingerprint,
                        scanner=scanner,
                        state=ACTIVE,
                        head_sha=scan.commit_sha,
                        first_scan_id=str(scan.id),
                        last_scan_id=str(scan.id),
                        path=location.get("path"),
                        line_start=location.get("line_start"),
                    )
                )
                continue
            candidate.state = ACTIVE
            candidate.resolution_basis = None
            candidate.scanner = scanner
            candidate.head_sha = scan.commit_sha
            candidate.last_scan_id = str(scan.id)
            if location:
                candidate.path = location.get("path")
                candidate.line_start = location.get("line_start")

        absent = [row for fp, row in existing.items() if fp not in index and row.state in _OPEN_STATES]
        if absent:
            current_runs = await self._runs(scan.id)
            policy = summary.get("fingerprint_policy")
            coverage = {
                item["capability"]: item["state"]
                for item in derive_capability_coverage(
                    list(current_runs.values()), expected_scanners=scan.expected_scanners_json
                )
            }
            for candidate in absent:
                comparable = await self._comparable_absence(candidate, current_runs, policy, coverage)
                candidate.state = RESOLVED if comparable else OUTDATED
                candidate.resolution_basis = COMPARABLE_ABSENCE if comparable else None
                candidate.head_sha = scan.commit_sha
        await self.db.flush()

    async def remediation_evidence(self, repository_id: str, pull_request_number: int) -> list[ShadowReviewCandidate]:
        """Candidates that may count as remediation evidence: resolved with a comparable basis only."""
        return list(
            (
                await self.db.execute(
                    select(ShadowReviewCandidate)
                    .where(
                        ShadowReviewCandidate.repository_id == str(repository_id),
                        ShadowReviewCandidate.pull_request_number == int(pull_request_number),
                        ShadowReviewCandidate.state == RESOLVED,
                        ShadowReviewCandidate.resolution_basis == COMPARABLE_ABSENCE,
                    )
                    .order_by(ShadowReviewCandidate.fingerprint)
                )
            ).scalars()
        )

    async def _runs(self, scan_id: str) -> dict[str, ScannerRun]:
        rows = (await self.db.execute(select(ScannerRun).where(ScannerRun.scan_id == str(scan_id)))).scalars()
        return {run.scanner_name.strip().lower(): run for run in rows}

    async def _comparable_absence(
        self,
        candidate: ShadowReviewCandidate,
        current_runs: dict[str, ScannerRun],
        current_policy: str | None,
        coverage: dict[str, str],
    ) -> bool:
        capability = capability_for_scanner(candidate.scanner)
        previous = await self.db.get(Scan, candidate.last_scan_id)
        if capability is None or candidate.scanner is None or previous is None:
            return False
        previous_policy = (previous.summary_json or {}).get("fingerprint_policy")
        if current_policy is None or current_policy != previous_policy:
            return False
        previous_runs = await self._runs(previous.id)
        block = analyzer_comparability(
            _signature(previous_runs.get(candidate.scanner), previous_policy),
            _signature(current_runs.get(candidate.scanner), current_policy),
        )
        return block is None and coverage.get(capability) in {"complete", "not_applicable"}
