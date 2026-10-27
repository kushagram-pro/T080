from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import require_faculty
from app.models import (
    Collaboration,
    CollaborationRequest,
    NotificationType,
    RequestStatus,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.collaboration import CollaboratorOut, RelationshipOut, RequestCreate, RequestOut
from app.security import email
from app.services.collaboration import (
    display_name,
    find_collaboration,
    find_pending,
    notify,
    ordered_pair,
    parties,
)
from app.services.profiles import load_profile

router = APIRouter(prefix="/collaborations", tags=["collaborations"])


def _conflict(msg: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)


def _to_out(req: CollaborationRequest, viewer_id: int, people) -> RequestOut:
    sent = req.sender_id == viewer_id
    return RequestOut(
        id=req.id,
        direction="sent" if sent else "received",
        other=people[req.recipient_id if sent else req.sender_id],
        message=req.message,
        status=req.status,
        sent_at=req.sent_at,
        responded_at=req.responded_at,
    )


# ---------- Send (FR-026 to FR-029 / UC-014) ----------

@router.post("/requests", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def send_request(
    body: RequestCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_faculty),
):
    # Checks run in the order of UC-014's main flow, each with its own clear message (AC-010)
    if body.recipient_id == user.id:
        raise HTTPException(  # BR-009 / FR-029
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="You can't send a collaboration request to yourself",
        )

    recipient = db.get(User, body.recipient_id)
    if recipient is None or recipient.role != UserRole.faculty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Faculty member not found")
    if recipient.status != UserStatus.active:
        _conflict("This faculty member's account is not active, so the request can't be sent")  # BR-013

    recipient_profile = load_profile(db, user_id=recipient.id)
    if recipient_profile is None or not recipient_profile.is_discoverable():
        _conflict("This faculty member hasn't completed their profile yet")  # AC-003

    sender_profile = load_profile(db, user_id=user.id)
    if sender_profile is None:
        # So the recipient can look at who is asking before they answer
        _conflict("Create your profile before sending collaboration requests")

    other_name = recipient_profile.full_name
    if find_collaboration(db, user.id, recipient.id):
        _conflict(f"You're already collaborating with {other_name}")

    pending = find_pending(db, user.id, recipient.id)  # BR-010 / FR-028
    if pending is not None:
        if pending.sender_id == user.id:
            _conflict(f"You already have a pending request to {other_name}")
        _conflict(f"{other_name} has already sent you a request. You can accept it under Received requests.")

    req = CollaborationRequest(sender_id=user.id, recipient_id=recipient.id, message=body.message)
    db.add(req)
    try:
        db.flush()  # need req.id for the notification; also hits the pending-pair index on a race
    except IntegrityError:
        db.rollback()
        _conflict(f"There's already a pending request between you and {other_name}")

    sender_name = sender_profile.full_name
    notify(db, recipient.id, NotificationType.request_received,  # FR-034
           f"{sender_name} sent you a collaboration request.", req.id)
    db.commit()

    background.add_task(email.send_request_received, recipient.email, other_name, sender_name, body.message)
    return _to_out(req, user.id, parties(db, {recipient.id}))


# ---------- Respond (FR-030 / FR-033 / BR-011 / BR-012) ----------

def _locked_request(db: Session, request_id: int, user: User) -> CollaborationRequest:
    # Row lock: two clicks (or accept vs withdraw) can't both change the same request
    req = db.scalar(select(CollaborationRequest).where(CollaborationRequest.id == request_id).with_for_update())
    if req is None or user.id not in (req.sender_id, req.recipient_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    return req


def _require_pending(req: CollaborationRequest):
    if req.status != RequestStatus.pending:  # BR-012: no transitions out of a final state
        _conflict(f"This request has already been {req.status.value}")


def _only(req: CollaborationRequest, user: User, role: str):
    allowed = req.recipient_id if role == "recipient" else req.sender_id
    if user.id != allowed:
        action = "respond to" if role == "recipient" else "withdraw"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Only the {role} can {action} this request")


@router.post("/requests/{request_id}/accept", response_model=RequestOut)
def accept(request_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    req = _locked_request(db, request_id, user)
    _only(req, user, "recipient")
    _require_pending(req)

    sender = db.get(User, req.sender_id)
    if sender.status != UserStatus.active:
        _conflict(f"{display_name(sender)}'s account is no longer active")

    req.status = RequestStatus.accepted
    req.responded_at = datetime.utcnow()
    # BR-014: one mutual collaboration, whichever direction the request went
    if find_collaboration(db, req.sender_id, req.recipient_id) is None:
        a, b = ordered_pair(req.sender_id, req.recipient_id)
        db.add(Collaboration(request_id=req.id, faculty_a=a, faculty_b=b))

    me = display_name(user)
    notify(db, sender.id, NotificationType.request_accepted, f"{me} accepted your collaboration request.", req.id)  # FR-035
    db.commit()

    background.add_task(email.send_request_accepted, sender.email, display_name(sender), me)
    return _to_out(req, user.id, parties(db, {sender.id}))


@router.post("/requests/{request_id}/decline", response_model=RequestOut)
def decline(request_id: int, background: BackgroundTasks, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    req = _locked_request(db, request_id, user)
    _only(req, user, "recipient")
    _require_pending(req)

    req.status = RequestStatus.declined
    req.responded_at = datetime.utcnow()
    sender = db.get(User, req.sender_id)
    me = display_name(user)
    notify(db, sender.id, NotificationType.request_declined, f"{me} declined your collaboration request.", req.id)  # FR-035
    db.commit()

    background.add_task(email.send_request_declined, sender.email, display_name(sender), me)
    return _to_out(req, user.id, parties(db, {sender.id}))


@router.post("/requests/{request_id}/withdraw", response_model=RequestOut)
def withdraw(request_id: int, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    """UC-017. No notification: BR-018 doesn't list withdrawal."""
    req = _locked_request(db, request_id, user)
    _only(req, user, "sender")
    _require_pending(req)

    req.status = RequestStatus.withdrawn
    req.responded_at = datetime.utcnow()
    db.commit()
    return _to_out(req, user.id, parties(db, {req.recipient_id}))


# ---------- Lists (FR-031 / FR-032) ----------

def _list(db: Session, user: User, column, status_filter: RequestStatus | None) -> list[RequestOut]:
    q = select(CollaborationRequest).where(column == user.id)
    if status_filter is not None:
        q = q.where(CollaborationRequest.status == status_filter)
    reqs = db.scalars(q.order_by(CollaborationRequest.sent_at.desc(), CollaborationRequest.id.desc()).limit(200)).all()
    people = parties(db, {r.recipient_id if r.sender_id == user.id else r.sender_id for r in reqs})
    return [_to_out(r, user.id, people) for r in reqs]


@router.get("/requests/sent", response_model=list[RequestOut])
def sent_requests(
    status_filter: RequestStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_faculty),
):
    return _list(db, user, CollaborationRequest.sender_id, status_filter)


@router.get("/requests/received", response_model=list[RequestOut])
def received_requests(
    status_filter: RequestStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    user: User = Depends(require_faculty),
):
    return _list(db, user, CollaborationRequest.recipient_id, status_filter)


# ---------- My collaborators ----------

@router.get("", response_model=list[CollaboratorOut])
def my_collaborators(db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    rows = db.scalars(
        select(Collaboration)
        .where(or_(Collaboration.faculty_a == user.id, Collaboration.faculty_b == user.id))
        .order_by(Collaboration.created_at.desc())
    ).all()
    other_ids = {c.faculty_b if c.faculty_a == user.id else c.faculty_a for c in rows}
    # Deactivated colleagues are hidden, like everywhere else (BR-004)
    active = set(db.scalars(select(User.id).where(User.id.in_(other_ids), User.status == UserStatus.active)))
    people = parties(db, active)
    out = []
    for c in rows:
        other = c.faculty_b if c.faculty_a == user.id else c.faculty_a
        if other in active:
            out.append(CollaboratorOut(collaboration_id=c.id, other=people[other], since=c.created_at))
    return out


@router.get("/status/{user_id}", response_model=RelationshipOut)
def relationship(user_id: int, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    """What the profile page should show for this person."""
    if find_collaboration(db, user.id, user_id):
        return RelationshipOut(state="collaborators")
    pending = find_pending(db, user.id, user_id)
    if pending is not None:
        state = "pending_sent" if pending.sender_id == user.id else "pending_received"
        return RelationshipOut(state=state, request_id=pending.id)
    return RelationshipOut(state="none")
