"""Server-side refresh-token sessions.

Every refresh token is recorded by its jti. That makes three things possible that a purely
stateless JWT can't do:
  - logout really ends the session (the token is revoked, not just deleted from the browser)
  - password changes / resets and deactivation end every session for that account
  - a stolen token being replayed is detected (reuse of a rotated token) and shuts everything down
"""
import logging
from datetime import datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, User, UserStatus
from app.security.jwt import TokenError, create_refresh_token, decode_refresh_token, set_refresh_cookie

logger = logging.getLogger("sessions")

# Two tabs refreshing at almost the same moment both present the same cookie. The first rotates
# it; the second arrives with an already-rotated token. Within this window that's treated as
# benign, not as theft.
ROTATION_GRACE = timedelta(seconds=20)


def issue(db: Session, user: User, response: Response) -> str:
    """New refresh token for `user`: recorded, then set as the httpOnly cookie. Returns its jti. Caller commits."""
    token, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    # Housekeeping: drop this user's long-dead rows so the table doesn't grow forever
    db.execute(delete(RefreshToken).where(
        RefreshToken.user_id == user.id,
        RefreshToken.expires_at < datetime.utcnow() - timedelta(days=1),
    ))
    set_refresh_cookie(response, token)
    return jti


def rotate(db: Session, token: str | None, response: Response) -> User | None:
    """Validate a refresh token and replace it with a new one. Returns the user, or None to reject."""
    if not token:
        return None
    try:
        payload = decode_refresh_token(token)
        user_id, jti = int(payload["sub"]), payload["jti"]
    except (TokenError, ValueError, KeyError):
        return None

    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti).with_for_update())
    if row is None or row.user_id != user_id:
        return None  # issued before server-side sessions existed, or tampered with
    now = datetime.utcnow()

    if row.revoked_at is not None:
        rotated_moments_ago = row.replaced_by is not None and now - row.revoked_at < ROTATION_GRACE
        if not rotated_moments_ago:
            if row.replaced_by is not None:
                # A token that was already swapped for a newer one is being used again later:
                # someone has a copy. End every session for this account.
                logger.warning("Refresh token reuse detected for user %s; revoking all sessions", user_id)
                revoke_all(db, user_id)
                db.commit()
            return None

    if row.expires_at < now:
        return None

    user = db.get(User, user_id)
    if user is None or user.status != UserStatus.active:
        return None

    new_jti = issue(db, user, response)
    if row.revoked_at is None:
        row.revoked_at = now
        row.replaced_by = new_jti
    return user


def revoke(db: Session, token: str | None) -> None:
    """Logout: revoke the presented token (if it's valid and ours). Caller commits."""
    if not token:
        return
    try:
        jti = decode_refresh_token(token)["jti"]
    except (TokenError, KeyError):
        return
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.jti == jti, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )


def revoke_all(db: Session, user_id: int) -> int:
    """End every session for a user (password change/reset, deactivation, theft). Caller commits."""
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.utcnow())
    )
    return result.rowcount
