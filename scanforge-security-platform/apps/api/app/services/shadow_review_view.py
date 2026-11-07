"""Internal shadow results view and reviewer labels (#50, plan P2.3).

The view is derived on read from committed evidence (scan, scanner runs, the #47
classification and the #49 candidates); nothing here is a new source of truth. Reviewer
labels are human evaluation data stored with actor and timestamp, written to the audit log,
and never touch candidate state, findings or remediation evidence. Nothing is published.

View state, in order: ``failed`` / ``pending`` for unfinished or unusable runs; ``partial``
whenever any limitation exists (coverage not complete, results unknown, no comparable
baseline, a newer head recorded); ``empty`` when the run finished with no results and no
limitation; ``ready`` otherwise. ``empty`` means "the analyzers reported nothing in their
declared scope", never "safe".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.enums import ScanStatus
from app.db.models import (
    Scan,
    ScannerRun,
    ShadowPullRequestHead,
    ShadowReviewCandidate,
    ShadowReviewCandidateLabel,
)
from app.services.audit_logs import AuditLogService
from app.services.evidence_contract import derive_capability_coverage
from app.services.pr_classification import ShadowClassificationService
from app.services.shadow_corpus import ShadowCorpusService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

LABEL_AUDIT_ACTION = "shadow_candidate.labeled"
_COST_UNAVAILABLE = "no cost measurement is recorded for shadow runs"


def _label_view(row: ShadowReviewCandidateLabel) -> dict[str, Any]:
    return {
        "candidate_id": row.candidate_id,
        "label": row.label,
        "actor_user_id": row.actor_user_id,
        "labeled_at": row.updated_at or row.created_at,
    }


def _duration(runs: list[ScannerRun]) -> dict[str, Any]:
    measured = [run.duration_ms for run in runs if run.duration_ms is not None]
    if not measured:
        return {"state": "unavailable", "total_ms": None}
    return {"state": "measured" if len(measured) == len(runs) else "partial", "total_ms": sum(measured)}


class ShadowReviewViewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def build(self, scan: Scan) -> dict[str, Any]:
        runs = list(
            (await self.db.execute(select(ScannerRun).where(ScannerRun.scan_id == str(scan.id)))).scalars()
        )
        summary = scan.summary_json or {}
        health = summary.get("scanner_health")
        expected = health.get("expected") if isinstance(health, dict) else None
        coverage = derive_capability_coverage(runs, expected_scanners=expected or scan.expected_scanners_json)
        classification = await ShadowClassificationService(self.db).classify(scan)

        status = getattr(scan.status, "value", scan.status)
        view: dict[str, Any] = {
            "state": "pending",
            "scan_id": scan.id,
            "scan_status": status,
            "revisions": {
                "pull_request_number": scan.pull_request_number,
                "base_sha": scan.base_sha,
                "head_sha": scan.commit_sha,
                "merge_base_sha": scan.merge_base_sha,
                "comparison_strategy": scan.comparison_strategy,
                "baseline_scan_id": classification["baseline_scan_id"],
                "head_is_fork": bool(scan.head_is_fork),
            },
            "capability_coverage": coverage,
            "classification_state": classification["state"],
            "classification_counts": classification["counts"],
            "results": [],
            "limitations": [],
            "duration": _duration(runs),
            "cost_estimate": {"state": "unavailable", "reason": _COST_UNAVAILABLE},
        }
        if status in (ScanStatus.FAILED.value, ScanStatus.CANCELED.value):
            view["state"] = "failed"
            return view
        if status != ScanStatus.COMPLETED.value or classification["state"] != "classified":
            return view

        view["results"] = await self._results(scan, classification)
        view["limitations"] = await self._limitations(scan, coverage, classification)
        if view["limitations"]:
            view["state"] = "partial"
        else:
            view["state"] = "ready" if view["results"] else "empty"
        return view

    async def _results(self, scan: Scan, classification: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = {
            row.fingerprint: row
            for row in (
                await self.db.execute(
                    select(ShadowReviewCandidate).where(
                        ShadowReviewCandidate.repository_id == str(scan.repository_id),
                        ShadowReviewCandidate.pull_request_number == scan.pull_request_number,
                    )
                )
            ).scalars()
        }
        labels: dict[str, list[ShadowReviewCandidateLabel]] = {}
        if candidates:
            rows = (
                await self.db.execute(
                    select(ShadowReviewCandidateLabel)
                    .where(ShadowReviewCandidateLabel.candidate_id.in_([str(c.id) for c in candidates.values()]))
                    .order_by(ShadowReviewCandidateLabel.created_at)
                )
            ).scalars()
            for row in rows:
                labels.setdefault(str(row.candidate_id), []).append(row)
        results = []
        for item in classification["results"]:
            candidate = candidates.get(item["fingerprint"])
            results.append(
                {
                    **item,
                    "candidate_id": candidate.id if candidate else None,
                    "candidate_state": candidate.state if candidate else None,
                    "path": candidate.path if candidate else None,
                    "line_start": candidate.line_start if candidate else None,
                    "labels": [_label_view(r) for r in labels.get(str(candidate.id), [])] if candidate else [],
                }
            )
        return results

    async def _limitations(
        self, scan: Scan, coverage: list[dict[str, Any]], classification: dict[str, Any]
    ) -> list[str]:
        limitations = []
        for item in coverage:
            if item["state"] in {"partial", "unknown"}:
                reasons = "; ".join(r.replace("_", " ") for r in item.get("reasons") or [])
                detail = f" ({reasons})" if reasons else ""
                limitations.append(f"{item['capability']}: coverage {item['state']}{detail}")
        unknown = [r for r in classification["results"] if r["classification"] == "unknown"]
        if unknown:
            reasons = sorted({r["reason"].replace("_", " ") for r in unknown})
            limitations.append(
                f"{len(unknown)} result(s) unknown, not clean: no comparable baseline ({', '.join(reasons)})"
            )
        head = (
            await self.db.execute(
                select(ShadowPullRequestHead).where(
                    ShadowPullRequestHead.repository_id == str(scan.repository_id),
                    ShadowPullRequestHead.pull_request_number == scan.pull_request_number,
                )
            )
        ).scalar_one_or_none()
        if head is not None and head.head_sha != scan.commit_sha:
            limitations.append("a newer head has been recorded for this pull request; this view is an older revision")
        return limitations

    async def _actor_label(self, candidate_id: UUID, actor_user_id: UUID) -> ShadowReviewCandidateLabel | None:
        return (
            await self.db.execute(
                select(ShadowReviewCandidateLabel)
                .where(
                    ShadowReviewCandidateLabel.candidate_id == str(candidate_id),
                    ShadowReviewCandidateLabel.actor_user_id == str(actor_user_id),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def set_label(
        self, *, org_id: UUID, scan: Scan, candidate_id: UUID, actor_user_id: UUID, label: str
    ) -> ShadowReviewCandidateLabel | None:
        """Upsert the actor's label for a candidate of this scan's PR. None if not addressable."""
        candidate = (
            await self.db.execute(
                select(ShadowReviewCandidate).where(
                    ShadowReviewCandidate.id == str(candidate_id),
                    ShadowReviewCandidate.repository_id == str(scan.repository_id),
                    ShadowReviewCandidate.pull_request_number == scan.pull_request_number,
                )
            )
        ).scalar_one_or_none()
        if candidate is None:
            return None
        row = await self._actor_label(candidate_id, actor_user_id)
        previous = row.label if row else None
        if row is None:
            row = ShadowReviewCandidateLabel(
                organization_id=str(org_id),
                candidate_id=str(candidate_id),
                actor_user_id=str(actor_user_id),
                label=label,
            )
            try:
                async with self.db.begin_nested():
                    self.db.add(row)
                    await self.db.flush()
            except IntegrityError:
                # A concurrent first label by the same actor won the unique (candidate, actor) row.
                row = await self._actor_label(candidate_id, actor_user_id)
                if row is None:
                    raise
                previous = row.label
                row.label = label
        else:
            row.label = label
        AuditLogService(self.db).record(
            actor_user_id,
            LABEL_AUDIT_ACTION,
            "shadow_review_candidate",
            candidate_id,
            organization_id=org_id,
            metadata_json={"label": label, "previous_label": previous, "scan_id": str(scan.id)},
        )
        await self.db.flush()
        await ShadowCorpusService(self.db).record_label(org_id, row.id)
        await self.db.commit()
        await self.db.refresh(row)
        return row
