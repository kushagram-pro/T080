from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import AuditAction, UserRole, UserStatus
from app.schemas.auth import check_password_strength


class PendingUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    created_at: datetime
    submitted_at: datetime = Field(validation_alias="updated_at")  # differs from created_at after a re-application


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("A reason is required when rejecting a registration")
        return v


# ---------- Account management (FR-005 / FR-007 / FR-038) ----------

def _clean_name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Full name is required")
    return v


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    status: UserStatus
    department_id: int | None    # managed department (Department Management) or profile department (faculty)
    department_name: str | None
    has_profile: bool
    rejection_reason: str | None
    created_at: datetime


class AdminUserPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AdminUserOut]


class AdminUserCreate(BaseModel):
    """Accounts made by an admin are active straight away (no approval step)."""
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8)  # initial password; the user can change it after logging in
    role: UserRole = UserRole.faculty
    department_id: int | None = None   # required for Department Management

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name")
    @classmethod
    def name(cls, v: str) -> str:
        return _clean_name(v)

    @field_validator("password")
    @classmethod
    def password_rules(cls, v: str) -> str:
        return check_password_strength(v)


class AdminUserUpdate(BaseModel):
    """Only the fields sent are changed."""
    full_name: str | None = Field(default=None, max_length=150)
    role: UserRole | None = None
    department_id: int | None = None  # send null to clear

    @field_validator("full_name")
    @classmethod
    def name(cls, v):
        return None if v is None else _clean_name(v)


class AdminDashboard(BaseModel):
    """FR-040."""
    registered_faculty: int
    active_collaborations: int
    pending_requests: int
    pending_registrations: int
    departments: int
    inactive_accounts: int
    incomplete_profiles: int


class AuditEntryOut(BaseModel):
    id: int
    action: AuditAction
    actor_name: str | None
    target_name: str | None
    target_email: str | None
    details: str | None
    created_at: datetime


class AuditPage(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AuditEntryOut]
