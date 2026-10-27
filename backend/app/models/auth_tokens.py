from datetime import datetime
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class RefreshToken(Base):
    """One row per issued refresh token, so logout and other events can revoke it server-side.

    The JWT itself is still signed; this table only records whether a given token (by its
    random `jti`) is still allowed. Knowing a jti without the signing key is useless.
    """
    __tablename__ = "refresh_tokens"

    jti:         Mapped[str]             = mapped_column(String(64), primary_key=True)
    user_id:     Mapped[int]             = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at:  Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at:  Mapped[datetime]        = mapped_column(DateTime, nullable=False)
    revoked_at:  Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Set when the token was rotated (not logged out): lets a near-simultaneous refresh from a
    # second tab be told apart from a stolen token being replayed later.
    replaced_by: Mapped[str | None]      = mapped_column(String(64), nullable=True)


class PasswordResetToken(Base):
    """Single-use password reset link. Only a SHA-256 hash of the token is stored."""
    __tablename__ = "password_reset_tokens"

    id:          Mapped[int]             = mapped_column(primary_key=True)
    user_id:     Mapped[int]             = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash:  Mapped[str]             = mapped_column(String(64), unique=True, nullable=False)
    created_at:  Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at:  Mapped[datetime]        = mapped_column(DateTime, nullable=False)
    used_at:     Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
