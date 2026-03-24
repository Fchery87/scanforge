import time
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.organization import OrganizationIntegration
from app.schemas.github import GitHubConnectRequest, GitHubOAuthCallbackRequest, GitHubRepoItem


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

    def get_install_url(self, org_id: str) -> str:
        state = org_id
        return f"https://github.com/apps/{settings.GITHUB_APP_SLUG}/installations/new?state={state}"

    def get_oauth_authorize_url(self, org_id: str, callback_url: str) -> str:
        """Build GitHub OAuth authorize URL. The state parameter (org_id) is preserved by GitHub."""
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": callback_url,
            "state": org_id,
        }
        return f"https://github.com/login/oauth/authorize?{urlencode(params)}"

    async def handle_oauth_callback(
        self, data: GitHubOAuthCallbackRequest, callback_url: str
    ) -> OrganizationIntegration:
        """Exchange OAuth code for user token, get installation, and save integration."""
        user_token = await self._exchange_code_for_user_token(data.code, callback_url)
        install = await self._get_user_installation(user_token)

        connect_data = GitHubConnectRequest(
            installation_id=str(install["id"]),
            account_login=install.get("account", {}).get("login"),
            account_type=install.get("account", {}).get("type"),
        )
        return await self.save_integration(UUID(data.state), connect_data)

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

    async def save_integration(
        self,
        org_id: UUID,
        data: GitHubConnectRequest,
    ) -> OrganizationIntegration:
        result = await self.db.execute(
            select(OrganizationIntegration).where(OrganizationIntegration.organization_id == org_id)
        )
        integration = result.scalar_one_or_none()

        if integration:
            integration.installation_id = data.installation_id
            integration.account_login = data.account_login
            integration.account_type = data.account_type
        else:
            integration = OrganizationIntegration(
                organization_id=org_id,
                provider="github",
                installation_id=data.installation_id,
                account_login=data.account_login,
                account_type=data.account_type,
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
        app_jwt = _make_app_jwt()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            return resp.json()["token"]

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
