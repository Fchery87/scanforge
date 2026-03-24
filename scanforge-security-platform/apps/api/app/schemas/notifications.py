from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    notification_type: str
    title: str
    body: str | None
    is_read: bool
    link: str | None
    metadata_json: dict | None
    created_at: datetime


class NotificationMarkRead(BaseModel):
    notification_ids: list[UUID] = Field(..., min_length=1)


class NotificationCreate(BaseModel):
    user_id: UUID
    notification_type: str
    title: str
    body: str | None = None
    link: str | None = None
    metadata_json: dict | None = None
