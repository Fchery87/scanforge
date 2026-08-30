import logging
import time
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
        """Exchange OAuth code for user token, get installation, and save integration."""
        user_token = await self._exchange_code_for_user_token(data.code, callback_url)
        install = await self._get_user_installation(user_token)

        connect_data = GitHubConnectRequest(
            installation_id=str(install["id"]),
            state="",
            account_login=install.get("account", {}).get("login"),
            account_type=install.get("account", {}).get("type"),
        )
        return await self.save_integration(org_id, connect_data)

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

    async def _get_user_installation(self, user_token: str) -> dict:
        """Get the GitHub App installation for the authenticated user."""
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
                raise Exception("No GitHub App installation found. Please install the app first.")
            return installations[0]

    async def _get_installation_details(self, installation_id: str) -> dict:
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
    ) -> OrganizationIntegration:
        account_login = data.account_login
        account_type = data.account_type

        # Fetch account details from GitHub if not provided by the client
        if not account_login:
            try:
                details = await self._get_installation_details(data.installation_id)
                account = details.get("account", {})
                account_login = account.get("login")
                account_type = account.get("type")
            except Exception:
                logger.warning("Could not fetch installation details from GitHub", exc_info=True)

        result = await self.db.execute(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == org_id)
        )
        integration = result.scalar_one_or_none()

        if integration:
            integration.installation_id = data.installation_id
            integration.account_login = account_login
            integration.account_type = account_type
        else:
            integration = OrganizationIntegration(
                organization_id=org_id,
                provider="github",
                installation_id=data.installation_id,
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
        return response.status_code == httpx.codes.OK

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
