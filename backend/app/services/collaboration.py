from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Collaboration,
    CollaborationRequest,
    FacultyProfile,
    Notification,
    NotificationType,
    RequestStatus,
    User,
    UserStatus,
)
from app.schemas.collaboration import Party


def ordered_pair(a: int, b: int) -> tuple[int, int]:
    """Collaborations are stored once per pair with faculty_a < faculty_b (BR-014)."""
    return (a, b) if a < b else (b, a)


def find_collaboration(db: Session, a: int, b: int) -> Collaboration | None:
    x, y = ordered_pair(a, b)
    return db.scalar(select(Collaboration).where(Collaboration.faculty_a == x, Collaboration.faculty_b == y))


def find_pending(db: Session, a: int, b: int) -> CollaborationRequest | None:
    """The pending request between two people, in either direction (BR-010)."""
    return db.scalar(
        select(CollaborationRequest).where(
            CollaborationRequest.status == RequestStatus.pending,
            or_(
                and_(CollaborationRequest.sender_id == a, CollaborationRequest.recipient_id == b),
                and_(CollaborationRequest.sender_id == b, CollaborationRequest.recipient_id == a),
            ),
        )
    )


def display_name(user: User) -> str:
    return user.profile.full_name if user.profile else user.full_name


def parties(db: Session, user_ids: set[int]) -> dict[int, Party]:
    """Name / designation / department for each user, in one round of queries."""
    if not user_ids:
        return {}
    users = db.scalars(
        select(User)
        .where(User.id.in_(user_ids))
        .options(selectinload(User.profile).selectinload(FacultyProfile.department))
    ).all()
    out = {}
    for u in users:
        p = u.profile
        out[u.id] = Party(
            user_id=u.id,
            full_name=display_name(u),
            designation=p.designation if p else None,
            department=p.department.name if p and p.department else None,
        )
    return out


def notify(db: Session, recipient_id: int, type_: NotificationType, message: str, request_id: int) -> None:
    """In-app notification, committed together with the action that caused it.

    BR-018: request received / accepted / declined, plus request_cancelled (deactivation).
    BR-019: only the person directly involved.
    """
    db.add(Notification(recipient_id=recipient_id, type=type_, message=message, request_id=request_id))


def cancel_pending_for(db: Session, user: User) -> list[tuple[User, str]]:
    """Withdraw every pending request to or from `user` (their account is being deactivated).

    The other person gets an in-app notification saying why. Returns (other user, message)
    pairs so the caller can also email them after committing. Caller commits.
    """
    pending = db.scalars(
        select(CollaborationRequest)
        .where(
            CollaborationRequest.status == RequestStatus.pending,
            or_(CollaborationRequest.sender_id == user.id, CollaborationRequest.recipient_id == user.id),
        )
        .with_for_update()
    ).all()

    name = display_name(user)
    to_email = []
    now = datetime.utcnow()
    for req in pending:
        req.status = RequestStatus.withdrawn  # BR-011: withdrawn is the closest of the four states
        req.responded_at = now
        if req.sender_id == user.id:
            other_id = req.recipient_id
            message = f"{name}'s collaboration request to you was cancelled because their account is no longer active."
        else:
            other_id = req.sender_id
            message = f"Your collaboration request to {name} was cancelled because their account is no longer active."
        other = db.get(User, other_id)
        if other is None or other.status != UserStatus.active:
            continue  # nobody active to tell
        notify(db, other.id, NotificationType.request_cancelled, message, req.id)
        to_email.append((other, message))
    return to_email
