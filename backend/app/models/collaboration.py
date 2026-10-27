import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, Enum, DateTime, UniqueConstraint, CheckConstraint, Index, func, text
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

    # SRS BR-014: mutual. Store the pair once, ordered faculty_a < faculty_b.
    __table_args__ = (
        UniqueConstraint("faculty_a", "faculty_b", name="uq_collaboration_pair"),
        CheckConstraint("faculty_a < faculty_b", name="ck_collaboration_ordered_pair"),
    )