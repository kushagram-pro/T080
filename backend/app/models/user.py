import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Enum, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.profile import Department, FacultyProfile
    from app.models.collaboration import CollaborationRequest
    from app.models.notification import Notification

class UserRole(str, enum.Enum):
    faculty = "faculty"
    admin = "admin"
    research_admin = "research_admin"
    dept_mgmt = "dept_mgmt"

class UserStatus(str, enum.Enum):
    pending = "pending"     #self registered, awaiting admin approval
    active = "active"       #approved, can log in   
    inactive = "inactive"   #deactivated by admin

class User(Base):
    __tablename__ = "users"

    id:               Mapped[int]      = mapped_column(primary_key=True, index=True)
    email:            Mapped[str]      = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name:        Mapped[str]      = mapped_column(String(150), nullable=False)
    hashed_password:  Mapped[str]      = mapped_column(String(255), nullable=False)
    role:             Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.faculty, nullable=False)
    status:           Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.pending, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Department Management users are scoped to one department (SRS 11.4 / FR-044).
    # Faculty keep their department on their profile instead.
    department_id:    Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    created_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at:       Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile:           Mapped["FacultyProfile"]          = relationship("FacultyProfile", back_populates="user", uselist=False)
    managed_department: Mapped["Department | None"]     = relationship("Department", foreign_keys=[department_id])
    sent_requests:     Mapped[list["CollaborationRequest"]] = relationship("CollaborationRequest", foreign_keys="CollaborationRequest.sender_id", back_populates="sender")
    received_requests: Mapped[list["CollaborationRequest"]] = relationship("CollaborationRequest", foreign_keys="CollaborationRequest.recipient_id", back_populates="recipient")
    notifications:     Mapped[list["Notification"]]      = relationship("Notification", back_populates="recipient")
