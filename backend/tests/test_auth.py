"""Authentication & account basics: FR-001..FR-004, FR-006, BR-001, BR-002, BR-004, NFR-004, NFR-006."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.limiter import limiter
from app.models import RefreshToken, User, UserStatus
from app.security.jwt import REFRESH_COOKIE_NAME, create_refresh_token
from tests.conftest import PASSWORD, auth, login

REG = {"email": "new.person@lnmiit.ac.in", "password": PASSWORD, "full_name": "New Person"}


# ---------- Registration ----------

@pytest.mark.req("FR-001")
def test_register_creates_pending_account(client, db):
    r = client.post("/auth/register", json={**REG, "full_name": "  New   Person "})
    assert r.status_code == 201
    user = db.scalar(select(User).where(User.email == REG["email"]))
    assert user.status == UserStatus.pending and user.full_name == "New Person"


@pytest.mark.req("BR-001")
def test_register_rejects_non_institutional_email(client):
    r = client.post("/auth/register", json={**REG, "email": "someone@gmail.com"})
    assert r.status_code == 422


@pytest.mark.req("BR-002")
def test_register_rejects_duplicate_email_case_insensitive(client):
    assert client.post("/auth/register", json=REG).status_code == 201
    r = client.post("/auth/register", json={**REG, "email": REG["email"].upper()})
    assert r.status_code == 409


@pytest.mark.parametrize("password", ["short1", "lettersonly", "12345678", "x" * 73 + "1"])
def test_register_enforces_password_rules(client, password):
    assert client.post("/auth/register", json={**REG, "password": password}).status_code == 422


@pytest.mark.req("BR-002")
def test_rejected_applicant_can_reapply_on_same_account(client, make, db):
    u = make.user(email="again@lnmiit.ac.in", status=UserStatus.inactive, rejection_reason="Not faculty")
    r = client.post("/auth/register", json={"email": "again@lnmiit.ac.in", "password": "Another123", "full_name": "Again"})
    assert r.status_code == 201
    db.refresh(u)
    assert u.status == UserStatus.pending and u.rejection_reason is None


def test_deactivated_account_cannot_reregister(client, make):
    make.user(email="gone@lnmiit.ac.in", status=UserStatus.inactive)
    r = client.post("/auth/register", json={"email": "gone@lnmiit.ac.in", "password": PASSWORD, "full_name": "X"})
    assert r.status_code == 409


@pytest.mark.req("NFR-006")
def test_password_is_stored_hashed(client, db):
    client.post("/auth/register", json=REG)
    stored = db.scalar(select(User.hashed_password).where(User.email == REG["email"]))
    assert stored != PASSWORD and stored.startswith("$2")  # bcrypt


# ---------- Login / logout ----------

@pytest.mark.req("FR-002")
def test_login_returns_access_token_and_httponly_refresh_cookie(client, make):
    user = make.user()
    r = login(client, user)
    assert r.status_code == 200 and r.json()["access_token"]
    assert r.json()["user"]["email"] == user.email
    cookie = r.headers["set-cookie"]
    assert REFRESH_COOKIE_NAME in cookie and "HttpOnly" in cookie


@pytest.mark.req("FR-003")
def test_failed_login_does_not_reveal_which_field_was_wrong(client, make):
    user = make.user()
    wrong_password = login(client, user, "Wrong1234")
    unknown_email = login(client, "nobody@lnmiit.ac.in")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_pending_account_cannot_log_in(client, make):
    r = login(client, make.user(status=UserStatus.pending))
    assert r.status_code == 403 and "awaiting" in r.json()["detail"]


@pytest.mark.req("BR-004", "FR-007")
def test_deactivated_account_cannot_log_in(client, make):
    r = login(client, make.user(status=UserStatus.inactive))
    assert r.status_code == 403 and "deactivated" in r.json()["detail"]


def test_rejected_applicant_sees_reason_at_login(client, make):
    r = login(client, make.user(status=UserStatus.inactive, rejection_reason="Use your faculty email"))
    assert r.status_code == 403 and "Use your faculty email" in r.json()["detail"]


@pytest.mark.req("FR-004")
def test_logout_revokes_refresh_token_server_side(new_client, make):
    user = make.user()
    browser = new_client()
    login(browser, user)
    stolen_copy = browser.cookies.get(REFRESH_COOKIE_NAME)
    assert browser.post("/auth/logout").status_code == 204
    # A copy of the cookie taken before logout no longer works
    r = new_client().post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: stolen_copy})
    assert r.status_code == 401


@pytest.mark.req("NFR-004")
def test_protected_endpoint_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client, make):
    user = make.user()
    assert client.get("/auth/me", headers=auth(user)).json()["email"] == user.email


@pytest.mark.req("BR-004", "FR-007")
def test_deactivation_invalidates_existing_access_token(client, make, db):
    user = make.user()
    headers = auth(user)
    db.execute(update(User).where(User.id == user.id).values(status=UserStatus.inactive))
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_rate_limit_on_login(client, make):
    limiter.enabled = True
    user = make.user()
    codes = [login(client, user, "Wrong1234").status_code for _ in range(12)]
    assert 429 in codes


# ---------- Server-side sessions (refresh token rotation & revocation) ----------

def test_refresh_rotates_token(client, make, db):
    login(client, make.user())
    first = client.cookies.get(REFRESH_COOKIE_NAME)
    r = client.post("/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    assert client.cookies.get(REFRESH_COOKIE_NAME) != first


def test_second_tab_reusing_just_rotated_token_is_tolerated(new_client, make):
    browser = new_client()
    login(browser, make.user())
    old = browser.cookies.get(REFRESH_COOKIE_NAME)
    browser.post("/auth/refresh")
    assert new_client().post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: old}).status_code == 200


def test_replayed_old_token_revokes_all_sessions(new_client, make, db):
    user = make.user()
    browser = new_client()
    login(browser, user)
    stolen = browser.cookies.get(REFRESH_COOKIE_NAME)
    browser.post("/auth/refresh")
    current = browser.cookies.get(REFRESH_COOKIE_NAME)
    # Pretend the rotation happened 5 minutes ago (outside the grace window)
    db.execute(update(RefreshToken).where(RefreshToken.replaced_by.is_not(None))
               .values(revoked_at=datetime.utcnow() - timedelta(minutes=5)))
    db.commit()
    assert new_client().post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: stolen}).status_code == 401
    assert new_client().post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: current}).status_code == 401


def test_unrecorded_refresh_token_is_rejected(client, make):
    token, _, _ = create_refresh_token(make.user().id)
    assert client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: token}).status_code == 401


def test_access_token_is_not_accepted_as_refresh_token(client, make):
    access = login(client, make.user()).json()["access_token"]
    assert client.post("/auth/refresh", cookies={REFRESH_COOKIE_NAME: access}).status_code == 401


def test_change_password_signs_out_other_devices(new_client, make):
    user = make.user()
    phone, laptop = new_client(), new_client()
    login(phone, user)
    token = login(laptop, user).json()["access_token"]
    r = laptop.post("/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                    json={"current_password": PASSWORD, "new_password": "Changed123"})
    assert r.status_code == 200
    assert phone.post("/auth/refresh").status_code == 401
    assert laptop.post("/auth/refresh").status_code == 200
    assert login(new_client(), user, "Changed123").status_code == 200


@pytest.mark.parametrize("body,field", [
    ({"current_password": "Wrong1234", "new_password": "Changed123"}, "current_password"),
    ({"current_password": PASSWORD, "new_password": PASSWORD}, "new_password"),
    ({"current_password": PASSWORD, "new_password": "weakweak"}, "new_password"),
])
def test_change_password_validation(client, make, body, field):
    r = client.post("/auth/change-password", headers=auth(make.user()), json=body)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"][-1] == field
