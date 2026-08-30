from uuid import UUID

from pydantic import BaseModel, Field


class WorkerIdentityCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=120)
    capabilities: set[str] = Field(default_factory=lambda: {"scan:execute"})
