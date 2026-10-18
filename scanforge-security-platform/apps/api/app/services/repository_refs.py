"""Repository ref identity, exact revision resolution, and branch generation continuity (ADR-012 / Task M06).

Enforces:
- Canonical full ref preservation (`refs/heads/<branch_name>`) without losing slash-delimited branch names.
- Explicit separation of automatic default-branch scope from authorized manual branch requests.
- Provider-backed ancestry receipts (`ahead`, `identical`, `diverged`, `behind`, `unknown`).
- Automatic generation increment (`generation_number + 1`) on force-push, non-descendant history,
  unverifiable ancestry, or branch deletion followed by recreation.
- Absence-credit eligibility restricted strictly to verified distinct descendant commits within the
  same branch generation (`ancestry_status == "verified_descendant"`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select

from app.db.models.repository import Repository, RepositoryBranchGeneration

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

EXACT_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
HEX_COMMIT_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
GIT_REF_CONTROL_CHARACTER_LIMIT = 32

SCAN_TYPE_SCANNERS: dict[str, list[str]] = {
    "full": ["trivy", "gitleaks", "osv", "semgrep", "syft", "checkov", "grype"],
    "diff": ["gitleaks", "semgrep", "checkov"],
    "dependencies": ["trivy", "osv", "syft", "grype"],
    "secrets": ["gitleaks"],
}


class RepositoryRefError(ValueError):
    """Raised when a branch ref, commit SHA, or repository state is invalid."""


class RepositoryScopeError(ValueError):
    """Raised when a trigger attempts to scan an unauthorized branch scope."""


@dataclass(frozen=True)
class AncestryReceipt:
    base_commit_sha: str | None
    head_commit_sha: str
    relation: str
    ancestry_status: str
    generation_number: int
    new_generation_started: bool
    absence_credit_eligible: bool
    provider_receipt: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_commit_sha": self.base_commit_sha,
            "head_commit_sha": self.head_commit_sha,
            "relation": self.relation,
            "ancestry_status": self.ancestry_status,
            "generation_number": self.generation_number,
            "new_generation_started": self.new_generation_started,
            "absence_credit_eligible": self.absence_credit_eligible,
            "provider_receipt": dict(self.provider_receipt),
        }


@dataclass(frozen=True)
class ResolvedScanRevision:
    repository_id: str
    external_repo_id: str | None
    branch_name: str
    full_ref_name: str
    branch_scope: str
    commit_sha: str
    generation_number: int
    ancestry_status: str
    expected_scanners: list[str]
    coverage_scope: dict[str, Any]
    ancestry_receipt: AncestryReceipt


def normalize_branch_and_full_ref(
    branch_or_ref: str | None,
    default_branch: str | None = None,
) -> tuple[str, str]:
    """Return `(branch_name, full_ref_name)` for a branch or `refs/heads/...` ref.

    Rejects non-branch refs (`refs/tags/*`, `refs/pull/*`), path traversal (`..`),
    whitespace, and invalid Git ref sequences.
    """
    raw = (branch_or_ref or "").strip()
    if not raw:
        raw = (default_branch or "").strip()
    if not raw:
        raise RepositoryRefError("Branch ref or repository default_branch is required")

    if raw.startswith("refs/"):
        if not raw.startswith("refs/heads/"):
            raise RepositoryRefError(f"Only branch refs under refs/heads/ are supported, got {raw!r}")
        branch_name = raw[len("refs/heads/") :]
        full_ref_name = raw
    else:
        branch_name = raw
        full_ref_name = f"refs/heads/{branch_name}"

    if (
        not branch_name
        or branch_name.startswith("/")
        or branch_name.endswith(("/", ".lock"))
        or ".." in branch_name
        or "//" in branch_name
        or "@{" in branch_name
        or "\\" in branch_name
        or any(
            ch.isspace()
            or ord(ch) < GIT_REF_CONTROL_CHARACTER_LIMIT
            or ch in {"~", "^", ":", "?", "*", "["}
            for ch in branch_name
        )
    ):
        raise RepositoryRefError(f"Invalid Git branch reference: {branch_or_ref!r}")

    return branch_name, full_ref_name


def validate_commit_sha(commit_sha: str | None, *, require_exact: bool = True) -> str:
    """Validate and normalize a commit SHA to lowercase hex."""
    cleaned = (commit_sha or "").strip().lower()
    if not cleaned:
        raise RepositoryRefError("Exact commit SHA is required before scan dispatch")
    pattern = EXACT_COMMIT_SHA_RE if require_exact else HEX_COMMIT_SHA_RE
    if not pattern.match(cleaned):
        raise RepositoryRefError(f"Invalid commit SHA {commit_sha!r}; expected 40-character hexadecimal SHA")
    return cleaned


def resolve_branch_scope(
    *,
    branch_name: str,
    default_branch: str | None,
    trigger_type: str,
) -> str:
    """Enforce ADR-012 default-branch vs manual-branch scope rules."""
    normalized_default = (default_branch or "").strip()
    if normalized_default and normalized_default.startswith("refs/heads/"):
        normalized_default = normalized_default[len("refs/heads/") :]

    is_default = bool(normalized_default) and branch_name == normalized_default
    if trigger_type == "webhook":
        if not normalized_default:
            raise RepositoryScopeError("Repository default_branch must be verified before automatic push scans")
        if not is_default:
            raise RepositoryScopeError(
                f"Automatic push scans are restricted to default branch {normalized_default!r}; got {branch_name!r}"
            )
        return "default_branch"

    return "default_branch" if is_default else "manual_branch"


class RepositoryRefService:
    """Manages per-branch generations and provider-backed ancestry continuity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_generation(
        self,
        repository_id: UUID | str,
        full_ref_name: str,
    ) -> RepositoryBranchGeneration | None:
        result = await self.db.execute(
            select(RepositoryBranchGeneration)
            .where(
                RepositoryBranchGeneration.repository_id == str(repository_id),
                RepositoryBranchGeneration.full_ref_name == full_ref_name,
                RepositoryBranchGeneration.retired_at.is_(None),
            )
            .order_by(RepositoryBranchGeneration.generation_number.desc())
        )
        return result.scalars().first()

    async def retire_branch(
        self,
        repository_id: UUID | str,
        branch_or_ref: str,
        *,
        retired_at: datetime | None = None,
    ) -> RepositoryBranchGeneration | None:
        _, full_ref_name = normalize_branch_and_full_ref(branch_or_ref)
        active = await self.get_active_generation(repository_id, full_ref_name)
        if active is None:
            return None
        active.retired_at = retired_at or datetime.now(UTC)
        await self.db.flush()
        return active

    async def resolve_and_advance_generation(  # noqa: PLR0915
        self,
        *,
        repository_id: UUID | str,
        branch_name: str,
        full_ref_name: str,
        target_commit_sha: str,
        force_pushed: bool = False,
        ancestry_relation: str | None = None,
        provider_receipt: dict[str, Any] | None = None,
        compare_fn: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
    ) -> tuple[RepositoryBranchGeneration, AncestryReceipt]:
        """Resolve or advance the branch generation for `(repository_id, full_ref_name)`."""
        repo_id_str = str(repository_id)
        normalized_sha = validate_commit_sha(target_commit_sha, require_exact=False)
        active = await self.get_active_generation(repo_id_str, full_ref_name)

        max_gen_result = await self.db.execute(
            select(func.max(RepositoryBranchGeneration.generation_number)).where(
                RepositoryBranchGeneration.repository_id == repo_id_str,
                RepositoryBranchGeneration.full_ref_name == full_ref_name,
            )
        )
        max_gen = int(max_gen_result.scalar_one_or_none() or 0)

        receipt_meta = dict(provider_receipt or {})

        # Case 1: No active generation (initial creation or branch recreation after deletion)
        if active is None:
            next_gen_number = max_gen + 1
            was_recreated = max_gen >= 1
            ancestry_status = "recreated_reset" if was_recreated else "verified_initial"
            relation = "recreated" if was_recreated else "initial"
            generation = RepositoryBranchGeneration(
                repository_id=repo_id_str,
                full_ref_name=full_ref_name,
                branch_name=branch_name,
                generation_number=next_gen_number,
                head_commit_sha=normalized_sha,
                ancestry_status=ancestry_status,
                retired_at=None,
            )
            self.db.add(generation)
            await self.db.flush()
            receipt = AncestryReceipt(
                base_commit_sha=None,
                head_commit_sha=normalized_sha,
                relation=relation,
                ancestry_status=ancestry_status,
                generation_number=next_gen_number,
                new_generation_started=True,
                absence_credit_eligible=False,
                provider_receipt=receipt_meta,
            )
            return generation, receipt

        previous_sha = (active.head_commit_sha or "").strip().lower() or None

        # Case 2: Active generation has no recorded head commit yet
        if previous_sha is None:
            active.head_commit_sha = normalized_sha
            active.ancestry_status = "verified_initial"
            await self.db.flush()
            receipt = AncestryReceipt(
                base_commit_sha=None,
                head_commit_sha=normalized_sha,
                relation="initial",
                ancestry_status="verified_initial",
                generation_number=active.generation_number,
                new_generation_started=False,
                absence_credit_eligible=False,
                provider_receipt=receipt_meta,
            )
            return active, receipt

        # Case 3: Explicit force-push always retires the prior generation and starts a new one
        if force_pushed:
            active.retired_at = datetime.now(UTC)
            await self.db.flush()
            next_gen_number = max(max_gen, active.generation_number) + 1
            new_gen = RepositoryBranchGeneration(
                repository_id=repo_id_str,
                full_ref_name=full_ref_name,
                branch_name=branch_name,
                generation_number=next_gen_number,
                head_commit_sha=normalized_sha,
                ancestry_status="diverged_reset",
                retired_at=None,
            )
            self.db.add(new_gen)
            await self.db.flush()
            receipt = AncestryReceipt(
                base_commit_sha=previous_sha,
                head_commit_sha=normalized_sha,
                relation="diverged",
                ancestry_status="diverged_reset",
                generation_number=next_gen_number,
                new_generation_started=True,
                absence_credit_eligible=False,
                provider_receipt={**receipt_meta, "force_pushed": True},
            )
            return new_gen, receipt

        # Case 4: Same-commit rerun — preserves generation but never grants absence credit
        if previous_sha == normalized_sha:
            receipt = AncestryReceipt(
                base_commit_sha=previous_sha,
                head_commit_sha=normalized_sha,
                relation="identical",
                ancestry_status="same_revision",
                generation_number=active.generation_number,
                new_generation_started=False,
                absence_credit_eligible=False,
                provider_receipt=receipt_meta,
            )
            return active, receipt

        # Case 5: Determine ancestry relation between previous_sha and normalized_sha
        resolved_relation = ancestry_relation
        if resolved_relation is None and compare_fn is not None:
            try:
                compare_data = await compare_fn(previous_sha, normalized_sha)
                receipt_meta.update(compare_data or {})
                resolved_relation = str((compare_data or {}).get("status") or "unknown")
            except Exception as exc:
                receipt_meta["compare_error"] = type(exc).__name__
                resolved_relation = "unknown"

        if resolved_relation is None:
            resolved_relation = "unknown"

        if resolved_relation == "ahead":
            active.head_commit_sha = normalized_sha
            active.ancestry_status = "verified_descendant"
            await self.db.flush()
            receipt = AncestryReceipt(
                base_commit_sha=previous_sha,
                head_commit_sha=normalized_sha,
                relation="ahead",
                ancestry_status="verified_descendant",
                generation_number=active.generation_number,
                new_generation_started=False,
                absence_credit_eligible=True,
                provider_receipt=receipt_meta,
            )
            return active, receipt

        # Non-descendant ("diverged", "behind") or unverifiable ("unknown") continuity
        # retires the current generation and starts a new generation with zero absence credit.
        active.retired_at = datetime.now(UTC)
        await self.db.flush()
        next_gen_number = max(max_gen, active.generation_number) + 1
        reset_status = (
            "diverged_reset" if resolved_relation in {"diverged", "behind"} else "unknown_reset"
        )
        new_gen = RepositoryBranchGeneration(
            repository_id=repo_id_str,
            full_ref_name=full_ref_name,
            branch_name=branch_name,
            generation_number=next_gen_number,
            head_commit_sha=normalized_sha,
            ancestry_status=reset_status,
            retired_at=None,
        )
        self.db.add(new_gen)
        await self.db.flush()
        receipt = AncestryReceipt(
            base_commit_sha=previous_sha,
            head_commit_sha=normalized_sha,
            relation=resolved_relation,
            ancestry_status=reset_status,
            generation_number=next_gen_number,
            new_generation_started=True,
            absence_credit_eligible=False,
            provider_receipt=receipt_meta,
        )
        return new_gen, receipt

    async def resolve_scan_revision(
        self,
        *,
        repo: Repository,
        trigger_type: str,
        scan_type: str,
        branch_or_ref: str | None,
        commit_sha: str | None,
        force_pushed: bool = False,
        ancestry_relation: str | None = None,
        provider_receipt: dict[str, Any] | None = None,
        revision_resolver: Callable[[str, str | None], Awaitable[str]] | None = None,
        compare_fn: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
        require_exact_sha: bool = False,
    ) -> ResolvedScanRevision:
        """Resolve exact revision, full ref, generation, and coverage policy before scan dispatch."""
        if not repo.is_active or getattr(repo, "lifecycle_state", "connected") != "connected":
            raise RepositoryRefError("Repository is not active or requires authorization revalidation")

        branch_name, full_ref_name = normalize_branch_and_full_ref(
            branch_or_ref,
            repo.default_branch,
        )
        branch_scope = resolve_branch_scope(
            branch_name=branch_name,
            default_branch=repo.default_branch,
            trigger_type=trigger_type,
        )

        resolved_sha = (commit_sha or "").strip()
        if revision_resolver is not None:
            resolved_sha = await revision_resolver(branch_name, resolved_sha or None)

        if resolved_sha:
            normalized_sha = validate_commit_sha(
                resolved_sha,
                require_exact=require_exact_sha,
            )
            generation, ancestry_receipt = await self.resolve_and_advance_generation(
                repository_id=repo.id,
                branch_name=branch_name,
                full_ref_name=full_ref_name,
                target_commit_sha=normalized_sha,
                force_pushed=force_pushed,
                ancestry_relation=ancestry_relation,
                provider_receipt=provider_receipt,
                compare_fn=compare_fn,
            )
            generation_number = generation.generation_number
            ancestry_status = ancestry_receipt.ancestry_status
        else:
            if require_exact_sha:
                raise RepositoryRefError("Exact commit SHA is required before scan dispatch")
            normalized_sha = ""
            active = await self.get_active_generation(repo.id, full_ref_name)
            generation_number = active.generation_number if active else 1
            ancestry_status = "unknown"
            ancestry_receipt = AncestryReceipt(
                base_commit_sha=active.head_commit_sha if active else None,
                head_commit_sha="",
                relation="unknown",
                ancestry_status="unknown",
                generation_number=generation_number,
                new_generation_started=False,
                absence_credit_eligible=False,
                provider_receipt=dict(provider_receipt or {}),
            )

        expected_scanners = list(
            SCAN_TYPE_SCANNERS.get(scan_type, SCAN_TYPE_SCANNERS["full"])
        )
        coverage_scope = {
            "repository_id": str(repo.id),
            "external_repo_id": repo.external_repo_id,
            "branch": branch_name,
            "full_ref_name": full_ref_name,
            "branch_scope": branch_scope,
            "branch_generation_number": generation_number,
            "ancestry_status": ancestry_status,
            "absence_credit_eligible": ancestry_receipt.absence_credit_eligible,
            "commit_sha": normalized_sha or None,
            "scan_type": scan_type,
            "expected_scanners": expected_scanners,
            "ancestry_receipt": ancestry_receipt.to_dict(),
        }
        return ResolvedScanRevision(
            repository_id=str(repo.id),
            external_repo_id=repo.external_repo_id,
            branch_name=branch_name,
            full_ref_name=full_ref_name,
            branch_scope=branch_scope,
            commit_sha=normalized_sha,
            generation_number=generation_number,
            ancestry_status=ancestry_status,
            expected_scanners=expected_scanners,
            coverage_scope=coverage_scope,
            ancestry_receipt=ancestry_receipt,
        )
