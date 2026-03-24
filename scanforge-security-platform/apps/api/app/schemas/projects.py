from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    default_branch: str | None = Field(None, max_length=255)


class ProjectCreate(ProjectBase):
    organization_id: UUID


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    slug: str | None = Field(None, min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    default_branch: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None
    default_branch: str | None
    is_active: bool
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectWithStats(ProjectResponse):
    repo_count: int = 0
    scan_count: int = 0
    open_findings_count: int = 0
    critical_findings_count: int = 0
