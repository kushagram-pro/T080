import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, Enum, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

# SRS BR-018 lists received / accepted / declined. request_cancelled was added at the team's
# request: a pending request is withdrawn automatically when the other person is deactivated.
# Account approval/rejection is communicated by email only.
class NotificationType(str, enum.Enum):
    request_received  = "request_received"
    request_accepted  = "request_accepted"
    request_declined  = "request_declined"
    request_cancelled = "request_cancelled"

class Notification(Base):
    __tablename__ = "notifications"

    id:           Mapped[int]              = mapped_column(primary_key=True, index=True)
    recipient_id: Mapped[int]              = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type:         Mapped[NotificationType] = mapped_column(Enum(NotificationType), nullable=False)
    message:      Mapped[str]              = mapped_column(Text, nullable=False)
    # The request this is about, so the UI can link to it. Kept if the request row ever goes.
    request_id:   Mapped[int | None]       = mapped_column(ForeignKey("collaboration_requests.id", ondelete="SET NULL"), nullable=True)
    is_read:      Mapped[bool]             = mapped_column(Boolean, default=False, nullable=False)
    created_at:   Mapped[datetime]         = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_notifications_recipient_created", "recipient_id", "created_at"),)

    recipient: Mapped["User"] = relationship("User", back_populates="notifications")