from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import github_state
from app.core.config import settings
from app.core.error_messages import GENERIC_EXTERNAL_SERVICE_ERROR
from app.core.github_state import GitHubStateError, verify_github_state
from app.db.session import get_db
from app.middleware.auth import UserContext, get_current_user
from app.middleware.redis_rate_limit import per_route_limiter
from app.schemas.github import (
    GitHubConnectRequest,
    GitHubInstallCallbackRequest,
    GitHubInstallUrlResponse,
    GitHubIntegrationResponse,
    GitHubOAuthCallbackRequest,
    GitHubRepoListResponse,
)
from app.services.github import GitHubService
from app.services.organizations import OrganizationService

router = APIRouter()


def _extract_org_id_from_state_or_400(state: str) -> UUID:
    try:
        encoded_payload, _encoded_signature = state.split(".", 1)
        payload = github_state.json.loads(github_state._urlsafe_b64decode(encoded_payload))
        return UUID(str(payload["org_id"]))
    except (ValueError, KeyError, TypeError, github_state.json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc


@router.get(
    "/organizations/{org_id}/github/install-url",
    response_model=GitHubInstallUrlResponse,
)
async def get_github_install_url(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    url = gh.get_install_url(org_id, current_user.user_id)
    return GitHubInstallUrlResponse(url=url)


@router.get(
    "/organizations/{org_id}/github/oauth/authorize",
    response_model=GitHubInstallUrlResponse,
)
async def get_github_oauth_authorize_url(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the GitHub OAuth authorize URL. The state param preserves org_id through the flow."""
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # The callback URL must match what's configured in the GitHub App settings
    frontend_base = settings.CORS_ORIGINS.split(",")[0].strip()
    callback_url = f"{frontend_base}/github/callback"

    gh = GitHubService(db)
    url = gh.get_oauth_authorize_url(org_id, current_user.user_id, callback_url)
    return GitHubInstallUrlResponse(url=url)


@router.post(
    "/github/oauth/callback",
    response_model=GitHubIntegrationResponse,
    dependencies=[Depends(per_route_limiter(10, 60, "github:oauth"))],
)
async def github_oauth_callback(
    data: GitHubOAuthCallbackRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle GitHub OAuth callback. Exchanges code for user token, finds installation, saves integration."""
    org_service = OrganizationService(db)
    org_id = _extract_org_id_from_state_or_400(data.state)

    try:
        verify_github_state(data.state, org_id=org_id, user_id=current_user.user_id, purpose="oauth")
    except GitHubStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc

    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["admin", "owner"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can connect GitHub",
        )

    frontend_base = settings.CORS_ORIGINS.split(",")[0].strip()
    callback_url = f"{frontend_base}/github/callback"

    gh = GitHubService(db)
    try:
        return await gh.handle_oauth_callback(data, callback_url, org_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=GENERIC_EXTERNAL_SERVICE_ERROR,
        ) from exc


@router.post(
    "/github/install/callback",
    response_model=GitHubIntegrationResponse,
    dependencies=[Depends(per_route_limiter(10, 60, "github:install"))],
)
async def github_install_callback(
    data: GitHubInstallCallbackRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org_id = _extract_org_id_from_state_or_400(data.state)

    try:
        verify_github_state(data.state, org_id=org_id, user_id=current_user.user_id, purpose="install")
    except GitHubStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid GitHub state") from exc

    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["admin", "owner"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can connect GitHub",
        )

    gh = GitHubService(db)
    return await gh.save_integration(
        org_id,
        GitHubConnectRequest(installation_id=data.installation_id, state=data.state),
    )


@router.post(
    "/organizations/{org_id}/github/connect",
    response_model=GitHubIntegrationResponse,
)
async def connect_github(
    org_id: UUID,
    data: GitHubConnectRequest,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["admin", "owner"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can connect GitHub",
        )

    try:
        verify_github_state(data.state, org_id=org_id, user_id=current_user.user_id, purpose="install")
    except GitHubStateError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    gh = GitHubService(db)
    return await gh.save_integration(org_id, data)


@router.get(
    "/organizations/{org_id}/github/repositories",
    response_model=GitHubRepoListResponse,
)
async def list_github_repositories(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    integration = await gh.get_integration(org_id)
    if not integration:
        raise HTTPException(
            status_code=404,
            detail="No GitHub integration found. Connect GitHub first.",
        )

    try:
        repos = await gh.list_repositories(integration.installation_id)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=GENERIC_EXTERNAL_SERVICE_ERROR,
        ) from exc
    return GitHubRepoListResponse(items=repos, total=len(repos))


@router.get(
    "/organizations/{org_id}/github/integration",
    response_model=GitHubIntegrationResponse | None,
)
async def get_github_integration(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    org = await org_service.get_by_id(org_id, current_user.user_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    gh = GitHubService(db)
    return await gh.get_integration(org_id)


@router.delete(
    "/organizations/{org_id}/github/integration",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_github(
    org_id: UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org_service = OrganizationService(db)
    has_permission = await org_service.user_has_permission(org_id, current_user.user_id, ["admin", "owner"])
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and owners can disconnect GitHub",
        )

    gh = GitHubService(db)
    deleted = await gh.delete_integration(org_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No GitHub integration found")
