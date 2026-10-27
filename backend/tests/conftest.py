"""Shared test setup.

Tests run against a SEPARATE database: the dev database name + "_test" (e.g. faculty_portal_test),
or TEST_DATABASE_URL if set. It is created and migrated automatically, and every table is emptied
before each test, so tests never touch real data and never depend on each other.
"""
import os
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# --- Point the app at the test database BEFORE app.database creates its engine ---
from app.config import settings

_dev_url = make_url(settings.DATABASE_URL)
_test_url = make_url(os.environ["TEST_DATABASE_URL"]) if os.environ.get("TEST_DATABASE_URL") \
    else _dev_url.set(database=f"{_dev_url.database}_test")
if not _test_url.database.endswith("_test"):
    raise RuntimeError(f"Refusing to run tests against '{_test_url.database}': the test database name must end in _test")
settings.DATABASE_URL = _test_url.render_as_string(hide_password=False)

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Collaboration,
    CollaborationRequest,
    Department,
    ExpertiseKeyword,
    FacultyProfile,
    RequestStatus,
    ResearchInterest,
    User,
    UserRole,
    UserStatus,
)
from app.security import email as email_module  # noqa: E402
from app.security.hashing import hash_password  # noqa: E402
from app.security.jwt import create_access_token  # noqa: E402
from app.services.collaboration import ordered_pair  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "Passw0rd!"
_HASHED = hash_password(PASSWORD)  # bcrypt is slow on purpose; hash the shared test password once


# ---------- Database lifecycle ----------

def _create_test_database():
    admin = create_engine(_test_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        exists = c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _test_url.database}).scalar()
        if not exists:
            c.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Create the test database if needed and bring it to the latest migration (also tests the migrations)."""
    _create_test_database()
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    yield
    engine.dispose()


TABLES = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    yield


# ---------- Side effects: email and rate limits ----------

class Outbox(list):
    """Captured emails: (to, subject, html). Set .fail = True to simulate SendGrid being down."""
    fail = False

    def to(self, address: str):
        return [m for m in self if m[0] == address]

    def reset_token_for(self, address: str) -> str | None:
        for to, subject, html in reversed(self):
            if to == address and "Reset" in subject:
                m = re.search(r"#token=([A-Za-z0-9_\-]+)", html)
                return m.group(1) if m else None
        return None


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    box = Outbox()

    def fake_send(to, subject, html):
        box.append((to, subject, html))
        return not box.fail

    monkeypatch.setattr(email_module, "send_email", fake_send)
    monkeypatch.setattr(email_module, "_email_enabled", lambda: True)
    return box


@pytest.fixture(autouse=True)
def _no_rate_limits():
    limiter.enabled = False
    yield
    limiter.enabled = False
    limiter.reset()


# ---------- Clients and data builders ----------

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def new_client():
    """For tests that need several independent browsers (separate cookie jars)."""
    return lambda: TestClient(app)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def auth(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


def login(client: TestClient, user_or_email, password: str = PASSWORD):
    email = user_or_email if isinstance(user_or_email, str) else user_or_email.email
    return client.post("/auth/login", json={"email": email, "password": password})


class Factory:
    def __init__(self, db):
        self.db = db
        self.n = 0

    def _next(self):
        self.n += 1
        return self.n

    def department(self, name: str | None = None) -> Department:
        d = Department(name=name or f"Department {self._next()}", institute="LNMIIT")
        self.db.add(d)
        self.db.commit()
        return d

    def user(self, *, role=UserRole.faculty, status=UserStatus.active, email=None, name=None,
             password=PASSWORD, department=None, rejection_reason=None) -> User:
        n = self._next()
        u = User(
            email=email or f"user{n}@lnmiit.ac.in",
            full_name=name or f"User {n}",
            hashed_password=_HASHED if password == PASSWORD else hash_password(password),
            role=role, status=status, rejection_reason=rejection_reason,
            department_id=department.id if department else None,
        )
        self.db.add(u)
        self.db.commit()
        return u

    def faculty(self, name=None, *, department=None, designation="Professor", expertise=("Machine Learning",),
                interests=(), status=UserStatus.active, email=None) -> User:
        """Faculty user with a profile (complete unless designation/expertise are left empty)."""
        department = department or self.department()
        u = self.user(name=name, status=status, email=email)
        self.db.add(FacultyProfile(
            user_id=u.id, full_name=u.full_name, department_id=department.id, designation=designation,
            expertise_keywords=[ExpertiseKeyword(keyword=k) for k in expertise],
            research_interests=[ResearchInterest(topic=t) for t in interests],
        ))
        self.db.commit()
        return u

    def request(self, sender: User, recipient: User, status=RequestStatus.pending, message=None) -> CollaborationRequest:
        r = CollaborationRequest(sender_id=sender.id, recipient_id=recipient.id, status=status, message=message)
        self.db.add(r)
        self.db.commit()
        return r

    def collaborate(self, a: User, b: User) -> Collaboration:
        req = self.request(a, b, status=RequestStatus.accepted)
        x, y = ordered_pair(a.id, b.id)
        c = Collaboration(request_id=req.id, faculty_a=x, faculty_b=y)
        self.db.add(c)
        self.db.commit()
        return c


@pytest.fixture
def make(db):
    return Factory(db)


# ---------- Requirement traceability report ----------
# Tag tests with @pytest.mark.req("FR-026", "BR-009"); run with --req-report=PATH to write a
# Markdown table for the SRS traceability matrix's "Test" column.

SRS_IDS = (
    [f"FR-{i:03d}" for i in range(1, 45)]   # SRS section 13 numbering
    + [f"BR-{i:03d}" for i in range(1, 20)]
)


def pytest_addoption(parser):
    parser.addoption("--req-report", action="store", default=None,
                     help="write a requirements traceability table (Markdown) to this path")


def pytest_configure(config):
    config._req_results = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" or (rep.when == "setup" and rep.outcome != "passed"):
        for mark in item.iter_markers("req"):
            for rid in mark.args:
                item.config._req_results.setdefault(rid, []).append((item.name, rep.outcome))


def _sort_key(rid):
    prefix, _, num = rid.partition("-")
    order = {"FR": 0, "BR": 1, "NFR": 2, "AC": 3}.get(prefix, 9)
    return order, int(num) if num.isdigit() else 0


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    results = config._req_results
    if not results:
        return
    ids = sorted(set(results) | set(SRS_IDS), key=_sort_key)
    covered = [r for r in SRS_IDS if r in results]
    failing = [r for r in ids if any(o != "passed" for _, o in results.get(r, []))]
    missing = [r for r in SRS_IDS if r not in results]

    tr = terminalreporter
    tr.section("SRS requirement coverage")
    tr.write_line(f"FR/BR covered: {len(covered)}/{len(SRS_IDS)}   failing: {len(failing)}   not covered: {len(missing)}")
    if failing:
        tr.write_line("Failing: " + ", ".join(failing))
    if missing:
        tr.write_line("Not covered: " + ", ".join(missing))

    path = config.getoption("--req-report")
    if path:
        lines = ["| Requirement | Result | Tests |", "|---|---|---|"]
        for rid in ids:
            tests = results.get(rid, [])
            if not tests:
                status = "NOT TESTED"
            elif all(o == "passed" for _, o in tests):
                status = "PASS"
            else:
                status = "FAIL"
            names = "<br>".join(f"`{n}`" for n, _ in tests) or "-"
            lines.append(f"| {rid} | {status} | {names} |")
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        tr.write_line(f"Traceability table written to {path}")
