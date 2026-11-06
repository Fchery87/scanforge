"""New / existing / unknown classification of shadow PR results (#47, plan P2.1).

Where classification reads from: shadow findings are not stored as repository findings
(#46), so each completed scan carries its own evidence in ``summary_json`` (``result_index``:
fingerprint -> scanner, and ``fingerprint_policy``) plus its committed ``ScannerRun`` rows.
Classification compares the head run with a *baseline run*: a private shadow-style full scan
of the PR's merge-base commit that ScanForge schedules itself, so it executes under the same
pipeline (review pack included) as the head. It is derived on read from that committed
evidence; nothing is stored on findings and nothing is published to GitHub.

Rules, in order, per head result:
- no resolved merge-base, no baseline, or an unfinished baseline -> unknown (never clean);
- fingerprint policy differs between head and baseline -> unknown;
- fingerprint present in the baseline -> existing (positive observation at the merge-base);
- otherwise the claim "new" is an absence claim at the baseline, so it needs the baseline's
  analyzer to be comparable (P1.1 policy) and the baseline's capability coverage to be
  complete or analyzer-evidenced not applicable (#45); anything else -> unknown.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from app.db.enums import DispatchObligationStatus, ScanStatus
from app.db.models import Project, Repository, Scan, ScannerRun
from app.schemas.canonical_findings import (
    CATEGORY_FINGERPRINT_VERSIONS,
    CURRENT_FINGERPRINT_VERSION,
    SCANNER_FINGERPRINT_VERSIONS,
)
from app.services.evidence_contract import capability_for_scanner, derive_capability_coverage
from app.services.finding_lifecycle import analyzer_comparability, analyzer_signature
from app.services.scan_dispatch import ScanDispatchService, compute_automatic_business_identity

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.canonical_findings import CanonicalFindingCandidate

BASELINE_SCOPE = "pull_request_baseline"
_TERMINAL_UNUSABLE = (ScanStatus.FAILED, ScanStatus.CANCELED)
# Reasons for which a baseline scan under the head's analyzer identity may help.
_BASELINE_WORK_REASONS = frozenset(
    {
        "baseline_missing",
        "analyzer_not_comparable",
        "analyzer_baseline_unknown",
        "baseline_coverage_not_complete",
        "fingerprint_policy_not_comparable",
    }
)


def baseline_ref_name(pull_request_number: int) -> str:
    return f"refs/pull/{int(pull_request_number)}/base"


def fingerprint_policy_digest() -> str:
    """Digest of the fingerprint identity policy in force when a scan is ingested."""
    policy = {
        "default": CURRENT_FINGERPRINT_VERSION,
        "categories": CATEGORY_FINGERPRINT_VERSIONS,
        "scanners": SCANNER_FINGERPRINT_VERSIONS,
    }
    return hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()[:16]


def build_result_index(findings: Iterable[CanonicalFindingCandidate]) -> dict[str, str | None]:
    """Fingerprint -> producing scanner, recorded on the scan summary at ingest."""
    index: dict[str, str | None] = {}
    for finding in findings:
        scanner = (finding.primary_scanner or "").strip().lower() or None
        index[finding.canonical_fingerprint] = scanner
    return index


def carried_shadow_summary(previous: Mapping[str, object] | None) -> dict[str, object]:
    """Server-set summary keys that must survive the worker's completion summary."""
    digest = (previous or {}).get("baseline_analyzer_digest") if isinstance(previous, dict) else None
    return {"baseline_analyzer_digest": digest} if digest else {}


def _signature(run: ScannerRun | None, policy: str | None) -> dict[str, str | None] | None:
    if run is None:
        return None
    return analyzer_signature(
        scanner_name=run.scanner_name,
        scanner_version=run.scanner_version,
        parser_version=run.parser_version,
        rules_digest=run.rules_digest,
        fingerprint_version=policy,
    )


def _analyzer_digest(runs: Mapping[str, ScannerRun], policy: str | None) -> str:
    parts = {name: _signature(run, policy) for name, run in sorted(runs.items())}
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def _is_baseline_run(scan: Scan) -> bool:
    return bool(scan.full_ref_name) and scan.full_ref_name == baseline_ref_name(scan.pull_request_number or 0)


class ShadowClassificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _runs(self, scan_id: str) -> dict[str, ScannerRun]:
        rows = (await self.db.execute(select(ScannerRun).where(ScannerRun.scan_id == str(scan_id)))).scalars()
        return {run.scanner_name.strip().lower(): run for run in rows}

    async def _baseline_candidates(self, head: Scan) -> list[Scan]:
        return list(
            (
                await self.db.execute(
                    select(Scan)
                    .where(
                        Scan.repository_id == str(head.repository_id),
                        Scan.trigger_type == "pull_request",
                        Scan.pull_request_number == head.pull_request_number,
                        Scan.full_ref_name == baseline_ref_name(head.pull_request_number),
                        Scan.commit_sha == head.merge_base_sha,
                        Scan.deleted_at.is_(None),
                    )
                    .order_by(Scan.created_at.desc())
                )
            ).scalars()
        )

    @staticmethod
    def _usable(scan: Scan) -> bool:
        return scan.status == ScanStatus.COMPLETED and isinstance((scan.summary_json or {}).get("result_index"), dict)

    async def classify(self, head: Scan) -> dict[str, Any]:
        """Classify a completed shadow head run. Pure read; never schedules work."""
        result: dict[str, Any] = {
            "state": "unavailable",
            "merge_base_sha": head.merge_base_sha,
            "comparison_strategy": head.comparison_strategy,
            "baseline_scan_id": None,
            "counts": {"new": 0, "existing": 0, "unknown": 0},
            "results": [],
        }
        summary = head.summary_json or {}
        index = summary.get("result_index")
        if head.trigger_type != "pull_request" or head.status != ScanStatus.COMPLETED or not isinstance(index, dict):
            return result
        result["state"] = "classified"

        head_runs = await self._runs(head.id)
        head_policy = summary.get("fingerprint_policy")
        baseline, missing_reason = await self._select_baseline(head, head_runs, head_policy)
        base_runs: dict[str, ScannerRun] = {}
        base_index: dict[str, Any] = {}
        base_policy = None
        coverage: dict[str, str] = {}
        if baseline is not None:
            result["baseline_scan_id"] = str(baseline.id)
            base_runs = await self._runs(baseline.id)
            base_index = baseline.summary_json["result_index"]
            base_policy = (baseline.summary_json or {}).get("fingerprint_policy")
            coverage = {
                item["capability"]: item["state"]
                for item in derive_capability_coverage(
                    list(base_runs.values()), expected_scanners=baseline.expected_scanners_json
                )
            }

        for fingerprint, scanner in sorted(index.items()):
            capability = capability_for_scanner(scanner)
            if baseline is None:
                label, reason = "unknown", missing_reason
            elif head_policy is None or head_policy != base_policy:
                label, reason = "unknown", "fingerprint_policy_not_comparable"
            elif fingerprint in base_index:
                label, reason = "existing", "present_at_merge_base"
            else:
                label, reason = self._absence_claim(
                    scanner, capability, head_runs, base_runs, head_policy, base_policy, coverage
                )
            result["counts"][label] += 1
            result["results"].append(
                {
                    "fingerprint": fingerprint,
                    "scanner": scanner,
                    "capability": capability,
                    "classification": label,
                    "reason": reason,
                }
            )
        return result

    @staticmethod
    def _absence_claim(scanner, capability, head_runs, base_runs, head_policy, base_policy, coverage):
        if scanner is None or capability is None:
            return "unknown", "scanner_not_attributed"
        block = analyzer_comparability(
            _signature(base_runs.get(scanner), base_policy), _signature(head_runs.get(scanner), head_policy)
        )
        if block is not None:
            return "unknown", block.value
        if coverage.get(capability) not in {"complete", "not_applicable"}:
            return "unknown", "baseline_coverage_not_complete"
        return "new", "absent_at_comparable_baseline"

    async def _select_baseline(self, head: Scan, head_runs, head_policy) -> tuple[Scan | None, str]:
        if not head.merge_base_sha:
            return None, "merge_base_unresolved"
        candidates = await self._baseline_candidates(head)
        usable = [scan for scan in candidates if self._usable(scan)]
        if usable:
            wanted = _analyzer_digest(head_runs, head_policy)
            for scan in usable:
                if (scan.summary_json or {}).get("baseline_analyzer_digest") == wanted:
                    return scan, ""
            return usable[0], ""
        if any(scan.status not in _TERMINAL_UNUSABLE and scan.status != ScanStatus.COMPLETED for scan in candidates):
            return None, "baseline_pending"
        if candidates:
            return None, "baseline_failed"
        return None, "baseline_missing"

    async def schedule_baseline_work(self, head: Scan) -> Scan | None:
        """Request a baseline run of the merge-base when the head cannot be classified yet.

        Idempotent: the baseline's business identity is (PR, merge-base, head analyzer
        identity), so replays and repeated pushes never create a second one. Called from
        evidence ingress when a shadow head run completes.
        """
        if (
            getattr(head, "trigger_type", None) != "pull_request"
            or head.pull_request_number is None
            or not head.merge_base_sha
            or _is_baseline_run(head)
        ):
            return None
        classification = await self.classify(head)
        if not any(
            entry["classification"] == "unknown" and entry["reason"] in _BASELINE_WORK_REASONS
            for entry in classification["results"]
        ):
            return None

        head_runs = await self._runs(head.id)
        digest = _analyzer_digest(head_runs, (head.summary_json or {}).get("fingerprint_policy"))
        repo = await self.db.get(Repository, head.repository_id)
        project = await self.db.get(Project, head.project_id)
        if repo is None or project is None:
            return None

        dispatch = ScanDispatchService(self.db)
        expected = list(head.expected_scanners_json or [])
        ref = baseline_ref_name(head.pull_request_number)
        identity = compute_automatic_business_identity(
            organization_id=project.organization_id,
            repository_id=repo.id,
            trigger_type="pull_request",
            scan_type="full",
            full_ref_name=ref,
            branch_generation_number=1,
            commit_sha=head.merge_base_sha,
            coverage_scope=f"{BASELINE_SCOPE}:{digest}",
            expected_scanners=expected,
        )
        existing = await dispatch.find_existing_automatic_scan(repository_id=repo.id, business_identity_key=identity)
        if existing is not None:
            return existing[0]

        scan = Scan(
            id=str(uuid4()),
            project_id=head.project_id,
            repository_id=head.repository_id,
            trigger_type="pull_request",
            scan_type="full",
            status=ScanStatus.QUEUED,
            dispatch_state=DispatchObligationStatus.AWAITING_DISPATCH.value,
            branch_name=None,
            full_ref_name=ref,
            branch_generation_number=1,
            ancestry_status="unknown",
            commit_sha=head.merge_base_sha,
            pull_request_number=head.pull_request_number,
            requested_by_user_id=None,
            expected_scanners_json=expected,
            head_is_fork=False,
            summary_json={"coverage_scope": BASELINE_SCOPE, "baseline_analyzer_digest": digest},
        )
        self.db.add(scan)
        await self.db.flush()
        await dispatch.create_obligation_for_scan(
            scan=scan, repo=repo, project=project, business_identity_key=identity, request_idempotency_key=None
        )
        await self.db.flush()
        return scan
