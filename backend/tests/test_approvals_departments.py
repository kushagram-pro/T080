"""Registration approvals and department management: FR-039, FR-006, NFR-008."""
import pytest
from sqlalchemy import select

from app.models import AuditAction, AuditLog, User, UserRole, UserStatus
from tests.conftest import auth, login


# ---------- Approvals ----------

def test_admin_lists_pending_oldest_first(client, make):
    admin = make.user(role=UserRole.admin)
    first, second = make.user(status=UserStatus.pending), make.user(status=UserStatus.pending)
    make.user()  # active, not listed
    ids = [u["id"] for u in client.get("/admin/approvals", headers=auth(admin)).json()]
    assert ids == [first.id, second.id]


@pytest.mark.req("NFR-008")
def test_approve_activates_emails_and_audits(client, make, outbox, db):
    admin, applicant = make.user(role=UserRole.admin), make.user(status=UserStatus.pending)
    r = client.post(f"/admin/approvals/{applicant.id}/approve", headers=auth(admin))
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert any("approved" in subject for _, subject, _ in outbox.to(applicant.email))
    assert db.scalar(select(AuditLog.action).where(AuditLog.target_user_id == applicant.id)) == AuditAction.account_approved
    assert login(client, applicant).status_code == 200


def test_reject_requires_reason_and_reason_is_emailed_escaped(client, make, outbox):
    admin = make.user(role=UserRole.admin)
    applicant = make.user(status=UserStatus.pending, name="<b>Bob</b>")
    assert client.post(f"/admin/approvals/{applicant.id}/reject", headers=auth(admin), json={"reason": "  "}).status_code == 422
    r = client.post(f"/admin/approvals/{applicant.id}/reject", headers=auth(admin), json={"reason": "Not <i>faculty</i>"})
    assert r.status_code == 200 and r.json()["status"] == "inactive"
    html = outbox.to(applicant.email)[-1][2]
    assert "&lt;i&gt;" in html and "&lt;b&gt;" in html


def test_cannot_process_twice_or_unknown(client, make):
    admin, applicant = make.user(role=UserRole.admin), make.user(status=UserStatus.pending)
    assert client.post(f"/admin/approvals/{applicant.id}/approve", headers=auth(admin)).status_code == 200
    assert client.post(f"/admin/approvals/{applicant.id}/approve", headers=auth(admin)).status_code == 409
    assert client.post("/admin/approvals/999999/approve", headers=auth(admin)).status_code == 404


@pytest.mark.req("FR-006", "NFR-005")
def test_only_admins_can_use_approvals(client, make):
    for role in (UserRole.faculty, UserRole.research_admin, UserRole.dept_mgmt):
        assert client.get("/admin/approvals", headers=auth(make.user(role=role))).status_code == 403
    assert client.get("/admin/approvals").status_code == 401


# ---------- Departments (FR-039) ----------

@pytest.mark.req("FR-039")
def test_admin_creates_edits_and_deletes_departments(client, make):
    h = auth(make.user(role=UserRole.admin))
    r = client.post("/departments", headers=h, json={"name": "  Computer   Science "})
    assert r.status_code == 201 and r.json()["name"] == "Computer Science" and r.json()["institute"] == "LNMIIT"
    dept_id = r.json()["id"]
    assert client.patch(f"/departments/{dept_id}", headers=h, json={"name": "CSE"}).json()["name"] == "CSE"
    assert client.delete(f"/departments/{dept_id}", headers=h).status_code == 204
    assert client.get(f"/departments/{dept_id}", headers=h).status_code == 404


@pytest.mark.req("FR-039")
def test_department_names_unique_case_insensitive(client, make):
    h = auth(make.user(role=UserRole.admin))
    client.post("/departments", headers=h, json={"name": "Physics"})
    other = client.post("/departments", headers=h, json={"name": "Maths"}).json()["id"]
    assert client.post("/departments", headers=h, json={"name": "PHYSICS"}).status_code == 409
    assert client.patch(f"/departments/{other}", headers=h, json={"name": "physics"}).status_code == 409
    assert client.patch(f"/departments/{other}", headers=h, json={}).status_code == 422


@pytest.mark.req("FR-039")
def test_department_in_use_cannot_be_deleted(client, make):
    h = auth(make.user(role=UserRole.admin))
    with_faculty = make.department()
    make.faculty(department=with_faculty)
    with_manager = make.department()
    make.user(role=UserRole.dept_mgmt, department=with_manager)
    assert client.delete(f"/departments/{with_faculty.id}", headers=h).status_code == 409
    assert client.delete(f"/departments/{with_manager.id}", headers=h).status_code == 409


def test_any_logged_in_user_can_list_departments_with_counts(client, make):
    dept = make.department("Electronics")
    make.faculty(department=dept)
    rows = client.get("/departments", headers=auth(make.user())).json()
    assert {"name": "Electronics", "faculty_count": 1}.items() <= next(r for r in rows if r["id"] == dept.id).items()
    assert client.get("/departments").status_code == 401


@pytest.mark.req("FR-006")
def test_faculty_cannot_change_departments(client, make):
    assert client.post("/departments", headers=auth(make.user()), json={"name": "Hack"}).status_code == 403


@pytest.mark.req("NFR-008")
def test_department_changes_are_audited(client, make, db):
    admin = make.user(role=UserRole.admin)
    h = auth(admin)
    dept_id = client.post("/departments", headers=h, json={"name": "Audited"}).json()["id"]
    client.patch(f"/departments/{dept_id}", headers=h, json={"name": "Audited 2"})
    client.delete(f"/departments/{dept_id}", headers=h)
    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.actor_id == admin.id)))
    assert {AuditAction.department_created, AuditAction.department_updated, AuditAction.department_deleted} <= actions
