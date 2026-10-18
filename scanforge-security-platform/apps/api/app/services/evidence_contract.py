"""Authoritative versioned execution and evidence contract (ADR-013, ADR-014, ADR-016, ADR-017).

The API derives coverage completeness, scanner run completion, finding counts,
lifecycle closure eligibility, and artifact availability from the immutable
execution contract and validated evidence. Worker-supplied summaries cannot
grant authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.canonical_findings import CanonicalFindingCandidate
    from app.schemas.scan_completion import ScanCompletionRequest, ScannerRunCompletion

CURRENT_EVIDENCE_CONTRACT_VERSION = "2026-10-beta.v1"
SUPPORTED_EVIDENCE_CONTRACT_VERSIONS: frozenset[str] = frozenset({CURRENT_EVIDENCE_CONTRACT_VERSION})

KNOWN_BETA_SCANNERS: frozenset[str] = frozenset(
    {
        "trivy",
        "gitleaks",
        "semgrep",
        "osv",
        "osv-scanner",
        "syft",
        "checkov",
        "grype",
    }
)
DATABASE_BACKED_SCANNERS: frozenset[str] = frozenset({"trivy", "grype", "osv", "osv-scanner"})
MAX_SCANNER_DB_AGE = timedelta(days=7)

# Candidate ingress bounds; final operating envelope requires M15 G1 measurement approval.
CANDIDATE_MAX_COMPLETION_PAYLOAD_BYTES = 16 * 1024 * 1024
CANDIDATE_MAX_FINDINGS_PER_SCAN = 10_000
CANDIDATE_MAX_SCANNER_RUNS_PER_SCAN = 16
CANDIDATE_MAX_REFERENCES_PER_FINDING = 64
MIN_ABBREVIATED_COMMIT_SHA_LENGTH = 7

FORBIDDEN_SUMMARY_AUTHORITY_KEYS: frozenset[str] = frozenset(
    {
        "authoritative",
        "closure_eligible",
        "coverage_completeness",
        "evidence_digest",
        "verified_by_server",
        "allow_auto_close",
        "organization_id",
        "project_id",
        "bypass_redaction",
        "finding_status_override",
    }
)


class EvidenceContractError(ValueError):
    """Base error for evidence contract violations."""

    code = "evidence_contract_error"


class UnsupportedContractVersionError(EvidenceContractError):
    code = "unsupported_contract_version"


class DuplicateJsonKeyError(EvidenceContractError):
    code = "duplicate_json_key"


class InvalidJsonNumberError(EvidenceContractError):
    code = "invalid_json_number"


class DuplicateScannerRunError(EvidenceContractError):
    code = "duplicate_scanner_run"


class UnknownScannerError(EvidenceContractError):
    code = "unknown_scanner"


class ForbiddenWorkerAuthorityError(EvidenceContractError):
    code = "forbidden_worker_authority"


class IngressBoundExceededError(EvidenceContractError):
    code = "ingress_bound_exceeded"


@dataclass(frozen=True)
class DerivedScanEvidenceDecision:
    contract_version: str
    coverage_completeness: str
    scanner_runs_complete: bool
    closure_eligible: bool
    artifact_availability: str
    expected_scanners: tuple[str, ...]
    completed_scanners: tuple[str, ...]
    failed_scanners: tuple[str, ...]
    missing_scanners: tuple[str, ...]
    ineligibility_reasons: tuple[str, ...] = field(default_factory=tuple)
    severity_counts: dict[str, int] = field(default_factory=dict)


def negotiate_contract_version(
    version: str | None,
    *,
    require_explicit: bool = False,
) -> str:
    if not version:
        if require_explicit:
            raise UnsupportedContractVersionError("Missing required evidence contract_version")
        return CURRENT_EVIDENCE_CONTRACT_VERSION
    if version not in SUPPORTED_EVIDENCE_CONTRACT_VERSIONS:
        raise UnsupportedContractVersionError(
            f"Unsupported evidence contract_version '{version}'; supported: "
            f"{sorted(SUPPORTED_EVIDENCE_CONTRACT_VERSIONS)}"
        )
    return version


def _reject_duplicate_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateJsonKeyError(f"Duplicate JSON key '{key}' is forbidden by the evidence contract")
        obj[key] = value
    return obj


def _reject_non_finite_constant(constant: str) -> Any:
    raise InvalidJsonNumberError(f"Non-finite JSON number '{constant}' is forbidden by the evidence contract")


def parse_strict_contract_json(
    raw_json: str | bytes,
    *,
    max_bytes: int = CANDIDATE_MAX_COMPLETION_PAYLOAD_BYTES,
) -> Any:
    raw_bytes = raw_json.encode("utf-8") if isinstance(raw_json, str) else raw_json
    if len(raw_bytes) > max_bytes:
        raise IngressBoundExceededError(
            f"Completion payload size {len(raw_bytes)} exceeds candidate bound {max_bytes}"
        )
    return json.loads(
        raw_bytes.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_object_pairs,
        parse_constant=_reject_non_finite_constant,
    )


def _canonicalize_finding(finding: CanonicalFindingCandidate) -> dict[str, Any]:
    dumped = finding.model_dump(mode="json")
    refs = dumped.get("references") or []
    dumped["references"] = sorted(
        refs,
        key=lambda r: (
            str(r.get("type") or ""),
            str(r.get("value") or ""),
            str(r.get("url") or ""),
        ),
    )
    return dumped


def _canonicalize_scanner_run(run: ScannerRunCompletion) -> dict[str, Any]:
    return run.model_dump(mode="json")


def compute_canonical_evidence_digest(data: ScanCompletionRequest) -> str:
    """Compute a deterministic, order-independent SHA-256 digest of validated evidence."""
    negotiated_version = negotiate_contract_version(data.contract_version)
    for finding in data.findings:
        if finding.confidence_score is not None and not math.isfinite(finding.confidence_score):
            raise InvalidJsonNumberError("Finding confidence_score must be finite")

    sorted_findings = sorted(
        (_canonicalize_finding(f) for f in data.findings),
        key=lambda f: (
            str(f.get("canonical_fingerprint") or ""),
            str(f.get("category") or ""),
            str(f.get("primary_scanner") or ""),
            str(f.get("title") or ""),
            json.dumps(f.get("instance") or {}, sort_keys=True, separators=(",", ":"), default=str),
        ),
    )
    sorted_runs = sorted(
        (_canonicalize_scanner_run(r) for r in data.scanner_runs),
        key=lambda r: str(r.get("scanner_name") or ""),
    )
    sanitized_summary = {
        k: v for k, v in (data.summary_json or {}).items() if k not in FORBIDDEN_SUMMARY_AUTHORITY_KEYS
    }
    payload = {
        "artifact_uris": data.artifact_uris,
        "contract_version": negotiated_version,
        "execution_revision": data.execution_revision,
        "findings": sorted_findings,
        "scanner_runs": sorted_runs,
        "summary_json": sanitized_summary,
        "winning_attempt_id": str(data.winning_attempt_id),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _is_scanner_db_fresh(run: ScannerRunCompletion, *, now: datetime) -> bool:
    scanner = run.scanner_name.lower()
    if scanner not in DATABASE_BACKED_SCANNERS:
        return True
    if run.db_freshness_state != "fresh" or run.db_published_at is None or not run.db_digest:
        return False
    published_at = (
        run.db_published_at
        if run.db_published_at.tzinfo is not None
        else run.db_published_at.replace(tzinfo=UTC)
    )
    age = now - published_at
    return timedelta(0) <= age <= MAX_SCANNER_DB_AGE


def derive_scan_evidence_decision(  # noqa: PLR0912, PLR0915
    data: ScanCompletionRequest,
    *,
    expected_scanners: list[str] | tuple[str, ...] | None = None,
    commit_sha: str | None = None,
    full_ref_name: str | None = None,  # noqa: ARG001
    branch_generation_number: int = 1,  # noqa: ARG001
    ancestry_status: str = "unknown",
    cleanup_state: str = "completed",
    superseded_by_scan_id: str | None = None,
    now: datetime | None = None,
) -> DerivedScanEvidenceDecision:
    """Validate completion input and compute server-owned coverage, artifact, and closure decisions."""
    eval_now = now or datetime.now(UTC)
    contract_version = negotiate_contract_version(data.contract_version)

    if len(data.findings) > CANDIDATE_MAX_FINDINGS_PER_SCAN:
        raise IngressBoundExceededError(
            f"Findings count {len(data.findings)} exceeds candidate bound {CANDIDATE_MAX_FINDINGS_PER_SCAN}"
        )
    if len(data.scanner_runs) > CANDIDATE_MAX_SCANNER_RUNS_PER_SCAN:
        raise IngressBoundExceededError(
            f"Scanner runs count {len(data.scanner_runs)} exceeds candidate bound {CANDIDATE_MAX_SCANNER_RUNS_PER_SCAN}"
        )

    forbidden_keys = FORBIDDEN_SUMMARY_AUTHORITY_KEYS.intersection((data.summary_json or {}).keys())
    if forbidden_keys:
        raise ForbiddenWorkerAuthorityError(
            f"Worker summary_json cannot assert server-owned authority fields: {sorted(forbidden_keys)}"
        )

    seen_scanners: set[str] = set()
    for run in data.scanner_runs:
        name = run.scanner_name.strip().lower()
        if name in seen_scanners:
            raise DuplicateScannerRunError(f"Duplicate scanner_run entry for '{name}'")
        if name not in KNOWN_BETA_SCANNERS:
            raise UnknownScannerError(f"Unknown scanner '{name}' is not in the registered beta catalog")
        seen_scanners.add(name)

    for finding in data.findings:
        if len(finding.references) > CANDIDATE_MAX_REFERENCES_PER_FINDING:
            raise IngressBoundExceededError(
                f"Finding references count {len(finding.references)} exceeds candidate bound "
                f"{CANDIDATE_MAX_REFERENCES_PER_FINDING}"
            )

    reasons: list[str] = []
    if superseded_by_scan_id:
        reasons.append("scan_superseded")
        return DerivedScanEvidenceDecision(
            contract_version=contract_version,
            coverage_completeness="unknown",
            scanner_runs_complete=False,
            closure_eligible=False,
            artifact_availability="unavailable",
            expected_scanners=tuple(expected_scanners or ()),
            completed_scanners=(),
            failed_scanners=(),
            missing_scanners=tuple(expected_scanners or ()),
            ineligibility_reasons=tuple(reasons),
            severity_counts={},
        )

    resolved_expected = (
        tuple(s.strip().lower() for s in expected_scanners if s and s.strip())
        if expected_scanners
        else tuple(run.scanner_name.strip().lower() for run in data.scanner_runs)
    )
    if not resolved_expected:
        reasons.append("no_expected_scanners")

    runs_by_name = {run.scanner_name.strip().lower(): run for run in data.scanner_runs}
    completed_scanners: list[str] = []
    failed_scanners: list[str] = []
    missing_scanners: list[str] = []
    db_stale = False

    for scanner_name in resolved_expected:
        run = runs_by_name.get(scanner_name)
        if run is None:
            missing_scanners.append(scanner_name)
            continue
        outcome = (run.outcome_status or run.status or "").lower()
        if outcome in {"completed", "skipped_unapplicable"} and run.status == "completed":
            if not _is_scanner_db_fresh(run, now=eval_now):
                db_stale = True
                failed_scanners.append(scanner_name)
            else:
                completed_scanners.append(scanner_name)
        else:
            failed_scanners.append(scanner_name)

    if db_stale:
        reasons.append("scanner_database_stale")
    if missing_scanners:
        reasons.append("missing_expected_scanners")
    if failed_scanners and not db_stale:
        reasons.append("failed_scanner_runs")

    if not resolved_expected:
        coverage_completeness = "unknown"
        scanner_runs_complete = False
    elif not missing_scanners and not failed_scanners:
        coverage_completeness = "full"
        scanner_runs_complete = True
    else:
        coverage_completeness = "partial"
        scanner_runs_complete = False

    if not commit_sha or len(commit_sha.strip()) < MIN_ABBREVIATED_COMMIT_SHA_LENGTH:
        reasons.append("unverified_commit_revision")
    if ancestry_status not in {"verified_initial", "verified_descendant"}:
        reasons.append("non_descendant_ancestry")
    if cleanup_state not in {"completed", "not_required"}:
        reasons.append("cleanup_not_completed")

    closure_eligible = coverage_completeness == "full" and not reasons

    # Artifact availability is derived separately from scanner coverage.
    artifact_states = [
        (run.artifact_availability or ("verified_immutable" if run.artifact_uri else "unavailable")).lower()
        for run in data.scanner_runs
    ]
    if not artifact_states or all(state == "unavailable" for state in artifact_states):
        artifact_availability = "unavailable"
    elif all(state == "verified_immutable" for state in artifact_states):
        artifact_availability = "verified_immutable"
    else:
        artifact_availability = "partial"

    severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for finding in data.findings:
        sev = (finding.severity or "medium").lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    return DerivedScanEvidenceDecision(
        contract_version=contract_version,
        coverage_completeness=coverage_completeness,
        scanner_runs_complete=scanner_runs_complete,
        closure_eligible=closure_eligible,
        artifact_availability=artifact_availability,
        expected_scanners=resolved_expected,
        completed_scanners=tuple(completed_scanners),
        failed_scanners=tuple(failed_scanners),
        missing_scanners=tuple(missing_scanners),
        ineligibility_reasons=tuple(reasons),
        severity_counts=severity_counts,
    )
