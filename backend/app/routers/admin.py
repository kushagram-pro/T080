from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, selectinload

from app.config import settings
from app.database import get_db
from app.dependencies.auth import require_admin
from app.models import (
    AuditAction,
    AuditLog,
    Collaboration,
    CollaborationRequest,
    Department,
    FacultyProfile,
    RequestStatus,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.admin import (
    AdminDashboard,
    AdminUserCreate,
    AdminUserOut,
    AdminUserPage,
    AdminUserUpdate,
    AuditEntryOut,
    AuditPage,
)
from app.schemas.auth import MessageResponse
from app.security import email
from app.security.hashing import hash_password
from app.services import audit, password_reset, sessions
from app.services.collaboration import cancel_pending_for
from app.services.discovery import is_discoverable_sql

router = APIRouter(prefix="/admin", tags=["admin"])

ROLE_LABEL = {
    UserRole.faculty: "Faculty",
    UserRole.admin: "Administrator",
    UserRole.research_admin: "Research Admin",
    UserRole.dept_mgmt: "Department Management",
}


def _field_error(field: str, msg: str):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[{"loc": ["body", field], "msg": msg, "type": "value_error"}],
    )


def _to_out(u: User) -> AdminUserOut:
    if u.role == UserRole.dept_mgmt and u.managed_department:
        dept = u.managed_department
    elif u.profile and u.profile.department:
        dept = u.profile.department
    else:
        dept = None
    return AdminUserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        status=u.status,
        department_id=dept.id if dept else None,
        department_name=dept.name if dept else None,
        has_profile=u.profile is not None,
        rejection_reason=u.rejection_reason,
        created_at=u.created_at,
    )


def _load_user(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.profile).selectinload(FacultyProfile.department),
            selectinload(User.managed_department),
        )
        .with_for_update(of=User)
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _active_admins(db: Session) -> int:
    return db.scalar(
        select(func.count(User.id)).where(User.role == UserRole.admin, User.status == UserStatus.active)
    )


def _check_department(db: Session, role: UserRole, department_id: int | None) -> None:
    if role == UserRole.dept_mgmt:
        if department_id is None:
            _field_error("department_id", "Department Management accounts need a department")
        if db.get(Department, department_id) is None:
            _field_error("department_id", "Please choose a department from the list")


# ---------- Dashboard (FR-040) ----------

