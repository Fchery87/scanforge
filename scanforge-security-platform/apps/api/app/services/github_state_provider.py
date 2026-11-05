"""GitHub App adapter for `GitHubStateProvider` (#54).

Wraps the existing `GitHubService` calls. Network failures and unexpected statuses become
`GitHubProviderError` with a stable code so receipts never carry response bodies or tokens.
A 404 for the installation means it is gone; every other failure means "unknown", which the
reconciler treats as no change.

Not exercised against live GitHub: live App verification is recorded as not run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx

from app.services.github import GitHubRevisionNotFoundError, GitHubService
from app.services.github_reconciliation import GitHubProviderError, InstallationSnapshot, RepositorySnapshot

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class GitHubAppStateProvider:
    def __init__(self, db: AsyncSession, service: GitHubService | None = None):
        self._service = service or GitHubService(db)

    async def get_installation(self, installation_id: str) -> InstallationSnapshot | None:
        try:
            details = await self._service._get_installation_details(installation_id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.NOT_FOUND:
                return None
            raise GitHubProviderError(f"github_http_{exc.response.status_code}") from None
        except httpx.HTTPError as exc:
            raise GitHubProviderError("github_unreachable", type(exc).__name__) from None
        return InstallationSnapshot(
            suspended=bool(details.get("suspended_at")),
            permissions=dict(details.get("permissions") or {}),
        )

    async def list_repositories(self, installation_id: str) -> list[RepositorySnapshot]:
        try:
            items = await self._service.list_repositories(installation_id)
        except httpx.HTTPStatusError as exc:
            raise GitHubProviderError(f"github_http_{exc.response.status_code}") from None
        except httpx.HTTPError as exc:
            raise GitHubProviderError("github_unreachable", type(exc).__name__) from None
        return [
            RepositorySnapshot(
                external_repo_id=str(item.external_repo_id),
                owner_name=item.owner_name,
                repo_name=item.repo_name,
                full_name=item.full_name,
                default_branch=item.default_branch,
            )
            for item in items
        ]

    async def resolve_head(self, installation_id: str, owner_name: str, repo_name: str, branch_name: str) -> str:
        try:
            return await self._service.resolve_branch_commit(installation_id, owner_name, repo_name, branch_name)
        except GitHubRevisionNotFoundError:
            raise GitHubProviderError("head_not_found") from None
        except httpx.HTTPError as exc:
            raise GitHubProviderError("github_unreachable", type(exc).__name__) from None

    async def compare_commits(
        self, installation_id: str, owner_name: str, repo_name: str, base_sha: str, head_sha: str
    ) -> dict[str, Any]:
        try:
            return await self._service.compare_commits(installation_id, owner_name, repo_name, base_sha, head_sha)
        except httpx.HTTPError as exc:
            raise GitHubProviderError("github_unreachable", type(exc).__name__) from None
