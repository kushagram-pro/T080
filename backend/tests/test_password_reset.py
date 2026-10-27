"""Forgotten-password flow (self-service and admin-triggered)."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.models import AuditAction, AuditLog, PasswordResetToken, UserRole, UserStatus
from app.security.jwt import REFRESH_COOKIE_NAME
from tests.conftest import PASSWORD, auth, login


def forgot(client, email):
    return client.post("/auth/forgot-password", json={"email": email})


def reset(client, token, password="NewPass123"):
    return client.post("/auth/reset-password", json={"token": token, "new_password": password})


def _expire_cooldown(db, user):
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
               .values(created_at=datetime(2000, 1, 1)))
    db.commit()


def test_active_account_gets_reset_email(client, make, outbox):
    user = make.user()
    r = forgot(client, user.email.upper())
    assert r.status_code == 200
    assert outbox.reset_token_for(user.email)


@pytest.mark.parametrize("status", [UserStatus.pending, UserStatus.inactive])
def test_unapproved_or_deactivated_accounts_get_no_email(client, make, outbox, status):
    user = make.user(status=status)
    assert forgot(client, user.email).status_code == 200
    assert outbox.to(user.email) == []


@pytest.mark.req("FR-003")
def test_reply_is_identical_whether_or_not_account_exists(client, make):
    real = forgot(client, make.user().email).json()
    fake = forgot(client, "nobody@lnmiit.ac.in").json()
    assert real == fake


def test_link_uses_url_fragment_and_only_hash_is_stored(client, make, outbox, db):
    user = make.user()
    forgot(client, user.email)
    token = outbox.reset_token_for(user.email)
    assert "/reset-password#token=" in outbox.to(user.email)[-1][2]
    stored = db.scalar(select(PasswordResetToken.token_hash).where(PasswordResetToken.user_id == user.id))
    assert stored != token and len(stored) == 64


def test_no_second_email_within_cooldown(client, make, outbox):
    user = make.user()
    forgot(client, user.email)
    forgot(client, user.email)
    assert len(outbox.to(user.email)) == 1


def test_reset_changes_password_and_ends_sessions(new_client, make, outbox):
    user = make.user()
    signed_in = new_client()
    login(signed_in, user)
    forgot(new_client(), user.email)
    assert reset(new_client(), outbox.reset_token_for(user.email)).status_code == 200
    assert login(new_client(), user, "NewPass123").status_code == 200
    assert login(new_client(), user, PASSWORD).status_code == 401
    assert signed_in.post("/auth/refresh").status_code == 401


def test_link_is_single_use(client, make, outbox):
    user = make.user()
    forgot(client, user.email)
    token = outbox.reset_token_for(user.email)
    assert reset(client, token).status_code == 200
    r = reset(client, token, "Another123")
    assert r.status_code == 400 and "already been used" in r.json()["detail"]


def test_expired_link_is_rejected(client, make, outbox, db):
    user = make.user()
    forgot(client, user.email)
    db.execute(update(PasswordResetToken).values(expires_at=datetime.utcnow() - timedelta(minutes=1)))
    db.commit()
    r = reset(client, outbox.reset_token_for(user.email))
    assert r.status_code == 400 and "expired" in r.json()["detail"]


def test_older_link_stops_working_when_newer_sent(client, make, outbox, db):
    user = make.user()
    forgot(client, user.email)
    older = outbox.reset_token_for(user.email)
    _expire_cooldown(db, user)
    forgot(client, user.email)
    assert reset(client, older).status_code == 400
    assert reset(client, outbox.reset_token_for(user.email)).status_code == 200


def test_reset_rejects_weak_password_and_bad_token(client, make, outbox):
    user = make.user()
    forgot(client, user.email)
    assert reset(client, outbox.reset_token_for(user.email), "weakweak").status_code == 422
    assert reset(client, "x" * 43).status_code == 400


def test_account_deactivated_after_link_sent_cannot_reset(client, make, outbox, db):
    user = make.user()
    forgot(client, user.email)
    user.status = UserStatus.inactive
    db.commit()
    assert reset(client, outbox.reset_token_for(user.email)).status_code == 400


# ---------- Admin "Send reset link" ----------

@pytest.mark.req("NFR-008")
def test_admin_can_send_reset_link_and_it_is_audited(client, make, outbox, db):
    admin, user = make.user(role=UserRole.admin), make.user()
    r = client.post(f"/admin/users/{user.id}/send-password-reset", headers=auth(admin))
    assert r.status_code == 200 and outbox.reset_token_for(user.email)
    actions = db.scalars(select(AuditLog.action).where(AuditLog.target_user_id == user.id)).all()
    assert AuditAction.password_reset_sent in actions


def test_admin_reset_link_rules(client, make, outbox, db):
    admin = make.user(role=UserRole.admin)
    pending, user = make.user(status=UserStatus.pending), make.user()
    assert client.post(f"/admin/users/{pending.id}/send-password-reset", headers=auth(admin)).status_code == 409
    assert client.post(f"/admin/users/{user.id}/send-password-reset", headers=auth(admin)).status_code == 200
    assert client.post(f"/admin/users/{user.id}/send-password-reset", headers=auth(admin)).status_code == 429
    _expire_cooldown(db, user)
    outbox.fail = True
    assert client.post(f"/admin/users/{user.id}/send-password-reset", headers=auth(admin)).status_code == 502


@pytest.mark.req("FR-006")
def test_faculty_cannot_use_admin_reset(client, make):
    faculty, other = make.user(), make.user()
    assert client.post(f"/admin/users/{other.id}/send-password-reset", headers=auth(faculty)).status_code == 403