@router.get("/dashboard", response_model=AdminDashboard)
def dashboard(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    active_faculty = select(User.id).where(User.role == UserRole.faculty, User.status == UserStatus.active)
    a, b = aliased(User), aliased(User)
    return AdminDashboard(
        registered_faculty=db.scalar(select(func.count()).select_from(active_faculty.subquery())),
        # Only collaborations where both people are still active count as "active connections"
        active_collaborations=db.scalar(
            select(func.count(Collaboration.id))
            .join(a, a.id == Collaboration.faculty_a)
            .join(b, b.id == Collaboration.faculty_b)
            .where(a.status == UserStatus.active, b.status == UserStatus.active)
        ),
        pending_requests=db.scalar(
            select(func.count(CollaborationRequest.id)).where(CollaborationRequest.status == RequestStatus.pending)
        ),
        pending_registrations=db.scalar(select(func.count(User.id)).where(User.status == UserStatus.pending)),
        departments=db.scalar(select(func.count(Department.id))),
        inactive_accounts=db.scalar(select(func.count(User.id)).where(User.status == UserStatus.inactive)),
        # Active faculty who won't show up in search yet (no profile, or missing a required field)
        incomplete_profiles=db.scalar(
            select(func.count(User.id))
            .outerjoin(FacultyProfile, FacultyProfile.user_id == User.id)
            .where(User.role == UserRole.faculty, User.status == UserStatus.active)
            .where(or_(FacultyProfile.id.is_(None), ~is_discoverable_sql()))
        ),
    )


# ---------- Accounts (FR-038) ----------

@router.get("/users", response_model=AdminUserPage)
def list_users(
    q: str = Query("", max_length=200, description="Name or email contains"),
    role: UserRole | None = None,
    status_filter: UserStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    query = select(User)
    if q.strip():
        term = f"%{q.strip().replace('%', '').replace('_', '')}%"
        query = query.where(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if role is not None:
        query = query.where(User.role == role)
    if status_filter is not None:
        query = query.where(User.status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    users = db.scalars(
        query.order_by(User.full_name, User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(
            selectinload(User.profile).selectinload(FacultyProfile.department),
            selectinload(User.managed_department),
        )
    ).all()
    return AdminUserPage(total=total, page=page, page_size=page_size, results=[_to_out(u) for u in users])


@router.post("/users", response_model=AdminUserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: AdminUserCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if body.email.rsplit("@", 1)[1] != settings.ALLOWED_EMAIL_DOMAIN.lower():  # BR-001 applies here too
        _field_error("email", f"Use an @{settings.ALLOWED_EMAIL_DOMAIN} email address")
    _check_department(db, body.role, body.department_id)
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")  # BR-002

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        status=UserStatus.active,
        department_id=body.department_id if body.role == UserRole.dept_mgmt else None,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    audit.record(db, admin, AuditAction.account_created, target=user, details=ROLE_LABEL[user.role])
    db.commit()
    return _to_out(_load_user(db, user.id))


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(user_id: int, body: AdminUserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Edit name, assign a role (FR-005, BR-003: exactly one role) and a managed department."""
    user = _load_user(db, user_id)
    sent = body.model_fields_set
    if "full_name" in sent and body.full_name is None:
        _field_error("full_name", "Full name can't be empty")
    if "role" in sent and body.role is None:
        _field_error("role", "Choose a role")

    new_role = body.role if "role" in sent else user.role
    new_dept = body.department_id if "department_id" in sent else user.department_id
    if new_role != UserRole.dept_mgmt:
        new_dept = None  # only Department Management accounts are tied to a department
    _check_department(db, new_role, new_dept)

    if new_role != user.role:
        if user.id == admin.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can't change your own role")
        if user.role == UserRole.admin and user.status == UserStatus.active and _active_admins(db) <= 1:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There must be at least one active administrator")
        audit.record(db, admin, AuditAction.role_changed, target=user,
                     details=f"{ROLE_LABEL[user.role]} -> {ROLE_LABEL[new_role]}")
        user.role = new_role
    elif new_dept != user.department_id:
        audit.record(db, admin, AuditAction.role_changed, target=user, details=f"Department changed to #{new_dept}")

    user.department_id = new_dept
    if "full_name" in sent:
        user.full_name = body.full_name
    db.commit()
    db.expire_all()
    return _to_out(_load_user(db, user.id))


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
def deactivate(
    user_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """FR-007: a deactivated account can't log in (BR-004) and drops out of search.

    Their pending collaboration requests are withdrawn and the other person is told why,
    and every session they have is ended.
    """
    user = _load_user(db, user_id)
    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can't deactivate your own account")
    if user.status == UserStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This registration is still pending. Reject it from Approvals instead.")
    if user.status == UserStatus.inactive:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account is already deactivated")
    if user.role == UserRole.admin and _active_admins(db) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There must be at least one active administrator")

    user.status = UserStatus.inactive
    to_tell = cancel_pending_for(db, user)
    sessions.revoke_all(db, user.id)
    audit.record(db, admin, AuditAction.account_deactivated, target=user,
                 details=f"{len(to_tell)} pending request(s) cancelled" if to_tell else None)
    db.commit()
    for other, message in to_tell:
        background.add_task(email.send_request_cancelled, other.email, other.full_name, message)
    return _to_out(_load_user(db, user.id))


@router.post("/users/{user_id}/activate", response_model=AdminUserOut)
def activate(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = _load_user(db, user_id)
    if user.status == UserStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This registration is still pending. Approve it from Approvals instead.")
    if user.status == UserStatus.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account is already active")

    user.status = UserStatus.active
    user.rejection_reason = None  # re-activating a rejected applicant counts as approving them
    audit.record(db, admin, AuditAction.account_activated, target=user)
    db.commit()
    return _to_out(_load_user(db, user.id))


@router.post("/users/{user_id}/send-password-reset", response_model=MessageResponse)
def send_password_reset(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Email the user a reset link (same single-use link as "Forgot password").

    Sent synchronously so the admin is told if the email couldn't go out.
    """
    user = _load_user(db, user_id)
    if not password_reset.can_reset(user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Reset links can only be sent to active (approved) accounts")
    link = password_reset.create_link(db, user)
    if link is None:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="A reset email was sent less than a minute ago. Please wait before sending another.")
    audit.record(db, admin, AuditAction.password_reset_sent, target=user)
    db.commit()

    minutes = settings.PASSWORD_RESET_EXPIRE_MINUTES
    if email.send_password_reset(user.email, user.full_name, link, minutes):
        return MessageResponse(message=f"Reset link sent to {user.email}. It expires in {minutes} minutes.")
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="The reset link was created but the email couldn't be sent. Check the email (SendGrid) settings.",
    )


# ---------- Audit log (NFR-008) ----------

@router.get("/audit-logs", response_model=AuditPage)
def audit_logs(
    action: AuditAction | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    query = select(AuditLog)
    if action is not None:
        query = query.where(AuditLog.action == action)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(selectinload(AuditLog.actor), selectinload(AuditLog.target_user))
    ).all()
    return AuditPage(
        total=total,
        page=page,
        page_size=page_size,
        results=[
            AuditEntryOut(
                id=r.id,
                action=r.action,
                actor_name=r.actor.full_name if r.actor else None,
                target_name=r.target_user.full_name if r.target_user else None,
                target_email=r.target_user.email if r.target_user else None,
                details=r.details,
                created_at=r.created_at,
            )
            for r in rows
        ],
    )
