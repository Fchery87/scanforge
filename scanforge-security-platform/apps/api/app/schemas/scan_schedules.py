from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScanScheduleCreate(BaseModel):
    schedule_type: str = Field(..., pattern="^(daily|weekly|on_push)$")
    cron_expression: str | None = Field(None, max_length=100)
    scan_type: str = Field(default="full", pattern="^(full|diff|dependencies|secrets)$")
    is_active: bool = True


class ScanScheduleUpdate(BaseModel):
    schedule_type: str | None = Field(None, pattern="^(daily|weekly|on_push)$")
    cron_expression: str | None = Field(None, max_length=100)
    scan_type: str | None = Field(None, pattern="^(full|diff|dependencies|secrets)$")
    is_active: bool | None = None


class ScanScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    schedule_type: str
    cron_expression: str | None
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    scan_type: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
