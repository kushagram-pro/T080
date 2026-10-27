"""Collaboration requests & notifications: FR-026..FR-037, BR-009..BR-014, BR-018, BR-019, AC-001..AC-010."""
import threading

import pytest
from sqlalchemy import select

from app.models import Collaboration, Notification, NotificationType, RequestStatus, UserRole, UserStatus
from tests.conftest import auth


def send(client, sender, recipient_id, message=None):
    return client.post("/collaborations/requests", headers=auth(sender), json={"recipient_id": recipient_id, "message": message})


@pytest.fixture
def ab(make):
    dept = make.department()
    return make.faculty("Alice", department=dept), make.faculty("Bob", department=dept)


# ---------- Sending (UC-014) ----------

@pytest.mark.req("FR-026", "FR-027", "AC-007", "AC-008")
def test_send_request_with_message(client, ab):
    a, b = ab
    r = send(client, a, b.id, "  Let's work together!  ")
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending" and body["direction"] == "sent"
    assert body["message"] == "Let's work together!" and body["other"]["full_name"] == "Bob"


@pytest.mark.req("FR-027", "AC-006", "AC-010")
def test_message_limited_to_500_characters(client, ab):
    a, b = ab
    assert send(client, a, b.id, "x" * 501).status_code == 422
    assert send(client, a, b.id, "x" * 500).status_code == 201


@pytest.mark.req("FR-029", "BR-009", "AC-004")
def test_cannot_request_yourself(client, ab):
    a, _ = ab
    r = send(client, a, a.id)
    assert r.status_code == 422 and "yourself" in r.json()["detail"]


@pytest.mark.req("BR-013", "AC-002")
def test_cannot_request_deactivated_faculty(client, make, ab):
    a, _ = ab
    gone = make.faculty("Gone", status=UserStatus.inactive)
    assert send(client, a, gone.id).status_code == 409


@pytest.mark.req("AC-003")
def test_cannot_request_incomplete_profile(client, make, ab):
    a, _ = ab
    incomplete = make.faculty("Incomplete", designation=None)
    assert send(client, a, incomplete.id).status_code == 409


def test_sender_needs_profile_and_recipient_must_be_faculty(client, make, ab):
    a, b = ab
    assert send(client, make.user(), b.id).status_code == 409
    assert send(client, a, make.user(role=UserRole.admin).id).status_code == 404
    assert send(client, a, 999999).status_code == 404


@pytest.mark.req("AC-001")
def test_sending_requires_faculty_login(client, make, ab):
    _, b = ab
    assert client.post("/collaborations/requests", json={"recipient_id": b.id}).status_code == 401
    assert send(client, make.user(role=UserRole.admin), b.id).status_code == 403


@pytest.mark.req("FR-028", "BR-010", "AC-005")
def test_no_duplicate_pending_request_either_direction(client, ab):
    a, b = ab
    assert send(client, a, b.id).status_code == 201
    assert "already have a pending" in send(client, a, b.id).json()["detail"]
    assert "already sent you" in send(client, b, a.id).json()["detail"]


@pytest.mark.req("BR-010")
def test_new_request_allowed_after_decline(client, ab):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    client.post(f"/collaborations/requests/{rid}/decline", headers=auth(b))
    assert send(client, a, b.id).status_code == 201


# ---------- Responding (UC-015..017) ----------

@pytest.mark.req("FR-030", "FR-033", "BR-014")
def test_accept_creates_one_mutual_collaboration(client, ab, db):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    r = client.post(f"/collaborations/requests/{rid}/accept", headers=auth(b))
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["responded_at"]
    col = db.scalar(select(Collaboration).where(Collaboration.request_id == rid))
    assert col and col.faculty_a < col.faculty_b
    assert client.get("/collaborations", headers=auth(a)).json()[0]["other"]["full_name"] == "Bob"
    assert client.get("/collaborations", headers=auth(b)).json()[0]["other"]["full_name"] == "Alice"
    assert "already collaborating" in send(client, b, a.id).json()["detail"]


@pytest.mark.req("FR-030")
def test_decline_and_withdraw(client, make, ab):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    assert client.post(f"/collaborations/requests/{rid}/decline", headers=auth(b)).json()["status"] == "declined"
    c = make.faculty("Carol", expertise=["X"])
    rid2 = send(client, a, c.id).json()["id"]
    assert client.post(f"/collaborations/requests/{rid2}/withdraw", headers=auth(a)).json()["status"] == "withdrawn"


@pytest.mark.req("BR-011", "BR-012")
@pytest.mark.parametrize("action", ["accept", "decline", "withdraw"])
def test_no_transition_out_of_final_state(client, ab, action):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    client.post(f"/collaborations/requests/{rid}/accept", headers=auth(b))
    actor = a if action == "withdraw" else b
    r = client.post(f"/collaborations/requests/{rid}/{action}", headers=auth(actor))
    assert r.status_code == 409 and "already been accepted" in r.json()["detail"]


def test_only_the_right_party_can_act(client, make, ab):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    outsider = make.faculty("Outsider")
    assert client.post(f"/collaborations/requests/{rid}/accept", headers=auth(a)).status_code == 403
    assert client.post(f"/collaborations/requests/{rid}/withdraw", headers=auth(b)).status_code == 403
    assert client.post(f"/collaborations/requests/{rid}/accept", headers=auth(outsider)).status_code == 404


