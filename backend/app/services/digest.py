"""Weekly email digest for faculty.

Each digest covers what happened since the previous one (or the last 7 days the first time):
  - collaboration requests still waiting for their answer
  - unread messages in their collaborations
  - colleagues who joined (created a profile) since then and share their keywords
Nothing to report means no email. Run it on a schedule with `python -m scripts.send_digest`.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Collaboration,
    CollaborationMessage,
    CollaborationRequest,
    FacultyProfile,
    RequestStatus,
    User,
    UserRole,
    UserStatus,
)
from app.security import email
from app.services.collaboration import parties

logger = logging.getLogger("digest")

INTERVAL = timedelta(days=7)
# A little slack so a weekly scheduled run isn't skipped because last week's ran a few minutes later
DUE_AFTER = INTERVAL - timedelta(hours=12)
MAX_SUGGESTIONS = 3


@dataclass
class Digest:
    pending: list[str] = field(default_factory=list)
    unread_messages: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.pending or self.unread_messages or self.suggestions)


def due_users(db: Session, now: datetime) -> list[User]:
    """Active faculty with the digest on whose last one was a week or more ago."""
    return db.scalars(
        select(User).where(
            User.role == UserRole.faculty,
            User.status == UserStatus.active,
            User.email_digest.is_(True),
            or_(User.digest_sent_at.is_(None), User.digest_sent_at <= now - DUE_AFTER),
        ).order_by(User.id)
    ).all()


def build(db: Session, user: User, now: datetime) -> Digest:
    since = user.digest_sent_at or now - INTERVAL
    d = Digest()

    # Requests waiting for this user's answer, from people who are still active
    waiting = db.scalars(
        select(CollaborationRequest)
        .join(User, User.id == CollaborationRequest.sender_id)
        .where(
            CollaborationRequest.recipient_id == user.id,
            CollaborationRequest.status == RequestStatus.pending,
            User.status == UserStatus.active,
        )
        .order_by(CollaborationRequest.sent_at)
    ).all()
    people = parties(db, {r.sender_id for r in waiting})
    d.pending = [people[r.sender_id].full_name for r in waiting]

    # Unread messages, per conversation
    unread = db.execute(
        select(Collaboration, func.count(CollaborationMessage.id))
        .join(CollaborationMessage, CollaborationMessage.collaboration_id == Collaboration.id)
        .where(
            or_(Collaboration.faculty_a == user.id, Collaboration.faculty_b == user.id),
            CollaborationMessage.sender_id != user.id,
            CollaborationMessage.read_at.is_(None),
        )
        .group_by(Collaboration.id)
    ).all()
    people = parties(db, {c.other(user.id) for c, _ in unread})
    d.unread_messages = [f"{people[c.other(user.id)].full_name} ({n})" for c, n in unread]

    # New colleagues with shared keywords: the regular suggestions, limited to profiles created since
    from app.routers.suggestions import suggestions  # the ranking lives there

    if db.scalar(select(FacultyProfile.id).where(FacultyProfile.user_id == user.id)) is not None:
        new_ids = set(db.scalars(select(FacultyProfile.user_id).where(FacultyProfile.created_at > since)))
        if new_ids:
            ranked = suggestions(limit=50, db=db, user=user)
            d.suggestions = [
                f"{s.full_name}: {', '.join(s.shared_keywords)}" for s in ranked if s.user_id in new_ids
            ][:MAX_SUGGESTIONS]
    return d


def send_due(db: Session, now: datetime | None = None, dry_run: bool = False) -> tuple[int, int]:
    """Send every digest that is due. Returns (sent, skipped because there was nothing to say)."""
    now = now or datetime.utcnow()
    sent = skipped = 0
    for user in due_users(db, now):
        d = build(db, user, now)
        if d.is_empty():
            skipped += 1
            continue
        if dry_run:
            logger.info("Would send digest to %s: %s", user.email, d)
            sent += 1
            continue
        email.send_weekly_digest(user.email, user.full_name, d.pending, d.unread_messages, d.suggestions)
        # Recorded even if SendGrid is down, so a failure doesn't turn into a burst of repeats later
        user.digest_sent_at = now
        db.commit()
        sent += 1
    return sent, skipped
