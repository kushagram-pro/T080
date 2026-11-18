"""Features added beyond the SRS, tagged EXT-xxx in the traceability table.

EXT-001 collaboration messaging       EXT-005 audit log filters
EXT-002 ending a collaboration        EXT-006 admin dashboard trends
EXT-003 hiding a profile from search  EXT-007 weekly email digest
EXT-004 CSV export of reports         EXT-008 joint projects
EXT-009 search by name (tests in test_search_suggestions.py)
"""
import csv
import io
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    AuditAction,
    AuditLog,
    Collaboration,
    CollaborationMessage,
    Notification,
    NotificationType,
    Project,
    ProjectStatus,
    UserRole,
    UserStatus,
)
from app.services import digest
from tests.conftest import auth


@pytest.fixture
def pair(make):
    dept = make.department("CSE")
    a = make.faculty("Alice", department=dept, expertise=["Machine Learning"])
    b = make.faculty("Bob", department=dept, expertise=["Machine Learning"])
    collab = make.collaborate(a, b)
    return a, b, collab


def say(client, user, collab, text):
    return client.post(f"/collaborations/{collab.id}/messages", headers=auth(user), json={"body": text})


def thread(client, user, collab, **params):
    return client.get(f"/collaborations/{collab.id}/messages", headers=auth(user), params=params)


# ---------- EXT-001: messaging ----------

@pytest.mark.req("EXT-001")
def test_collaborators_can_message_each_other(client, pair):
    a, b, collab = pair
    r = say(client, a, collab, "  Hello Bob  ")
    assert r.status_code == 201 and r.json()["body"] == "Hello Bob" and r.json()["mine"] is True
    say(client, b, collab, "Hi Alice")

    t = thread(client, a, collab).json()
    assert [(m["body"], m["mine"]) for m in t["messages"]] == [("Hello Bob", True), ("Hi Alice", False)]
    assert t["can_send"] is True and t["other"]["full_name"] == "Bob"


@pytest.mark.req("EXT-001", "BR-019")
def test_only_the_two_collaborators_can_read_or_write(client, pair, make):
    a, b, collab = pair
    outsider = make.faculty("Eve")
    assert thread(client, outsider, collab).status_code == 404
    assert say(client, outsider, collab, "hi").status_code == 404
    assert client.get(f"/collaborations/{collab.id}/messages", headers=auth(make.user(role=UserRole.admin))).status_code == 403


@pytest.mark.req("EXT-001")
@pytest.mark.parametrize("body", ["", "   ", "x" * 2001])
def test_message_must_be_1_to_2000_characters(client, pair, body):
    a, _, collab = pair
    assert say(client, a, collab, body).status_code == 422


@pytest.mark.req("EXT-001")
def test_unread_counts_and_one_notification_per_conversation(client, pair, db):
    a, b, collab = pair
    for text in ("one", "two", "three"):
        say(client, a, collab, text)

    mine = client.get("/collaborations", headers=auth(b)).json()
    assert mine[0]["unread_messages"] == 3
    notes = db.scalars(select(Notification).where(Notification.recipient_id == b.id)).all()
    assert len(notes) == 1 and notes[0].type == NotificationType.message_received  # refreshed, not repeated

    assert client.post(f"/collaborations/{collab.id}/messages/read", headers=auth(b)).status_code == 204
    assert client.get("/collaborations", headers=auth(b)).json()[0]["unread_messages"] == 0
    db.expire_all()
    assert db.get(Notification, notes[0].id).is_read is True
    assert all(m["read_at"] for m in thread(client, a, collab).json()["messages"])  # the sender sees "read"


@pytest.mark.req("EXT-001")
def test_paging_older_and_polling_newer(client, pair):
    a, _, collab = pair
    for i in range(5):
        say(client, a, collab, f"m{i}")
    latest = thread(client, a, collab, limit=2).json()
    assert [m["body"] for m in latest["messages"]] == ["m3", "m4"] and latest["has_more"] is True
    older = thread(client, a, collab, limit=10, before_id=latest["messages"][0]["id"]).json()
    assert [m["body"] for m in older["messages"]] == ["m0", "m1", "m2"] and older["has_more"] is False
    assert thread(client, a, collab, after_id=latest["messages"][-1]["id"]).json()["messages"] == []


@pytest.mark.req("EXT-001", "BR-004")
def test_cannot_message_a_deactivated_partner(client, pair, db):
    a, b, collab = pair
    b.status = UserStatus.inactive
    db.commit()
    assert say(client, a, collab, "still there?").status_code == 409
    assert thread(client, a, collab).json()["can_send"] is False


