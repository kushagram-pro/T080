import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Response
from jose import JWTError, jwt

from app.config import settings

ACCESS = "access"
REFRESH = "refresh"

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"  # cookie is only sent to /auth/refresh and /auth/logout


class TokenError(Exception):
    """Raised for any invalid, expired or wrong-type token."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str) -> str:
    now = _now()
    claims = {
        "sub": str(user_id),
        "role": role,
        "type": ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at). The caller records the jti so it can be revoked."""
    now = _now()
    jti = uuid.uuid4().hex
    expires = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    claims = {
        "sub": str(user_id),
        "type": REFRESH,
        "jti": jti,
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(claims, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti, expires.replace(tzinfo=None)  # DB stores naive UTC


def _decode(token: str, key: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, key, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise TokenError(str(e)) from e
    if payload.get("type") != expected_type or "sub" not in payload:
        raise TokenError("Wrong token type")
    if expected_type == REFRESH and "jti" not in payload:
        raise TokenError("Refresh token without id")
    return payload


def decode_access_token(token: str) -> dict:
    return _decode(token, settings.SECRET_KEY, ACCESS)


def decode_refresh_token(token: str) -> dict:
    return _decode(token, settings.REFRESH_SECRET_KEY, REFRESH)


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
