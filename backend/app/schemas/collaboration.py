from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models import NotificationType, RequestStatus

MESSAGE_MAX = 500  # FR-027 / AC-006


class RequestCreate(BaseModel):
    recipient_id: int
    message: str | None = Field(default=None, max_length=MESSAGE_MAX)

    @field_validator("message")
    @classmethod
    def clean(cls, v):
        if v is None:
            return None
        v = v.strip()
        return v or None


class Party(BaseModel):
    """The other faculty member on a request or collaboration."""
    user_id: int
    full_name: str
    designation: str | None
    department: str | None


class RequestOut(BaseModel):
    id: int
    direction: Literal["sent", "received"]  # from the viewer's point of view
    other: Party
    message: str | None
    status: RequestStatus
    sent_at: datetime
    responded_at: datetime | None


class CollaboratorOut(BaseModel):
    """FR / dashboard "My Collaborators": a mutual collaboration (BR-014)."""
    collaboration_id: int
    other: Party
    since: datetime


class RelationshipOut(BaseModel):
    """What the profile page should offer: Send, Withdraw, Accept/Decline, or nothing."""
    state: Literal["none", "pending_sent", "pending_received", "collaborators"]
    request_id: int | None = None


class NotificationOut(BaseModel):
    id: int
    type: NotificationType
    message: str
    request_id: int | None
    is_read: bool
    created_at: datetime


class NotificationPage(BaseModel):
    unread_count: int
    total: int
    page: int
    page_size: int
    results: list[NotificationOut]