# ---------- EXT-002: ending a collaboration ----------

@pytest.mark.req("EXT-002")
def test_either_person_can_end_and_the_other_is_notified(client, pair, db):
    a, b, collab = pair
    say(client, a, collab, "before")
    r = client.post(f"/collaborations/{collab.id}/end", headers=auth(b))
    assert r.status_code == 200 and r.json()["ended_by_me"] is True and r.json()["ended_at"]
    assert client.post(f"/collaborations/{collab.id}/end", headers=auth(a)).status_code == 409

    note = db.scalars(select(Notification).where(Notification.recipient_id == a.id)).all()[-1]
    assert note.type == NotificationType.collaboration_ended and note.request_id == collab.request_id

    # History stays readable, but no new messages; the relationship is back to "none"
    t = thread(client, a, collab).json()
    assert [m["body"] for m in t["messages"]] == ["before"] and t["can_send"] is False
    assert say(client, a, collab, "after").status_code == 409
    assert client.get(f"/collaborations/status/{b.id}", headers=auth(a)).json()["state"] == "none"
    listed = client.get("/collaborations", headers=auth(a)).json()
    assert listed[0]["ended_at"] and listed[0]["ended_by_me"] is False


@pytest.mark.req("EXT-002", "BR-014")
def test_pair_can_collaborate_again_after_ending(client, pair, db):
    a, b, collab = pair
    client.post(f"/collaborations/{collab.id}/end", headers=auth(a))
    req = client.post("/collaborations/requests", headers=auth(a), json={"recipient_id": b.id}).json()
    assert client.post(f"/collaborations/requests/{req['id']}/accept", headers=auth(b)).status_code == 200
    db.expire_all()
    rows = db.scalars(select(Collaboration).order_by(Collaboration.id)).all()
    assert len(rows) == 2 and rows[0].ended_at is not None and rows[1].ended_at is None
    # Ongoing first, then the ended one
    assert [c["ended_at"] is None for c in client.get("/collaborations", headers=auth(a)).json()] == [True, False]


@pytest.mark.req("EXT-002")
def test_ended_collaborations_drop_out_of_counts_and_suggestions(client, pair, make):
    a, b, collab = pair
    admin = auth(make.user(role=UserRole.admin))
    assert client.get("/admin/dashboard", headers=admin).json()["active_collaborations"] == 1
    assert client.get("/suggestions", headers=auth(a)).json() == []  # Bob is a collaborator

    client.post(f"/collaborations/{collab.id}/end", headers=auth(a))
    assert client.get("/admin/dashboard", headers=admin).json()["active_collaborations"] == 0
    assert [s["full_name"] for s in client.get("/suggestions", headers=auth(a)).json()] == ["Bob"]
    rep = client.get("/reports/activity", headers=admin).json()
    assert rep["collaborations"] == 0 and rep["ended_collaborations"] == 1
    assert rep["collaborations_by_month"][-1]["count"] == 1  # it was still new that month


# ---------- EXT-003: hiding a profile ----------

def hide(client, user, hidden=True):
    return client.patch("/profiles/me", headers=auth(user), json={"is_hidden": hidden})


@pytest.mark.req("EXT-003", "BR-005")
def test_hidden_profile_leaves_search_and_suggestions(client, make):
    dept = make.department()
    me = make.faculty("Me", department=dept, expertise=["Robotics"])
    other = make.faculty("Hidden One", department=dept, expertise=["Robotics"])
    r = hide(client, other)
    assert r.status_code == 200 and r.json()["is_hidden"] is True and r.json()["is_discoverable"] is True

    assert client.get("/search", headers=auth(me), params={"q": "robotics"}).json()["total"] == 0
    assert client.get("/suggestions", headers=auth(me)).json() == []
    assert client.get(f"/profiles/{other.id}", headers=auth(me)).status_code == 404
    assert client.post("/collaborations/requests", headers=auth(me), json={"recipient_id": other.id}).status_code == 404

    # Oversight roles still see it; un-hiding brings it back
    ra = auth(make.user(role=UserRole.research_admin))
    assert client.get("/search", headers=ra, params={"q": "robotics"}).json()["total"] == 2
    hide(client, other, False)
    assert client.get("/search", headers=auth(me), params={"q": "robotics"}).json()["total"] == 1


