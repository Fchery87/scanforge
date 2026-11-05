"""Reconcile GitHub App installation and repository lifecycle events (#53, P2.5).

Authority model: a repository may run scans only while it is active, in the
``connected`` lifecycle state, and bound to an installation that GitHub still
reports as installed, unsuspended and permitted to read contents. Every handler
is scoped by the repository's *stored* installation binding, so an event from a
foreign installation can never change another organization's repositories.
Handlers are idempotent state transitions; replays are harmless.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.db.models import OrganizationIntegration, Repository, RepositoryIntegration
from app.services.repositories import RepositoryService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

REVOKED_STATE = "reauthorization_required"
CONNECTED_STATE = "connected"
SUPPORTED_EVENTS = frozenset({"installation", "installation_repositories", "repository"})

REASON_DELETED = "installation_deleted"
REASON_SUSPENDED = "installation_suspended"
REASON_PERMISSIONS = "insufficient_permissions"
REASON_REMOVED = "repository_removed_from_installation"
REASON_REPOSITORY_DELETED = "repository_deleted"
REASON_TRANSFERRED = "repository_transferred"
_REASON_KEY = "revocation_reason"


def _ignored(event: str, action: str | None) -> dict[str, Any]:
    return {"status": "ignored", "event": event, "action": action}


def _processed(event: str, action: str | None, updated: int) -> dict[str, Any]:
    return {"status": "processed", "event": event, "action": action, "repositories_updated": updated}


def _has_contents_read(permissions: dict[str, Any] | None) -> bool:
    return (permissions or {}).get("contents") in {"read", "write"}


class GitHubLifecycleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def handle(self, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        action = payload.get("action")
        installation_id = (payload.get("installation") or {}).get("id")
        if event not in SUPPORTED_EVENTS or installation_id is None:
            return _ignored(event, action)
        installation_id = str(installation_id)

        if event == "installation":
            result = await self._handle_installation(action, installation_id, payload)
        elif event == "installation_repositories":
            result = await self._handle_installation_repositories(action, installation_id, payload)
        else:
            result = await self._handle_repository(action, installation_id, payload)
        await self.db.commit()
        return result if result is not None else _ignored(event, action)

    # -- helpers -----------------------------------------------------------

    async def _bound_repositories(
        self, installation_id: str, *, external_repo_id: str | None = None
    ) -> list[tuple[Repository, RepositoryIntegration]]:
        query = (
            select(Repository, RepositoryIntegration)
            .join(RepositoryIntegration, RepositoryIntegration.repository_id == Repository.id)
            .where(RepositoryIntegration.installation_id == installation_id)
        )
        if external_repo_id is not None:
            query = query.where(Repository.external_repo_id == external_repo_id)
        rows = (await self.db.execute(query)).all()
        return [(repo, integration) for repo, integration in rows]

    @staticmethod
    def _revoke(repo: Repository, integration: RepositoryIntegration, reason: str) -> bool:
        if repo.lifecycle_state == "disconnected":
            return False
        meta = dict(integration.access_metadata or {})
        changed = repo.is_active or repo.lifecycle_state != REVOKED_STATE or meta.get(_REASON_KEY) != reason
        repo.is_active = False
        repo.lifecycle_state = REVOKED_STATE
        meta[_REASON_KEY] = reason
        integration.access_metadata = meta
        return changed

    @staticmethod
    def _restore(repo: Repository, integration: RepositoryIntegration, *, reasons: set[str]) -> bool:
        """Restore only repositories that this lifecycle path revoked for one of `reasons`.

        Human disconnects and unrelated revocations stay revoked.
        """
        meta = dict(integration.access_metadata or {})
        if repo.lifecycle_state != REVOKED_STATE or meta.get(_REASON_KEY) not in reasons:
            return False
        meta.pop(_REASON_KEY, None)
        meta.pop("reauthorization_required", None)
        integration.access_metadata = meta
        repo.is_active = True
        repo.lifecycle_state = CONNECTED_STATE
        return True

    # -- installation ------------------------------------------------------

    async def _handle_installation(
        self, action: str | None, installation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        bound = await self._bound_repositories(installation_id)
        updated = 0
        if action == "deleted":
            for repo, integration in bound:
                updated += self._revoke(repo, integration, REASON_DELETED)
            org_integrations = (
                await self.db.execute(
                    select(OrganizationIntegration).where(OrganizationIntegration.installation_id == installation_id)
                )
            ).scalars()
            for org_integration in org_integrations.all():
                await self.db.delete(org_integration)
            return _processed("installation", action, updated)
        if action == "suspend":
            for repo, integration in bound:
                updated += self._revoke(repo, integration, REASON_SUSPENDED)
            return _processed("installation", action, updated)
        if action == "unsuspend":
            for repo, integration in bound:
                updated += self._restore(repo, integration, reasons={REASON_SUSPENDED})
            return _processed("installation", action, updated)
        if action == "new_permissions_accepted":
            permissions = (payload.get("installation") or {}).get("permissions")
            for repo, integration in bound:
                meta = dict(integration.access_metadata or {})
                meta["permissions"] = permissions
                integration.access_metadata = meta
                if _has_contents_read(permissions):
                    updated += self._restore(repo, integration, reasons={REASON_PERMISSIONS})
                else:
                    updated += self._revoke(repo, integration, REASON_PERMISSIONS)
            return _processed("installation", action, updated)
        return None

    async def _handle_installation_repositories(
        self, action: str | None, installation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        updated = 0
        if action == "removed":
            for item in payload.get("repositories_removed") or []:
                for repo, integration in await self._bound_repositories(
                    installation_id, external_repo_id=str(item.get("id"))
                ):
                    updated += self._revoke(repo, integration, REASON_REMOVED)
            return _processed("installation_repositories", action, updated)
        if action == "added":
            for item in payload.get("repositories_added") or []:
                for repo, integration in await self._bound_repositories(
                    installation_id, external_repo_id=str(item.get("id"))
                ):
                    updated += self._restore(repo, integration, reasons={REASON_REMOVED})
            return _processed("installation_repositories", action, updated)
        return None

    # -- repository --------------------------------------------------------

    async def _handle_repository(  # noqa: PLR0911
        self, action: str | None, installation_id: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        repository = payload.get("repository") or {}
        if repository.get("id") is None:
            return None
        external_repo_id = str(repository["id"])
        bound = await self._bound_repositories(installation_id, external_repo_id=external_repo_id)
        if not bound:
            return None
        repo, integration = bound[0]
        owner = (repository.get("owner") or {}).get("login") or repo.owner_name

        if action == "deleted":
            self._revoke(repo, integration, REASON_REPOSITORY_DELETED)
            return _processed("repository", action, 1)

        if action in {"renamed", "transferred"}:
            full_name = repository.get("full_name") or f"{owner}/{repository.get('name') or repo.repo_name}"
            await RepositoryService(self.db).reconcile_rename_or_transfer(
                external_repo_id=external_repo_id,
                new_owner_name=owner,
                new_repo_name=repository.get("name") or repo.repo_name,
                new_full_name=full_name,
                installation_id=installation_id,
                default_branch=repository.get("default_branch"),
                # A transfer is only authoritative while the same bound installation reports it.
                installation_accessible=action == "renamed",
            )
            if action == "transferred" and repo.lifecycle_state == REVOKED_STATE:
                meta = dict(integration.access_metadata or {})
                meta[_REASON_KEY] = REASON_TRANSFERRED
                integration.access_metadata = meta
            return _processed("repository", action, 1)

        if action == "edited" and "default_branch" in (payload.get("changes") or {}):
            new_default = repository.get("default_branch")
            if new_default and new_default != repo.default_branch:
                repo.default_branch = new_default
                return _processed("repository", action, 1)
            return _processed("repository", action, 0)
        return None


async def find_organization_for_installation(db: AsyncSession, installation_id: str) -> str | None:
    result = await db.execute(
        select(OrganizationIntegration.organization_id).where(
            OrganizationIntegration.installation_id == installation_id
        )
    )
    org_id = result.scalar_one_or_none()
    return str(org_id) if org_id is not None else None


__all__ = ["SUPPORTED_EVENTS", "GitHubLifecycleService", "find_organization_for_installation"]
