from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RepositoryProvider(str):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    MANUAL = "manual"


class RepositoryConnect(BaseModel):
    provider: str = Field(..., pattern="^(github|gitlab|bitbucket|manual)$")
    external_repo_id: str | None = None
    owner_name: str = Field(..., min_length=1, max_length=255)
    repo_name: str = Field(..., min_length=1, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    default_branch: str | None = Field(None, max_length=255)
    clone_url: str | None = Field(None, max_length=1024)
    html_url: str | None = Field(None, max_length=1024)
    installation_id: str | None = None
    provider_account_id: str | None = None


class RepositoryUpdate(BaseModel):
    default_branch: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    provider: str
    external_repo_id: str | None
    owner_name: str
    repo_name: str
    full_name: str
    default_branch: str | None
    clone_url: str | None
    html_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RepositoryWithIntegration(RepositoryResponse):
    has_github_app: bool = False
    installation_id: str | None = None


class RepositoryDisconnect(BaseModel):
    reason: str | None = None
