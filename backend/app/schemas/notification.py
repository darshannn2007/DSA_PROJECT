"""Notification schemas."""
from datetime import datetime
from pydantic import BaseModel
from backend.app.schemas.profile import ProfileSummary


class NotificationResponse(BaseModel):
    id: int
    type: str
    actor: ProfileSummary | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    created_at: datetime
    read_at: datetime | None = None


class NotificationList(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