def test_cannot_accept_from_now_deactivated_sender(client, ab, db):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    a.status = UserStatus.inactive
    db.commit()
    assert client.post(f"/collaborations/requests/{rid}/accept", headers=auth(b)).status_code == 409


@pytest.mark.req("BR-012")
def test_concurrent_accepts_only_one_wins(client, ab):
    """Row locking: two simultaneous accepts can't both succeed."""
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    codes = []

    def accept():
        from fastapi.testclient import TestClient
        from app.main import app
        codes.append(TestClient(app).post(f"/collaborations/requests/{rid}/accept", headers=auth(b)).status_code)

    threads = [threading.Thread(target=accept) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [200, 409, 409, 409]


# ---------- Lists ----------

@pytest.mark.req("FR-031", "FR-032")
def test_sent_and_received_lists_with_status(client, ab):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    assert [r["id"] for r in client.get("/collaborations/requests/sent", headers=auth(a)).json()] == [rid]
    received = client.get("/collaborations/requests/received", headers=auth(b)).json()
    assert received[0]["id"] == rid and received[0]["status"] == "pending"
    assert client.get("/collaborations/requests/received", headers=auth(b), params={"status": "accepted"}).json() == []


def test_relationship_states(client, ab):
    a, b = ab
    status = lambda viewer, other: client.get(f"/collaborations/status/{other.id}", headers=auth(viewer)).json()["state"]
    assert status(a, b) == "none"
    rid = send(client, a, b.id).json()["id"]
    assert (status(a, b), status(b, a)) == ("pending_sent", "pending_received")
    client.post(f"/collaborations/requests/{rid}/accept", headers=auth(b))
    assert status(a, b) == "collaborators"


# ---------- Notifications ----------

@pytest.mark.req("FR-034", "AC-009", "BR-019")
def test_recipient_notified_and_emailed_on_new_request(client, ab, outbox):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    n = client.get("/notifications", headers=auth(b)).json()
    assert n["unread_count"] == 1
    assert n["results"][0]["type"] == "request_received" and n["results"][0]["request_id"] == rid
    assert outbox.to(b.email)
    assert client.get("/notifications", headers=auth(a)).json()["total"] == 0


@pytest.mark.req("FR-035")
@pytest.mark.parametrize("action,kind", [("accept", "request_accepted"), ("decline", "request_declined")])
def test_sender_notified_of_response(client, ab, outbox, action, kind):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    client.post(f"/collaborations/requests/{rid}/{action}", headers=auth(b))
    assert client.get("/notifications", headers=auth(a)).json()["results"][0]["type"] == kind
    assert outbox.to(a.email)


@pytest.mark.req("BR-018")
def test_withdrawal_creates_no_notification(client, ab, db):
    a, b = ab
    rid = send(client, a, b.id).json()["id"]
    before = client.get("/notifications", headers=auth(b)).json()["total"]
    client.post(f"/collaborations/requests/{rid}/withdraw", headers=auth(a))
    assert client.get("/notifications", headers=auth(b)).json()["total"] == before


@pytest.mark.req("FR-036", "FR-037", "BR-019")
def test_notification_history_and_read_state(client, make, ab):
    a, b = ab
    c = make.faculty("Carol")
    send(client, a, b.id)
    send(client, c, b.id)
    page = client.get("/notifications", headers=auth(b)).json()
    times = [x["created_at"] for x in page["results"]]
    assert times == sorted(times, reverse=True) and page["unread_count"] == 2
    first = page["results"][0]["id"]
    assert client.post(f"/notifications/{first}/read", headers=auth(a)).status_code == 404  # not yours
    assert client.post(f"/notifications/{first}/read", headers=auth(b)).json()["is_read"] is True
    assert client.get("/notifications/unread-count", headers=auth(b)).json()["unread_count"] == 1
    assert client.get("/notifications", headers=auth(b), params={"unread_only": True}).json()["total"] == 1
    assert client.post("/notifications/read-all", headers=auth(b)).json()["updated"] == 1
    assert client.get("/notifications/unread-count", headers=auth(b)).json()["unread_count"] == 0


def test_deactivation_cancels_pending_requests_and_notifies(client, make, outbox, db):
    admin = make.user(role=UserRole.admin)
    dept = make.department()
    a, b, c = (make.faculty(n, department=dept) for n in ("Alice", "Bob", "Carol"))
    inactive = make.faculty("Ina", department=dept, status=UserStatus.inactive)
    make.request(a, b)
    make.request(c, a)
    make.request(a, inactive)
    make.collaborate(a, make.faculty("Dan", department=dept))  # accepted collaborations are untouched

    assert client.post(f"/admin/users/{a.id}/deactivate", headers=auth(admin)).status_code == 200

    from app.models import CollaborationRequest
    statuses = db.scalars(select(CollaborationRequest.status).where(
        (CollaborationRequest.sender_id == a.id) | (CollaborationRequest.recipient_id == a.id))).all()
    assert sorted(s.value for s in statuses) == ["accepted", "withdrawn", "withdrawn", "withdrawn"]

    def notes(user):
        return db.scalars(select(Notification).where(Notification.recipient_id == user.id)).all()
    nb, nc = notes(b), notes(c)
    assert len(nb) == 1 and nb[0].type == NotificationType.request_cancelled and "to you was cancelled" in nb[0].message
    assert len(nc) == 1 and "Your collaboration request to Alice was cancelled" in nc[0].message
    assert notes(inactive) == []
    assert {to for to, _, _ in outbox} == {b.email, c.email}
