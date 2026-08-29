from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkerIdentityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    capabilities: set[str] = Field(default_factory=set)


class WorkerIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    capabilities_json: list[str]
    disabled_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerCredentialIssue(BaseModel):
    worker_id: UUID
    credential: str
