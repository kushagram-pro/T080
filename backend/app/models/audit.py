import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Text, ForeignKey, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    account_approved    = "account_approved"
    account_rejected    = "account_rejected"
    account_created     = "account_created"
    account_activated   = "account_activated"
    account_deactivated = "account_deactivated"
    role_changed        = "role_changed"
    department_created  = "department_created"
    department_updated  = "department_updated"
    department_deleted  = "department_deleted"
    password_reset_sent = "password_reset_sent"


class AuditLog(Base):
    """NFR-008 / SRS 15.10: record of significant administrative actions."""
    __tablename__ = "audit_logs"

    id:             Mapped[int]         = mapped_column(primary_key=True, index=True)
    actor_id:       Mapped[int | None]  = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action:         Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False, index=True)
    target_user_id: Mapped[int | None]  = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    details:        Mapped[str | None]  = mapped_column(Text, nullable=True)
    created_at:     Mapped[datetime]    = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor:       Mapped["User | None"] = relationship("User", foreign_keys=[actor_id])
    target_user: Mapped["User | None"] = relationship("User", foreign_keys=[target_user_id])
