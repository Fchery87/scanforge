import logging
import time
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.github_state import issue_github_state
from app.db.models.organization import OrganizationIntegration
from app.schemas.github import GitHubConnectRequest, GitHubOAuthCallbackRequest, GitHubRepoItem

logger = logging.getLogger(__name__)
GIT_COMMIT_SHA_LENGTH = 40


class GitHubInstallationAccessError(PermissionError):
    """Raised when the connecting user or installation lacks verified GitHub authority."""

    code = "github_installation_access_denied"


class GitHubInstallationConflictError(ValueError):
    """Raised when a GitHub installation is already bound to another ScanForge organization."""

    code = "github_installation_already_bound"


class GitHubRevisionNotFoundError(LookupError):
    """Raised when a branch ref or exact commit SHA cannot be verified in GitHub."""

    code = "github_revision_not_found"


def _make_app_jwt() -> str:
    """Create a signed JWT to authenticate as the GitHub App."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": settings.GITHUB_APP_ID,
    }
    private_key = settings.GITHUB_PRIVATE_KEY.replace("\\n", "\n")
    return jwt.encode(payload, private_key, algorithm="RS256")


class GitHubService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def get_install_url(self, org_id: UUID, user_id: UUID) -> str:
        state = issue_github_state(org_id, user_id, "install")
        return f"https://github.com/apps/{settings.GITHUB_APP_SLUG}/installations/new?state={state}"

    def get_oauth_authorize_url(self, org_id: UUID, user_id: UUID, callback_url: str) -> str:
        """Build GitHub OAuth authorize URL. The state parameter (org_id) is preserved by GitHub."""
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": callback_url,
            "state": issue_github_state(org_id, user_id, "oauth"),
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def handle_oauth_callback(
        self, data: GitHubOAuthCallbackRequest, callback_url: str, org_id: UUID
    ) -> OrganizationIntegration:
        """Exchange OAuth code for user token, verify user installation access, and save integration."""
        user_token = await self._exchange_code_for_user_token(data.code, callback_url)
        requested_installation_id = getattr(data, "installation_id", None)
        install = await self._get_user_installation(
            user_token,
            installation_id=requested_installation_id,
        )

        connect_data = GitHubConnectRequest(
            installation_id=str(install["id"]),
            state="",
            account_login=install.get("account", {}).get("login"),
            account_type=install.get("account", {}).get("type"),
        )
        return await self.save_integration(
            org_id,
            connect_data,
            verified_installation=install,
        )

    async def _exchange_code_for_user_token(self, code: str, redirect_uri: str) -> str:
        """Exchange OAuth authorization code for a user access token."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            body = resp.json()
            if "error" in body:
                raise Exception(body.get("error_description", body["error"]))
            return body["access_token"]

    async def _get_user_installation(
        self,
        user_token: str,
        installation_id: str | None = None,
    ) -> dict[str, Any]:
        """Verify and return a GitHub App installation accessible to the authenticated user."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user/installations",
                headers={
                    "Authorization": f"Bearer {user_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            installations = data.get("installations", [])
            if not installations:
                raise GitHubInstallationAccessError(
                    "No GitHub App installation found for the connecting user."
                )
            if installation_id is not None:
                for inst in installations:
                    if str(inst.get("id")) == str(installation_id):
                        return inst
                raise GitHubInstallationAccessError(
                    "Connecting user does not have access to the requested GitHub installation."
                )
            return installations[0]

    async def _get_installation_details(self, installation_id: str) -> dict[str, Any]:
        """Fetch installation details from GitHub using the App JWT."""
        app_jwt = _make_app_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/app/installations/{installation_id}",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def save_integration(
        self,
        org_id: UUID,
        data: GitHubConnectRequest,
        *,
        user_token: str | None = None,
        verified_installation: dict[str, Any] | None = None,
    ) -> OrganizationIntegration:
        installation_id = str(data.installation_id).strip()
        if not installation_id:
            raise GitHubInstallationAccessError("GitHub installation_id is required")

        # 1. Enforce 1:1 installation-to-organization binding before reserving or mutating state
        existing_installation_result = await self.db.execute(
            select(OrganizationIntegration).where(
                OrganizationIntegration.installation_id == installation_id
            )
        )
        for bound in existing_installation_result.scalars().all():
            if str(bound.organization_id) != str(org_id):
                raise GitHubInstallationConflictError(
                    "GitHub installation is already bound to another organization"
                )

        # 2. Verify installation authority before persisting binding
        details = verified_installation
        effective_user_token = user_token or getattr(data, "user_token", None)
        if details is None:
            if effective_user_token:
                details = await self._get_user_installation(
                    effective_user_token,
                    installation_id=installation_id,
                )
            else:
                try:
                    details = await self._get_installation_details(installation_id)
                except Exception as exc:
                    logger.warning("Could not verify installation details from GitHub", exc_info=True)
                    raise GitHubInstallationAccessError(
                        "Unable to verify GitHub installation access"
                    ) from exc

        if not isinstance(details, dict):
            raise GitHubInstallationAccessError("Invalid GitHub installation verification response")
        if details.get("id") is not None and str(details["id"]) != installation_id:
            raise GitHubInstallationAccessError(
                "Verified GitHub installation ID does not match requested installation"
            )

        account = details.get("account") or {}
        account_login = account.get("login") or data.account_login
        account_type = account.get("type") or data.account_type

        result = await self.db.execute(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == org_id)
        )
        integration = result.scalar_one_or_none()

        if integration:
            integration.installation_id = installation_id
            integration.account_login = account_login
            integration.account_type = account_type
        else:
            integration = OrganizationIntegration(
                organization_id=org_id,
                provider="github",
                installation_id=installation_id,
                account_login=account_login,
                account_type=account_type,
            )
            self.db.add(integration)

        await self.db.commit()
        await self.db.refresh(integration)
        return integration

    async def get_integration(self, org_id: UUID) -> OrganizationIntegration | None:
        result = await self.db.execute(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def delete_integration(self, org_id: UUID) -> bool:
        integration = await self.get_integration(org_id)
        if not integration:
            return False
        await self.db.delete(integration)
        await self.db.commit()
        return True

    async def _get_installation_token(self, installation_id: str) -> str:
        """Exchange App JWT for an installation access token."""
        try:
            app_jwt = _make_app_jwt()
        except Exception:
            logger.error("Failed to create GitHub App JWT — check GITHUB_APP_ID and GITHUB_PRIVATE_KEY", exc_info=True)
            raise

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            if not resp.is_success:
                logger.error(
                    "GitHub installation token exchange failed: %s %s",
                    resp.status_code,
                    resp.text,
                )
            resp.raise_for_status()
            return resp.json()["token"]

    async def repository_is_accessible(
        self,
        installation_id: str,
        owner_name: str,
        repo_name: str,
        *,
        expected_external_repo_id: str | None = None,
    ) -> bool:
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(
                f"https://api.github.com/repos/{owner_name}/{repo_name}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if response.status_code != httpx.codes.OK:
            return False
        if expected_external_repo_id is not None:
            try:
                payload = response.json()
            except Exception:
                return False
            if isinstance(payload, dict) and payload.get("id") is not None:
                return str(payload["id"]) == str(expected_external_repo_id)
        return True

    async def get_installation_repository(
        self,
        installation_id: str,
        *,
        external_repo_id: str | None = None,
        owner_name: str | None = None,
        repo_name: str | None = None,
        full_name: str | None = None,
    ) -> dict[str, Any]:
        """Verify that a repository belongs to `installation_id` and return immutable provider metadata."""
        repos = await self.list_repositories(installation_id)
        matched: GitHubRepoItem | None = None
        for item in repos:
            if external_repo_id and str(item.external_repo_id) == str(external_repo_id):
                matched = item
                break
            if full_name and item.full_name.lower() == full_name.lower():
                matched = item
                break
            if (
                owner_name
                and repo_name
                and f"{item.owner_name}/{item.repo_name}".lower() == f"{owner_name}/{repo_name}".lower()
            ):
                matched = item
                break

        if matched is None:
            raise GitHubInstallationAccessError(
                "Repository is not accessible under the organization's verified GitHub installation"
            )
        if external_repo_id and str(matched.external_repo_id) != str(external_repo_id):
            raise GitHubInstallationAccessError(
                "Repository immutable provider ID does not match requested external_repo_id"
            )
        return {
            "external_repo_id": str(matched.external_repo_id),
            "owner_name": matched.owner_name,
            "repo_name": matched.repo_name,
            "full_name": matched.full_name,
            "default_branch": matched.default_branch,
            "clone_url": matched.clone_url or f"https://github.com/{matched.full_name}.git",
            "html_url": matched.html_url or f"https://github.com/{matched.full_name}",
        }

    async def resolve_branch_commit(
        self,
        installation_id: str,
        owner_name: str,
        repo_name: str,
        branch_name: str,
        *,
        expected_commit_sha: str | None = None,
    ) -> str:
        """Resolve or verify an exact 40-character commit SHA in GitHub."""
        token = await self._get_installation_token(installation_id)
        target_ref = expected_commit_sha or f"heads/{branch_name}"
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner_name}/{repo_name}/commits/{target_ref}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if resp.status_code != httpx.codes.OK:
            raise GitHubRevisionNotFoundError(
                f"Revision {target_ref!r} is not accessible in {owner_name}/{repo_name}"
            )
        body = resp.json()
        resolved_sha = str(body.get("sha") or "").strip().lower()
        if len(resolved_sha) != GIT_COMMIT_SHA_LENGTH:
            raise GitHubRevisionNotFoundError("GitHub did not return a 40-character commit SHA")
        if expected_commit_sha and resolved_sha != expected_commit_sha.strip().lower():
            raise GitHubRevisionNotFoundError(
                f"Resolved commit {resolved_sha} does not match expected {expected_commit_sha}"
            )
        return resolved_sha

    async def compare_commits(
        self,
        installation_id: str,
        owner_name: str,
        repo_name: str,
        base_sha: str,
        head_sha: str,
    ) -> dict[str, Any]:
        """Return a provider-backed ancestry comparison receipt between `base_sha` and `head_sha`."""
        token = await self._get_installation_token(installation_id)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner_name}/{repo_name}/compare/{base_sha}...{head_sha}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        if resp.status_code != httpx.codes.OK:
            return {
                "status": "unknown",
                "base_sha": base_sha,
                "head_sha": head_sha,
                "http_status": resp.status_code,
            }
        body = resp.json()
        return {
            "status": str(body.get("status") or "unknown"),
            "ahead_by": int(body.get("ahead_by") or 0),
            "behind_by": int(body.get("behind_by") or 0),
            "base_sha": base_sha,
            "head_sha": head_sha,
            "merge_base_sha": (body.get("merge_base_commit") or {}).get("sha"),
        }

    async def list_repositories(self, installation_id: str, per_page: int = 100) -> list[GitHubRepoItem]:
        token = await self._get_installation_token(installation_id)
        repos: list[GitHubRepoItem] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    "https://api.github.com/installation/repositories",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"per_page": per_page, "page": page},
                )
                if not resp.is_success:
                    logger.error(
                        "GitHub list repositories failed: %s %s",
                        resp.status_code,
                        resp.text,
                    )
                resp.raise_for_status()
                data = resp.json()
                for r in data.get("repositories", []):
                    repos.append(
                        GitHubRepoItem(
                            external_repo_id=str(r["id"]),
                            owner_name=r["owner"]["login"],
                            repo_name=r["name"],
                            full_name=r["full_name"],
                            default_branch=r.get("default_branch"),
                            clone_url=r.get("clone_url"),
                            html_url=r.get("html_url"),
                            private=r.get("private", False),
                        )
                    )
                if len(data.get("repositories", [])) < per_page:
                    break
                page += 1

        return repos
