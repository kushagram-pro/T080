import logging
from html import escape

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import ClickTracking, Mail, TrackingSettings

from app.config import settings

logger = logging.getLogger(__name__)

# Call these through FastAPI BackgroundTasks so a slow or failing SendGrid
# never blocks or breaks the request. Failures are logged, never raised.


def _email_enabled() -> bool:
    key = settings.SENDGRID_API_KEY
    return bool(key) and key.startswith("SG.")


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    if not _email_enabled():
        logger.info("Email disabled (no SendGrid key). Would send to=%s subject=%r", to_email, subject)
        return False

    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        html_content=html_body,
    )
    # Don't let SendGrid rewrite links through its tracker (password reset links must go straight to us)
    message.tracking_settings = TrackingSettings(click_tracking=ClickTracking(False, False))
    try:
        resp = SendGridAPIClient(settings.SENDGRID_API_KEY).send(message)
        if resp.status_code >= 400:
            logger.error("SendGrid returned %s for to=%s", resp.status_code, to_email)
            return False
        return True
    except Exception:
        logger.exception("SendGrid send failed for to=%s", to_email)
        return False


def _wrap(body: str) -> str:
    return (
        '<div style="font-family:Arial,sans-serif;max-width:560px">'
        f"{body}"
        f'<p><a href="{escape(settings.FRONTEND_ORIGIN)}">Open Faculty Collaboration Network Portal</a></p>'
        '<p style="color:#888;font-size:12px">LNMIIT Faculty Collaboration Network Portal</p>'
        "</div>"
    )


# --- Account approval (registration flow) ---

def send_account_approved(to_email: str, name: str) -> bool:
    body = (
        f"<p>Dear {escape(name)},</p>"
        "<p>Your account on the Faculty Collaboration Network Portal has been approved. "
        "You can now log in and complete your profile.</p>"
    )
    return send_email(to_email, "Your portal account has been approved", _wrap(body))


def send_account_rejected(to_email: str, name: str, reason: str) -> bool:
    body = (
        f"<p>Dear {escape(name)},</p>"
        "<p>Your registration on the Faculty Collaboration Network Portal was not approved.</p>"
        f"<p><strong>Reason:</strong> {escape(reason)}</p>"
    )
    return send_email(to_email, "Your portal registration was not approved", _wrap(body))


# --- Collaboration requests (SRS BR-018: received / accepted / declined only) ---

def send_request_received(to_email: str, recipient_name: str, sender_name: str, message: str | None) -> bool:
    body = (
        f"<p>Dear {escape(recipient_name)},</p>"
        f"<p><strong>{escape(sender_name)}</strong> has sent you a collaboration request.</p>"
    )
    if message:
        body += f'<blockquote style="border-left:3px solid #ccc;padding-left:8px">{escape(message)}</blockquote>'
    return send_email(to_email, f"New collaboration request from {sender_name}", _wrap(body))


def send_request_accepted(to_email: str, sender_name: str, recipient_name: str) -> bool:
    body = (
        f"<p>Dear {escape(sender_name)},</p>"
        f"<p><strong>{escape(recipient_name)}</strong> has accepted your collaboration request.</p>"
    )
    return send_email(to_email, f"{recipient_name} accepted your collaboration request", _wrap(body))


def send_request_declined(to_email: str, sender_name: str, recipient_name: str) -> bool:
    body = (
        f"<p>Dear {escape(sender_name)},</p>"
        f"<p><strong>{escape(recipient_name)}</strong> has declined your collaboration request.</p>"
    )
    return send_email(to_email, f"{recipient_name} declined your collaboration request", _wrap(body))


# --- Password reset ---

def send_password_reset(to_email: str, name: str, link: str, minutes: int) -> bool:
    if not _email_enabled():
        # Development only (no SendGrid key configured): print the link so the flow can be tested
        logger.info("Email disabled. Password reset link for %s: %s", to_email, link)
        return False
    body = (
        f"<p>Dear {escape(name)},</p>"
        "<p>We received a request to reset the password for your Faculty Collaboration Network account.</p>"
        f'<p><a href="{escape(link)}" style="display:inline-block;padding:10px 18px;background:#111;color:#fff;'
        'text-decoration:none;border-radius:8px">Choose a new password</a></p>'
        f"<p>This link works once and expires in {minutes} minutes.</p>"
        "<p>If you didn't ask for this, you can ignore this email; your password won't change.</p>"
    )
    return send_email(to_email, "Reset your portal password", _wrap(body))


# --- Collaboration request cancelled because an account was deactivated ---

def send_request_cancelled(to_email: str, name: str, message: str) -> bool:
    body = f"<p>Dear {escape(name)},</p><p>{escape(message)}</p>"
    return send_email(to_email, "A collaboration request was cancelled", _wrap(body))