@pytest.mark.req("EXT-003")
def test_collaborators_can_still_open_a_hidden_profile(client, pair):
    a, b, _ = pair
    hide(client, b)
    assert client.get(f"/profiles/{b.id}", headers=auth(a)).status_code == 200


@pytest.mark.req("EXT-003")
def test_hidden_counts_in_reports(client, pair, make):
    a, b, _ = pair
    hide(client, b)
    admin = auth(make.user(role=UserRole.admin))
    rep = client.get("/reports/department", headers=admin, params={"department_id": a.profile.department_id}).json()
    rows = {f["full_name"]: f for f in rep["faculty"]}
    assert rows["Bob"]["hidden"] is True and rows["Bob"]["discoverable"] is False
    assert rows["Alice"]["hidden"] is False and rows["Alice"]["discoverable"] is True


def test_is_hidden_cannot_be_null(client, pair):
    assert client.patch("/profiles/me", headers=auth(pair[0]), json={"is_hidden": None}).status_code == 422


# ---------- EXT-004: CSV export ----------

def read_csv(response):
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


@pytest.mark.req("EXT-004", "FR-043")
def test_activity_report_csv(client, pair, make):
    rows = read_csv(client.get("/reports/activity.csv", headers=auth(make.user(role=UserRole.research_admin))))
    assert rows[0][:2] == ["Department", "Faculty"] and rows[1][:2] == ["CSE", "2"]


@pytest.mark.req("EXT-004", "FR-044")
def test_department_csv_and_access(client, pair, make):
    a, _, _ = pair
    dept = a.profile.department
    manager = make.user(role=UserRole.dept_mgmt, department=dept)
    rows = read_csv(client.get("/reports/department.csv", headers=auth(manager)))
    assert rows[0][0] == "Name" and sorted(r[0] for r in rows[1:]) == ["Alice", "Bob"]
    assert client.get("/reports/department.csv", headers=auth(a)).status_code == 403
    assert client.get("/reports/activity.csv", headers=auth(manager)).status_code == 403


@pytest.mark.req("EXT-004")
def test_csv_cells_cannot_run_as_formulas(client, make):
    make.faculty("=HYPERLINK(\"http://evil\")", department=make.department("Dept"))
    rows = read_csv(client.get("/reports/department.csv", headers=auth(make.user(role=UserRole.admin)),
                               params={"department_id": 1}))
    assert rows[1][0].startswith("'=")


# ---------- EXT-005: audit log filters ----------

@pytest.mark.req("EXT-005", "NFR-008")
def test_audit_log_filters(client, make, db):
    admin1, admin2 = make.user(role=UserRole.admin, name="Admin One"), make.user(role=UserRole.admin, name="Admin Two")
    target = make.user(name="Target Person", email="target@lnmiit.ac.in")
    old = datetime(2026, 1, 15, 10, 0)
    db.add_all([
        AuditLog(actor_id=admin1.id, action=AuditAction.account_created, target_user_id=target.id, created_at=old),
        AuditLog(actor_id=admin2.id, action=AuditAction.role_changed, target_user_id=target.id),
        AuditLog(actor_id=admin2.id, action=AuditAction.department_created, details="#1 Dept"),
    ])
    db.commit()
    h = auth(admin1)

    def total(**params):
        return client.get("/admin/audit-logs", headers=h, params=params).json()["total"]

    assert total() == 3
    assert total(actor_id=admin2.id) == 2
    assert total(target="TARGET@lnmiit") == 2 and total(target="person") == 2 and total(target="nobody") == 0
    assert total(date_from="2026-01-15", date_to="2026-01-15") == 1
    assert total(date_to="2026-01-14") == 0
    assert total(actor_id=admin2.id, action="role_changed") == 1
    assert client.get("/admin/audit-logs", headers=h, params={"date_from": "2026-02-01", "date_to": "2026-01-01"}).status_code == 422


# ---------- EXT-006: dashboard trends ----------

@pytest.mark.req("EXT-006", "FR-040")
def test_dashboard_trends(client, pair, make):
    a, b, _ = pair
    make.request(a, make.faculty("Carol"))
    t = client.get("/admin/dashboard/trends", headers=auth(make.user(role=UserRole.admin)))
    assert t.status_code == 200
    t = t.json()
    assert all(len(t[k]) == 12 for k in ("registrations", "collaborations", "requests"))
    assert t["registrations"][-1] == {"month": date.today().strftime("%Y-%m"), "count": 3}  # faculty only
    assert t["collaborations"][-1]["count"] == 1 and t["requests"][-1]["count"] == 2
    assert client.get("/admin/dashboard/trends", headers=auth(a)).status_code == 403


