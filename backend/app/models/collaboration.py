import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, Enum, DateTime, CheckConstraint, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class RequestStatus(str, enum.Enum):
    pending   = "pending"
    accepted  = "accepted"
    declined  = "declined"
    withdrawn = "withdrawn"

class CollaborationRequest(Base):
    __tablename__ = "collaboration_requests"

    id:           Mapped[int]           = mapped_column(primary_key=True, index=True)
    sender_id:    Mapped[int]           = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    recipient_id: Mapped[int]           = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    message:      Mapped[str | None]    = mapped_column(Text, nullable=True)
    status:       Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.pending, nullable=False)
    sent_at:      Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # SRS BR-010: at most one PENDING request between two faculty, in either direction.
    # Declined/withdrawn rows are history and must not block a fresh request.
    __table_args__ = (
        Index(
            "uq_collab_request_pending_pair",
            func.least(sender_id, recipient_id),
            func.greatest(sender_id, recipient_id),
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        CheckConstraint("sender_id <> recipient_id", name="ck_collab_request_not_self"),  # SRS BR-009
    )

    sender:    Mapped["User"] = relationship("User", foreign_keys=[sender_id],    back_populates="sent_requests")
    recipient: Mapped["User"] = relationship("User", foreign_keys=[recipient_id], back_populates="received_requests")

class Collaboration(Base):
    __tablename__ = "collaborations"

    id:         Mapped[int]      = mapped_column(primary_key=True, index=True)
    request_id: Mapped[int]      = mapped_column(ForeignKey("collaboration_requests.id"), unique=True, nullable=False)
    faculty_a:  Mapped[int]      = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    faculty_b:  Mapped[int]      = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # Either person can end a collaboration. The row is kept (with its messages) as history,
    # and the pair can collaborate again later through a new request.
    ended_at:   Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_by:   Mapped[int | None]      = mapped_column(ForeignKey("users.id", name="collaborations_ended_by_fkey"), nullable=True)

    # SRS BR-014: mutual. Store the pair once, ordered faculty_a < faculty_b; at most one
    # ongoing collaboration per pair (ended ones are history and don't count).
    __table_args__ = (
        Index(
            "uq_collaboration_active_pair", "faculty_a", "faculty_b",
            unique=True, postgresql_where=text("ended_at IS NULL"),
        ),
        CheckConstraint("faculty_a < faculty_b", name="ck_collaboration_ordered_pair"),
    )

    messages: Mapped[list["CollaborationMessage"]] = relationship(
        "CollaborationMessage", back_populates="collaboration", order_by="CollaborationMessage.id",
        cascade="all, delete-orphan", passive_deletes=True,
    )

    @property
    def is_active(self) -> bool:
        return self.ended_at is None

    def other(self, user_id: int) -> int:
        return self.faculty_b if self.faculty_a == user_id else self.faculty_a


class CollaborationMessage(Base):
    """A message between the two people in a collaboration."""
    __tablename__ = "collaboration_messages"

    id:               Mapped[int]             = mapped_column(primary_key=True)
    collaboration_id: Mapped[int]             = mapped_column(ForeignKey("collaborations.id", ondelete="CASCADE"), nullable=False)
    sender_id:        Mapped[int]             = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    body:             Mapped[str]             = mapped_column(Text, nullable=False)
    created_at:       Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    read_at:          Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # by the other person

    __table_args__ = (Index("ix_collab_messages_collab_id", "collaboration_id", "id"),)

    collaboration: Mapped["Collaboration"] = relationship("Collaboration", back_populates="messages")