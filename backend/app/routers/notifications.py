from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import Notification, User
from app.schemas.collaboration import NotificationOut, NotificationPage

router = APIRouter(prefix="/notifications", tags=["notifications"])

# Every query is scoped to the logged-in user: you only ever see your own (BR-019)


def _unread(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
    )


@router.get("", response_model=NotificationPage)
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """FR-037: newest first."""
    q = select(Notification).where(Notification.recipient_id == user.id)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return NotificationPage(
        unread_count=_unread(db, user),
        total=total,
        page=page,
        page_size=page_size,
        results=[NotificationOut.model_validate(n, from_attributes=True) for n in rows],
    )


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Cheap endpoint for the bell badge to poll."""
    return {"unread_count": _unread(db, user)}


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = db.execute(
        update(Notification)
        .where(Notification.recipient_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return {"updated": result.rowcount}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """FR-036."""
    n = db.get(Notification, notification_id)
    if n is None or n.recipient_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.is_read = True
    db.commit()
    return NotificationOut.model_validate(n, from_attributes=True)
