from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportCreate(BaseModel):
    project_id: UUID
    export_type: str = Field(..., pattern="^(findings|pipeline|summary)$")
    format: str = Field(..., pattern="^(csv|json|pdf)$")
    filters: dict | None = None
    title: str | None = Field(None, max_length=255)


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    organization_id: UUID
    export_type: str
    format: str
    status: str
    title: str | None
    storage_uri: str | None
    file_name: str | None
    size_bytes: int | None
    created_by_user_id: UUID | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
