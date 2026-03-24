from uuid import UUID

from pydantic import BaseModel


class GitHubInstallUrlResponse(BaseModel):
    url: str


class GitHubConnectRequest(BaseModel):
    installation_id: str
    account_login: str | None = None
    account_type: str | None = None


class GitHubOAuthCallbackRequest(BaseModel):
    code: str
    state: str


class GitHubIntegrationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    provider: str
    installation_id: str
    account_login: str | None
    account_type: str | None

    model_config = {"from_attributes": True}


class GitHubRepoItem(BaseModel):
    external_repo_id: str
    owner_name: str
    repo_name: str
    full_name: str
    default_branch: str | None
    clone_url: str | None
    html_url: str | None
    private: bool


class GitHubRepoListResponse(BaseModel):
    items: list[GitHubRepoItem]
    total: int
