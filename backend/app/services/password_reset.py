"""Password reset by emailed link.

The link carries a random token; the database only stores its SHA-256 hash, so a database
leak doesn't hand out working reset links. Links are single-use and short-lived.
"""
import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PasswordResetToken, User, UserStatus

# Don't send another email if one was sent this recently (stops inbox flooding)
RESEND_COOLDOWN = timedelta(seconds=60)


class ResetError(Exception):
    """Invalid, used or expired link, or the account can't be reset any more."""


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def can_reset(user: User | None) -> bool:
    """Only approved, currently active accounts get reset emails."""
    return user is not None and user.status == UserStatus.active


def create_link(db: Session, user: User) -> str | None:
    """New single-use reset link for `user`, or None if one was sent moments ago. Caller commits.

    Any older unused links stop working, so only the newest email is valid.
    """
    now = datetime.utcnow()
    recent = db.scalar(
        select(PasswordResetToken.id).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.created_at > now - RESEND_COOLDOWN,
        )
    )
    if recent is not None:
        return None

    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(
        user_id=user.id,
        token_hash=_hash(raw),
        expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES),
    ))
    # In the URL fragment (#), not the query string: fragments aren't sent to servers or
    # included in Referer headers, so the token doesn't end up in logs.
    return f"{settings.FRONTEND_ORIGIN}/reset-password#token={raw}"


def consume(db: Session, raw: str) -> User:
    """Validate a reset token and mark it used. Returns the user. Caller sets the password and commits."""
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash(raw)).with_for_update()
    )
    now = datetime.utcnow()
    if row is None or row.used_at is not None:
        raise ResetError("This reset link is invalid or has already been used.")
    if row.expires_at < now:
        raise ResetError("This reset link has expired.")
    user = db.get(User, row.user_id)
    if not can_reset(user):
        raise ResetError("This account can't be reset. Please contact the administrator.")
    row.used_at = now
    return user
