"""Reconcile repositories to GitHub's current state after missed events (#54, P2.5).

After an ingress outage (or on demand) the service reads GitHub's *current* installation,
repository list and default-branch head through an injected provider, then converges local
authority and head to it:

- Lifecycle events missed during the outage (delete, suspend, permission change, repository
  removal or re-add, rename, default-branch change) are applied with the same revoke/restore
  rules as the live lifecycle handlers, so human disconnects are never reversed.
- A reinstall under a new installation id rebinds revoked repositories by immutable
  repository id, only for the organization that owns the current binding.
- Each connected repository advances its default-branch generation once, to the current head.
  Intervening commits are never observed, scanned or credited: ancestry is compared only
  between the previously recorded head and the current head.
- Provider failures never change authority (unknown is not revoked). Every run persists a
  receipt with redacted operational errors; secrets and response bodies are never stored.

Live GitHub App delivery is not verified here; callers inject a provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select

from app.db.models import (
    GitHubReconciliationReceipt,
    OrganizationIntegration,
    Project,
    Repository,
    RepositoryIntegration,
)
from app.services.github_lifecycle import (
    REASON_DELETED,
    REASON_PERMISSIONS,
    REASON_REMOVED,
    REASON_SUSPENDED,
    REASON_TRANSFERRED,
    GitHubLifecycleService,
    _has_contents_read,
)
from app.services.repository_refs import RepositoryRefService, normalize_branch_and_full_ref

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

ERROR_MESSAGE_LIMIT = 500
_REDACTIONS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+"),
    re.compile(r"(?i)\bbearer\s+\S+"),
    re.compile(r"(?i)\b(token|secret|password|authorization)\s*[=:]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|$)", re.DOTALL),
)


class GitHubProviderError(Exception):
    """A transient or unexpected provider failure with a stable, non-secret `code`."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class InstallationSnapshot:
    suspended: bool
    permissions: dict[str, Any]


@dataclass(frozen=True)
class RepositorySnapshot:
    external_repo_id: str
    owner_name: str
    repo_name: str
    full_name: str
    default_branch: str | None


class GitHubStateProvider(Protocol):
    async def get_installation(self, installation_id: str) -> InstallationSnapshot | None:
        """Current installation state, or None when GitHub reports it gone (404)."""

    async def list_repositories(self, installation_id: str) -> list[RepositorySnapshot]: ...

    async def resolve_head(self, installation_id: str, owner_name: str, repo_name: str, branch_name: str) -> str: ...

    async def compare_commits(
        self, installation_id: str, owner_name: str, repo_name: str, base_sha: str, head_sha: str
    ) -> dict[str, Any]: ...


def redact(text: str) -> str:
    for pattern in _REDACTIONS:
        text = pattern.sub("[redacted]", text)
    return text[:ERROR_MESSAGE_LIMIT]


def _safe_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, GitHubProviderError):
        return exc.code[:64], redact(exc.message)
    return "unexpected_error", f"Unexpected {type(exc).__name__} during reconciliation"


def _now() -> datetime:
    return datetime.now(UTC)


