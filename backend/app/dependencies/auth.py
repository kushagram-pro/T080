from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, UserStatus
from app.security.jwt import TokenError, decode_access_token

_bearer = HTTPBearer(auto_error=False)

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """NFR-004: protected routes require a valid access token."""
    if creds is None:
        raise _unauthorized
    try:
        payload = decode_access_token(creds.credentials)
        user_id = int(payload["sub"])
    except (TokenError, ValueError):
        raise _unauthorized

    user = db.get(User, user_id)
    # SRS BR-004 / FR-007: a deactivated account loses access immediately,
    # even if it still holds an unexpired token.
    if user is None or user.status != UserStatus.active:
        raise _unauthorized
    return user


def require_roles(*roles: UserRole):
    """FR-006 / NFR-005: restrict a route to the given roles.

    Usage: user: User = Depends(require_roles(UserRole.admin))
    """
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to do this")
        return user
    return checker


# Shortcuts for the common cases
require_faculty = require_roles(UserRole.faculty)
require_admin = require_roles(UserRole.admin)
require_oversight = require_roles(UserRole.admin, UserRole.research_admin, UserRole.dept_mgmt)