# ---------- EXT-007: weekly email digest ----------

@pytest.mark.req("EXT-007")
def test_digest_lists_pending_requests_unread_messages_and_new_matches(client, pair, make, db, outbox):
    a, b, collab = pair
    say(client, b, collab, "ping")
    make.request(make.faculty("Requester"), a)
    make.faculty("Newcomer", expertise=["Machine Learning"])

    sent, skipped = digest.send_due(db)
    mail = outbox.to(a.email)
    assert len(mail) == 1 and "weekly" in mail[0][1].lower()
    html = mail[0][2]
    assert "Requester" in html and "Bob (1)" in html and "Newcomer: Machine Learning" in html

    # Sent at most once a week
    outbox.clear()
    digest.send_due(db)
    assert outbox.to(a.email) == []
    digest.send_due(db, now=datetime.utcnow() + timedelta(days=7))
    assert len(outbox.to(a.email)) == 1


@pytest.mark.req("EXT-007")
def test_digest_skips_people_with_nothing_new_or_who_opted_out(client, pair, make, db, outbox):
    a, b, collab = pair
    assert client.patch("/auth/me/preferences", headers=auth(b), json={"email_digest": False}).json()["email_digest"] is False
    say(client, a, collab, "for Bob")
    digest.send_due(db)
    assert outbox.to(b.email) == []      # opted out
    assert outbox.to(a.email) == []      # nothing new for Alice
    assert client.get("/auth/me", headers=auth(a)).json()["email_digest"] is True  # on by default


# ---------- EXT-008: joint projects ----------

@pytest.fixture
def project(make, pair, db):
    a, _, _ = pair
    p = Project(profile_id=a.profile.id, title="Shared robot", status=ProjectStatus.ongoing, start_date=date(2025, 1, 1))
    db.add(p)
    db.commit()
    return p


def set_members(client, user, project, ids):
    return client.put(f"/profiles/me/projects/{project.id}/members", headers=auth(user), json={"user_ids": ids})


@pytest.mark.req("EXT-008")
def test_joint_project_shows_on_both_profiles(client, pair, project):
    a, b, _ = pair
    r = set_members(client, a, project, [b.id, b.id])
    assert r.status_code == 200 and r.json()["members"] == [{"user_id": b.id, "full_name": "Bob"}]

    mine = client.get("/profiles/me", headers=auth(a)).json()
    assert mine["projects"][0]["members"][0]["full_name"] == "Bob"
    theirs = client.get(f"/profiles/{b.id}", headers=auth(a)).json()
    assert theirs["joint_projects"][0]["title"] == "Shared robot"
    assert theirs["joint_projects"][0]["owner"] == {"user_id": a.id, "full_name": "Alice"}


@pytest.mark.req("EXT-008")
def test_only_current_collaborators_can_be_added(client, pair, project, make):
    a, b, collab = pair
    assert set_members(client, a, project, [make.faculty("Stranger").id]).status_code == 422
    set_members(client, a, project, [b.id])
    client.post(f"/collaborations/{collab.id}/end", headers=auth(a))
    assert set_members(client, a, project, [b.id]).status_code == 200  # already listed: stays
    assert set_members(client, a, project, []).json()["members"] == []
    assert set_members(client, a, project, [b.id]).status_code == 422  # can't re-add after ending


@pytest.mark.req("EXT-008", "BR-006")
def test_member_can_leave_but_not_edit(client, pair, project):
    a, b, _ = pair
    set_members(client, a, project, [b.id])
    assert set_members(client, b, project, []).status_code == 404  # not Bob's project
    assert client.delete(f"/profiles/me/joint-projects/{project.id}", headers=auth(b)).status_code == 204
    assert client.get("/profiles/me", headers=auth(b)).json()["joint_projects"] == []
    assert client.delete(f"/profiles/me/joint-projects/{project.id}", headers=auth(b)).status_code == 404


@pytest.mark.req("EXT-008")
def test_deleting_a_project_removes_its_members(client, pair, project, db):
    a, b, _ = pair
    set_members(client, a, project, [b.id])
    assert client.delete(f"/profiles/me/projects/{project.id}", headers=auth(a)).status_code == 204
    assert client.get("/profiles/me", headers=auth(b)).json()["joint_projects"] == []