class GitHubReconciliationService:
    def __init__(self, db: AsyncSession, provider: GitHubStateProvider):
        self.db = db
        self.provider = provider
        self._lifecycle = GitHubLifecycleService(db)

    # -- entry points -------------------------------------------------------

    async def reconcile_installation(self, installation_id: str, *, trigger: str = "manual") -> dict[str, Any]:
        return await self._run(str(installation_id), trigger, rebind_org_id=None)

    async def reconcile_organization(self, organization_id: Any, *, trigger: str = "reinstall") -> dict[str, Any]:
        """Reconcile the organization's *current* installation, rebinding repositories
        that a deleted earlier installation left revoked."""
        integration = (
            await self.db.execute(
                select(OrganizationIntegration).where(
                    OrganizationIntegration.organization_id == organization_id,
                    OrganizationIntegration.provider == "github",
                )
            )
        ).scalar_one_or_none()
        if integration is None or not integration.installation_id:
            return {"status": "skipped", "reason": "no_installation_binding", "repositories": []}
        return await self._run(str(integration.installation_id), trigger, rebind_org_id=organization_id)

    # -- run ----------------------------------------------------------------

    async def _run(self, installation_id: str, trigger: str, *, rebind_org_id: Any) -> dict[str, Any]:
        started = _now()
        organization_id = rebind_org_id or await self._organization_for(installation_id)
        summary: dict[str, Any] = {"installation_id": installation_id, "repositories": []}
        error_code: str | None = None
        error_message: str | None = None
        try:
            # All provider reads that decide authority happen before any local change.
            snapshot = await self.provider.get_installation(installation_id)
            listing = await self.provider.list_repositories(installation_id) if self._is_active(snapshot) else []
        except Exception as exc:
            await self.db.rollback()
            error_code, error_message = _safe_error(exc)
            summary["installation_state"] = "unknown"
            return await self._finish(
                installation_id, organization_id, trigger, started, "failed", summary, error_code, error_message
            )

        if snapshot is None:
            summary["installation_state"] = "deleted"
            await self._revoke_all(installation_id, REASON_DELETED, summary)
            await self._drop_org_bindings(installation_id)
        elif snapshot.suspended:
            summary["installation_state"] = "suspended"
            await self._revoke_all(installation_id, REASON_SUSPENDED, summary)
        elif not _has_contents_read(snapshot.permissions):
            summary["installation_state"] = "permissions_insufficient"
            await self._revoke_all(installation_id, REASON_PERMISSIONS, summary, permissions=snapshot.permissions)
        else:
            summary["installation_state"] = "active"
            await self._reconcile_active(installation_id, listing, rebind_org_id, summary)

        errors = [r for r in summary["repositories"] if r.get("error_code")]
        status = "completed_with_errors" if errors else "completed"
        return await self._finish(installation_id, organization_id, trigger, started, status, summary, None, None)

    @staticmethod
    def _is_active(snapshot: InstallationSnapshot | None) -> bool:
        return snapshot is not None and not snapshot.suspended and _has_contents_read(snapshot.permissions)

    async def _finish(
        self,
        installation_id: str,
        organization_id: Any,
        trigger: str,
        started: datetime,
        status: str,
        summary: dict[str, Any],
        error_code: str | None,
        error_message: str | None,
    ) -> dict[str, Any]:
        receipt = GitHubReconciliationReceipt(
            installation_id=installation_id,
            organization_id=organization_id,
            trigger=trigger[:32],
            status=status,
            error_code=error_code,
            error_message=error_message,
            summary=summary,
            started_at=started,
            finished_at=_now(),
        )
        self.db.add(receipt)
        await self.db.commit()
        result = {**summary, "status": status, "receipt_id": str(receipt.id)}
        if error_code:
            result["error_code"] = error_code
        return result

    async def _organization_for(self, installation_id: str) -> Any:
        found = (
            await self.db.execute(
                select(OrganizationIntegration.organization_id).where(
                    OrganizationIntegration.installation_id == installation_id
                )
            )
        ).scalar_one_or_none()
        if found is not None:
            return found
        return (
            await self.db.execute(
                select(Project.organization_id)
                .join(Repository, Repository.project_id == Project.id)
                .join(RepositoryIntegration, RepositoryIntegration.repository_id == Repository.id)
                .where(RepositoryIntegration.installation_id == installation_id)
                .limit(1)
            )
        ).scalar_one_or_none()

    # -- authority ----------------------------------------------------------

    async def _revoke_all(
        self,
        installation_id: str,
        reason: str,
        summary: dict[str, Any],
        *,
        permissions: dict[str, Any] | None = None,
    ) -> None:
        for repo, integration in await self._lifecycle._bound_repositories(installation_id):
            if permissions is not None:
                meta = dict(integration.access_metadata or {})
                meta["permissions"] = permissions
                integration.access_metadata = meta
            self._lifecycle._revoke(repo, integration, reason)
            summary["repositories"].append(self._entry(repo, action="revoked", reason=reason))

    async def _drop_org_bindings(self, installation_id: str) -> None:
        rows = await self.db.execute(
            select(OrganizationIntegration).where(OrganizationIntegration.installation_id == installation_id)
        )
        for row in rows.scalars().all():
            await self.db.delete(row)

    async def _rebind_after_reinstall(
        self, installation_id: str, organization_id: Any, listed_ids: set[str]
    ) -> None:
        """Move repositories left revoked by a deleted installation onto the org's new one."""
        rows = await self.db.execute(
            select(Repository, RepositoryIntegration)
            .join(Project, Project.id == Repository.project_id)
            .join(RepositoryIntegration, RepositoryIntegration.repository_id == Repository.id)
            .where(Project.organization_id == organization_id, RepositoryIntegration.installation_id != installation_id)
        )
        for repo, integration in rows.all():
            if repo.external_repo_id is None or str(repo.external_repo_id) not in listed_ids:
                continue
            meta = dict(integration.access_metadata or {})
            if repo.lifecycle_state != "reauthorization_required" or meta.get("revocation_reason") != REASON_DELETED:
                continue
            integration.installation_id = installation_id
            self._lifecycle._restore(repo, integration, reasons={REASON_DELETED})

    async def _reconcile_active(
        self,
        installation_id: str,
        listing: list[RepositorySnapshot],
        rebind_org_id: Any,
        summary: dict[str, Any],
    ) -> None:
        by_id = {str(item.external_repo_id): item for item in listing}
        if rebind_org_id is not None:
            await self._rebind_after_reinstall(installation_id, rebind_org_id, set(by_id))
        await self.db.flush()

        for repo, integration in await self._lifecycle._bound_repositories(installation_id):
            listed = by_id.get(str(repo.external_repo_id)) if repo.external_repo_id is not None else None
            if listed is None:
                self._lifecycle._revoke(repo, integration, REASON_REMOVED)
                summary["repositories"].append(self._entry(repo, action="revoked", reason=REASON_REMOVED))
                continue
            self._lifecycle._restore(
                repo, integration, reasons={REASON_SUSPENDED, REASON_PERMISSIONS, REASON_REMOVED, REASON_DELETED}
            )
            if repo.lifecycle_state != "connected" or not repo.is_active:
                summary["repositories"].append(self._entry(repo, action="skipped", reason=repo.lifecycle_state))
                continue
            if listed.owner_name.lower() != repo.owner_name.lower():
                # Ownership changed: authority does not follow a transfer automatically.
                self._lifecycle._revoke(repo, integration, REASON_TRANSFERRED)
                summary["repositories"].append(self._entry(repo, action="revoked", reason=REASON_TRANSFERRED))
                continue
            self._apply_names(repo, listed)
            summary["repositories"].append(await self._advance_head(installation_id, repo))

    @staticmethod
    def _apply_names(repo: Repository, listed: RepositorySnapshot) -> None:
        repo.owner_name = listed.owner_name
        repo.repo_name = listed.repo_name
        repo.full_name = listed.full_name
        repo.clone_url = f"https://github.com/{listed.full_name}.git"
        repo.html_url = f"https://github.com/{listed.full_name}"
        if listed.default_branch:
            repo.default_branch = listed.default_branch

    # -- head ---------------------------------------------------------------

    @staticmethod
    def _entry(repo: Repository, *, action: str, reason: str | None = None) -> dict[str, Any]:
        return {
            "repository_id": str(repo.id),
            "external_repo_id": repo.external_repo_id,
            "action": action,
            "reason": reason,
        }

    async def _advance_head(self, installation_id: str, repo: Repository) -> dict[str, Any]:
        entry = self._entry(repo, action="head_reconciled")
        refs = RepositoryRefService(self.db)
        try:
            branch_name, full_ref_name = normalize_branch_and_full_ref(None, repo.default_branch)
            active = await refs.get_active_generation(repo.id, full_ref_name)
            previous = (active.head_commit_sha if active else None) or None
            current = (
                await self.provider.resolve_head(installation_id, repo.owner_name, repo.repo_name, branch_name)
            ).strip().lower()

            async def compare(base: str, head: str) -> dict[str, Any]:
                return await self.provider.compare_commits(installation_id, repo.owner_name, repo.repo_name, base, head)

            _, receipt = await refs.resolve_and_advance_generation(
                repository_id=repo.id,
                branch_name=branch_name,
                full_ref_name=full_ref_name,
                target_commit_sha=current,
                compare_fn=compare,
            )
        except Exception as exc:
            code, message = _safe_error(exc)
            if not isinstance(exc, GitHubProviderError):
                code = "head_resolution_failed"
            entry.update(action="head_error", error_code=code, error_message=message)
            return entry
        entry.update(
            previous_head=previous,
            current_head=current,
            head_changed=previous != current,
            relation=receipt.relation,
            ancestry_status=receipt.ancestry_status,
            generation_number=receipt.generation_number,
            new_generation_started=receipt.new_generation_started,
            absence_credit_eligible=receipt.absence_credit_eligible,
            provider_receipt=receipt.provider_receipt,
            # Only the previous and current heads are ever examined; nothing in between.
            intermediate_commits_observed=False,
        )
        return entry
