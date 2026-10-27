from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.limiter import limiter
from app.models import User, UserRole, UserStatus
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)
from app.security.hashing import hash_password, verify_against_dummy, verify_password
from app.security import email
from app.security.jwt import REFRESH_COOKIE_NAME, clear_refresh_cookie, create_access_token
from app.services import password_reset, sessions

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid email or password"  # FR-003: never say which one was wrong


def _issue_tokens(db: Session, user: User, response: Response) -> TokenResponse:
    sessions.issue(db, user, response)  # recorded server-side so it can be revoked
    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """FR-001 / UC-003. Faculty self-register; account stays pending until an admin approves it."""
    # SRS BR-001: institutional email only
    domain = body.email.rsplit("@", 1)[1]
    if domain != settings.ALLOWED_EMAIL_DOMAIN.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Please register with your @{settings.ALLOWED_EMAIL_DOMAIN} email address",
        )

    existing = db.scalar(select(User).where(User.email == body.email).with_for_update())
    if existing is not None:
        # A rejected applicant may re-apply: the same account (BR-002) goes back to pending.
        # Rejected = inactive WITH a reason; deactivated-after-approval accounts have no reason.
        if existing.status == UserStatus.inactive and existing.rejection_reason:
            existing.full_name = body.full_name
            existing.hashed_password = hash_password(body.password)
            existing.role = UserRole.faculty
            existing.status = UserStatus.pending
            existing.rejection_reason = None
            db.commit()
            return MessageResponse(
                message="Registration re-submitted. You will get an email once an administrator reviews it."
            )
        # SRS BR-002: one account per email
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=UserRole.faculty,
        status=UserStatus.pending,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two simultaneous registrations with the same email
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    return MessageResponse(
        message="Registration received. You will get an email once an administrator approves your account."
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, response: Response, body: LoginRequest, db: Session = Depends(get_db)):
    """FR-002 / FR-003 / UC-001."""
    user = db.scalar(select(User).where(User.email == body.email))

    if user is None:
        verify_against_dummy(body.password)  # same timing as a wrong password
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    # Status is only revealed after the password is proven correct.
    if user.status == UserStatus.pending:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is awaiting administrator approval")
    if user.status == UserStatus.inactive:
        if user.rejection_reason:
            detail = f"Your registration was not approved. Reason: {user.rejection_reason}"
        else:
            detail = "Your account has been deactivated. Please contact the administrator."  # BR-004
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    return _issue_tokens(db, user, response)


@router.post("/refresh", response_model=TokenResponse, responses={401: {"description": "Missing, invalid or expired refresh token"}})
@limiter.limit("30/minute")
def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    """Exchange the httpOnly refresh cookie for a new access token. The old token is retired
    (rotation); a revoked, logged-out or replayed token is rejected."""
    user = sessions.rotate(db, refresh_token, response)
    if user is None:
        # Returned (not raised) so the cookie-clearing header is kept
        rejection = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Session expired. Please log in again."},
        )
        clear_refresh_cookie(rejection)
        return rejection

    db.commit()
    return TokenResponse(
        access_token=create_access_token(user.id, user.role.value),
        user=UserOut.model_validate(user),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    """FR-004. Revokes the refresh token server-side, so a copied cookie stops working too.
    The frontend must also drop its in-memory access token."""
    sessions.revoke(db, refresh_token)
    db.commit()
    clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=MessageResponse)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    response: Response,
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lets users replace the initial password an administrator set for them."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "current_password"], "msg": "Current password is incorrect", "type": "value_error"}],
        )
    if verify_password(body.new_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "new_password"], "msg": "Choose a password different from your current one", "type": "value_error"}],
        )
    user.hashed_password = hash_password(body.new_password)
    # Sign out every other device; this browser gets a fresh session so the user stays logged in here
    sessions.revoke_all(db, user.id)
    sessions.issue(db, user, response)
    db.commit()
    return MessageResponse(message="Password changed. You've been signed out on other devices.")


# ---------- Forgotten password ----------

RESET_SENT = (
    "If an active account exists for that email, we've sent a link to reset the password. "
    "It expires in {minutes} minutes."
)


@router.post("/forgot-password", response_model=MessageResponse)
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Emails a reset link to approved, active accounts only.

    The reply is identical whether or not the email belongs to an account (same idea as FR-003),
    so this can't be used to find out who is registered.
    """
    user = db.scalar(select(User).where(User.email == body.email))
    if password_reset.can_reset(user):
        link = password_reset.create_link(db, user)  # None if one was sent in the last minute
        db.commit()
        if link:
            background.add_task(email.send_password_reset, user.email, user.full_name, link,
                                settings.PASSWORD_RESET_EXPIRE_MINUTES)
    return MessageResponse(message=RESET_SENT.format(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES))


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("10/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user = password_reset.consume(db, body.token)
    except password_reset.ResetError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    user.hashed_password = hash_password(body.new_password)
    sessions.revoke_all(db, user.id)  # whoever might have had access is signed out everywhere
    db.commit()
    return MessageResponse(message="Your password has been reset. You can now log in.")
