"""Administration & oversight: FR-005..FR-007, FR-038, FR-040, FR-043, FR-044, BR-003, NFR-008."""
import pytest
from sqlalchemy import select

from app.models import AuditAction, AuditLog, RequestStatus, UserRole, UserStatus
from tests.conftest import auth, login

NEW = {"email": "made.by.admin@lnmiit.ac.in", "full_name": " New  Person ", "password": "Start1234", "role": "faculty"}


@pytest.fixture
def admin(make):
    return make.user(role=UserRole.admin, name="The Admin")


# ---------- Dashboard (FR-040) ----------

@pytest.mark.req("FR-040")
def test_dashboard_counts(client, make, admin):
    dept = make.department()
    a, b = make.faculty(department=dept), make.faculty(department=dept)
    make.faculty(department=dept, designation=None)        # incomplete profile
    make.user()                                             # active faculty, no profile (also incomplete)
    make.user(status=UserStatus.pending)
    make.user(status=UserStatus.inactive)
    make.collaborate(a, b)
    make.request(b, a)
    d = client.get("/admin/dashboard", headers=auth(admin)).json()
    assert d == {"registered_faculty": 4, "active_collaborations": 1, "pending_requests": 1,
                 "pending_registrations": 1, "departments": 1, "inactive_accounts": 1, "incomplete_profiles": 2}


# ---------- Accounts (FR-038) ----------

@pytest.mark.req("FR-038")
def test_list_users_with_search_and_filters(client, make, admin):
    make.user(name="Zed Pending", status=UserStatus.pending)
    manager = make.user(name="Head Of Dept", role=UserRole.dept_mgmt, department=make.department("Physics"))
    h = auth(admin)
    assert [u["full_name"] for u in client.get("/admin/users", headers=h, params={"q": "zed"}).json()["results"]] == ["Zed Pending"]
    rows = client.get("/admin/users", headers=h, params={"role": "dept_mgmt"}).json()["results"]
    assert rows[0]["id"] == manager.id and rows[0]["department_name"] == "Physics"
    assert client.get("/admin/users", headers=h, params={"status": "pending"}).json()["total"] == 1


@pytest.mark.req("FR-038", "BR-001", "BR-002")
def test_create_account(client, admin):
    h = auth(admin)
    assert client.post("/admin/users", headers=h, json={**NEW, "email": "x@gmail.com"}).status_code == 422
    assert client.post("/admin/users", headers=h, json={**NEW, "password": "short"}).status_code == 422
    r = client.post("/admin/users", headers=h, json=NEW)
    assert r.status_code == 201 and r.json()["status"] == "active" and r.json()["full_name"] == "New Person"
    assert client.post("/admin/users", headers=h, json=NEW).status_code == 409
    assert login(client, NEW["email"], NEW["password"]).status_code == 200


@pytest.mark.req("FR-005", "BR-003")
def test_assign_roles_and_managed_department(client, make, admin):
    h = auth(admin)
    user = make.user()
    dept = make.department()
    assert client.patch(f"/admin/users/{user.id}", headers=h, json={"role": "research_admin"}).json()["role"] == "research_admin"
    assert client.patch(f"/admin/users/{user.id}", headers=h, json={"role": "dept_mgmt"}).status_code == 422
    r = client.patch(f"/admin/users/{user.id}", headers=h, json={"role": "dept_mgmt", "department_id": dept.id})
    assert r.json()["department_id"] == dept.id
    assert client.patch(f"/admin/users/{user.id}", headers=h, json={"role": "faculty"}).json()["department_id"] is None


def test_admin_cannot_lock_themselves_out(client, make, admin):
    h = auth(admin)
    assert client.patch(f"/admin/users/{admin.id}", headers=h, json={"role": "faculty"}).status_code == 409
    assert client.post(f"/admin/users/{admin.id}/deactivate", headers=h).status_code == 409


@pytest.mark.req("FR-007", "BR-004")
def test_deactivate_and_activate(client, make, admin):
    h = auth(admin)
    user = make.user()
    assert client.post(f"/admin/users/{user.id}/deactivate", headers=h).json()["status"] == "inactive"
    assert login(client, user).status_code == 403
    assert client.post(f"/admin/users/{user.id}/deactivate", headers=h).status_code == 409
    assert client.post(f"/admin/users/{user.id}/activate", headers=h).json()["status"] == "active"
    pending = make.user(status=UserStatus.pending)
    assert client.post(f"/admin/users/{pending.id}/activate", headers=h).status_code == 409
    assert client.post(f"/admin/users/{pending.id}/deactivate", headers=h).status_code == 409


