from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_admin
from app.models import AuditAction, User, UserStatus
from app.schemas.admin import PendingUserOut, RejectRequest
from app.schemas.auth import UserOut
from app.security import email
from app.services import audit

router = APIRouter(prefix="/admin/approvals", tags=["admin: approvals"])


def _get_pending_for_update(db: Session, user_id: int) -> User:
    # Row lock so two admins acting at once can't both approve/reject the same user
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.status != UserStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This registration has already been processed")
    return user


@router.get("", response_model=list[PendingUserOut])
def list_pending(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Registrations awaiting a decision, oldest submission first.

    updated_at, not created_at: a rejected applicant who re-applies keeps their
    original created_at but should queue by when they re-submitted.
    """
    return db.scalars(
        select(User).where(User.status == UserStatus.pending).order_by(User.updated_at, User.id)
    ).all()


@router.post("/{user_id}/approve", response_model=UserOut)
def approve(
    user_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = _get_pending_for_update(db, user_id)
    user.status = UserStatus.active
    user.rejection_reason = None
    audit.record(db, admin, AuditAction.account_approved, target=user)
    db.commit()

    background.add_task(email.send_account_approved, user.email, user.full_name)
    return user


@router.post("/{user_id}/reject", response_model=UserOut)
def reject(
    user_id: int,
    body: RejectRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = _get_pending_for_update(db, user_id)
    user.status = UserStatus.inactive
    user.rejection_reason = body.reason
    audit.record(db, admin, AuditAction.account_rejected, target=user, details=body.reason)
    db.commit()

    background.add_task(email.send_account_rejected, user.email, user.full_name, body.reason)
    return user
