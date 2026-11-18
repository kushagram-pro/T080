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
    """FR / dashboard "My Collaborators": a mutual collaboration (BR-014), ongoing or ended."""
    collaboration_id: int
    request_id: int          # the request that started it; notifications link to it
    other: Party
    since: datetime
    ended_at: datetime | None
    ended_by_me: bool
    unread_messages: int


class RelationshipOut(BaseModel):
    """What the profile page should offer: Send, Withdraw, Accept/Decline, or nothing."""
    state: Literal["none", "pending_sent", "pending_received", "collaborators"]
    request_id: int | None = None
    collaboration_id: int | None = None


# ---------- Messages ----------

CHAT_MESSAGE_MAX = 2000


class ChatMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=CHAT_MESSAGE_MAX)

    @field_validator("body")
    @classmethod
    def clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Write a message first")
        return v


class ChatMessageOut(BaseModel):
    id: int
    sender_id: int
    mine: bool
    body: str
    created_at: datetime
    read_at: datetime | None


class ChatThreadOut(BaseModel):
    collaboration_id: int
    other: Party
    ended_at: datetime | None
    can_send: bool                  # ongoing, and the other person's account is active
    messages: list[ChatMessageOut]  # oldest first
    has_more: bool                  # older messages exist (pass before_id to load them)


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