@pytest.mark.req("NFR-008")
def test_account_actions_are_audited_newest_first(client, make, admin, db):
    h = auth(admin)
    user = make.user()
    client.patch(f"/admin/users/{user.id}", headers=h, json={"role": "research_admin"})
    client.post(f"/admin/users/{user.id}/deactivate", headers=h)
    client.post(f"/admin/users/{user.id}/activate", headers=h)
    logs = client.get("/admin/audit-logs", headers=h).json()["results"]
    assert [l["action"] for l in logs] == ["account_activated", "account_deactivated", "role_changed"]
    assert logs[0]["actor_name"] == "The Admin" and logs[-1]["details"] == "Faculty -> Research Admin"
    only = client.get("/admin/audit-logs", headers=h, params={"action": "role_changed"}).json()["results"]
    assert [l["action"] for l in only] == ["role_changed"]


@pytest.mark.req("FR-006", "NFR-005")
@pytest.mark.parametrize("role", [UserRole.faculty, UserRole.research_admin, UserRole.dept_mgmt])
def test_non_admins_cannot_use_admin_endpoints(client, make, role):
    h = auth(make.user(role=role))
    for path in ("/admin/dashboard", "/admin/users", "/admin/audit-logs"):
        assert client.get(path, headers=h).status_code == 403


# ---------- Reports (FR-043 / FR-044) ----------

@pytest.fixture
def campus(make):
    one, two = make.department("Dept One"), make.department("Dept Two")
    f1 = make.faculty("F1", department=one, expertise=["Machine Learning", "Robotics"])
    f2 = make.faculty("F2", department=two, expertise=["machine learning"])
    f3 = make.faculty("F3", department=one, designation=None)
    make.collaborate(f1, f2)
    make.request(f3, f1)
    make.request(f2, f3, status=RequestStatus.declined)
    return {"one": one, "two": two, "f1": f1, "f2": f2, "f3": f3}


@pytest.mark.req("FR-043")
def test_activity_report(client, make, campus):
    rep = client.get("/reports/activity", headers=auth(make.user(role=UserRole.research_admin))).json()
    rows = {r["department"]: r for r in rep["by_department"]}
    one = rows["Dept One"]
    assert (one["faculty"], one["discoverable_profiles"], one["collaborations"], one["cross_department"], one["pending_requests"]) == (2, 1, 1, 1, 1)
    assert rep["collaborations"] == 1 and rep["cross_department_collaborations"] == 1
    assert rep["requests"]["declined"] == 1 and rep["acceptance_rate"] == 0.5
    assert rep["top_expertise"][0] == {"keyword": "Machine Learning", "count": 3}  # counted case-insensitively
    assert len(rep["collaborations_by_month"]) == 12 and rep["collaborations_by_month"][-1]["count"] == 1


@pytest.mark.req("FR-043", "FR-006")
def test_activity_report_access(client, make, campus):
    assert client.get("/reports/activity", headers=auth(make.user(role=UserRole.admin))).status_code == 200
    for role in (UserRole.faculty, UserRole.dept_mgmt):
        assert client.get("/reports/activity", headers=auth(make.user(role=role))).status_code == 403


@pytest.mark.req("FR-044")
def test_department_summary_scoped_to_managers_department(client, make, campus):
    manager = make.user(role=UserRole.dept_mgmt, department=campus["one"])
    r = client.get("/reports/department", headers=auth(manager), params={"department_id": campus["two"].id}).json()
    assert r["department"] == "Dept One"  # the parameter is ignored for department managers
    assert [f["full_name"] for f in r["faculty"]] == ["F1", "F3"]
    assert [f["discoverable"] for f in r["faculty"]] == [True, False]
    assert r["collaborations"][0]["partner_department"] == "Dept Two"
    assert r["requests"]["pending"] == 1


@pytest.mark.req("FR-044")
def test_department_summary_access_rules(client, make, campus):
    unassigned = make.user(role=UserRole.dept_mgmt)
    assert client.get("/reports/department", headers=auth(unassigned)).status_code == 409
    ra = auth(make.user(role=UserRole.research_admin))
    assert client.get("/reports/department", headers=ra).status_code == 422
    assert client.get("/reports/department", headers=ra, params={"department_id": campus["two"].id}).json()["department"] == "Dept Two"
    assert client.get("/reports/department", headers=auth(campus["f1"])).status_code == 403
