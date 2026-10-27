"""Faculty profiles: FR-008..FR-017, FR-041, BR-005..BR-008, AC-011..AC-018."""
from datetime import date

import pytest

from app.models import UserRole, UserStatus
from tests.conftest import auth


@pytest.fixture
def dept(make):
    return make.department("Computer Science")


def profile_body(dept, **overrides):
    body = {"department_id": dept.id, "designation": "Assistant Professor",
            "expertise_keywords": ["Machine Learning"], "research_interests": ["Medical Imaging"]}
    return {**body, **overrides}


@pytest.fixture
def me(client, make, dept):
    """A faculty member with a profile, plus their auth headers."""
    user = make.user(name="Alice Rao")
    h = auth(user)
    assert client.post("/profiles/me", headers=h, json=profile_body(dept)).status_code == 201
    return user, h


# ---------- Create (UC-004) ----------

@pytest.mark.req("FR-008", "AC-015", "AC-016")
def test_create_profile(client, make, dept):
    user = make.user(name="Alice Rao")
    r = client.post("/profiles/me", headers=auth(user), json=profile_body(dept, bio="  Hello  "))
    p = r.json()
    assert r.status_code == 201
    assert p["full_name"] == "Alice Rao" and p["department"]["name"] == "Computer Science"
    assert p["designation"] == "Assistant Professor" and p["bio"] == "Hello"


@pytest.mark.req("AC-013", "AC-018", "BR-005")
@pytest.mark.parametrize("override", [
    {"expertise_keywords": []},
    {"expertise_keywords": ["  ", ""]},
    {"designation": "Wizard"},
    {"designation": None},
])
def test_create_requires_mandatory_fields(client, make, dept, override):
    assert client.post("/profiles/me", headers=auth(make.user()), json=profile_body(dept, **override)).status_code == 422


@pytest.mark.req("AC-014")
def test_create_rejects_unknown_department(client, make, dept):
    r = client.post("/profiles/me", headers=auth(make.user()), json=profile_body(dept, department_id=999999))
    assert r.status_code == 422 and r.json()["detail"][0]["loc"][-1] == "department_id"


@pytest.mark.req("AC-012")
def test_only_one_profile_per_user(client, me, dept):
    _, h = me
    assert client.post("/profiles/me", headers=h, json=profile_body(dept)).status_code == 409


@pytest.mark.req("AC-011", "FR-006")
def test_profile_endpoints_need_a_faculty_login(client, make, dept):
    assert client.get("/profiles/me").status_code == 401
    admin = make.user(role=UserRole.admin)
    assert client.post("/profiles/me", headers=auth(admin), json=profile_body(dept)).status_code == 403


@pytest.mark.req("FR-016")
def test_view_own_profile_and_missing_profile(client, make, me):
    _, h = me
    p = client.get("/profiles/me", headers=h).json()
    assert p["expertise_keywords"] == ["Machine Learning"] and p["is_discoverable"] is True
    assert client.get("/profiles/me", headers=auth(make.user())).status_code == 404


# ---------- Update ----------

@pytest.mark.req("FR-009")
def test_partial_update_and_name_sync(client, make, me):
    user, h = me
    other = make.department("Physics")
    r = client.patch("/profiles/me", headers=h, json={"full_name": "Dr. Alice Rao", "department_id": other.id, "bio": None})
    assert r.status_code == 200 and r.json()["department"]["id"] == other.id and r.json()["bio"] is None
    assert client.get("/auth/me", headers=h).json()["full_name"] == "Dr. Alice Rao"


@pytest.mark.req("FR-010", "FR-011")
def test_keywords_cleaned_deduplicated_and_replaced(client, me):
    _, h = me
    r = client.patch("/profiles/me", headers=h, json={
        "expertise_keywords": ["machine   learning", "Machine Learning", "NLP"],
        "research_interests": ["Robotics", "robotics", "Vision"]})
    assert r.json()["expertise_keywords"] == ["machine learning", "NLP"]
    assert r.json()["research_interests"] == ["Robotics", "Vision"]


@pytest.mark.req("BR-005")
def test_cannot_remove_last_expertise_keyword(client, me):
    _, h = me
    assert client.patch("/profiles/me", headers=h, json={"expertise_keywords": []}).status_code == 422
    assert client.patch("/profiles/me", headers=h, json={"designation": None}).status_code == 422


# ---------- Publications ----------

@pytest.mark.req("FR-012", "FR-013")
def test_add_edit_delete_publication(client, me):
    _, h = me
    r = client.post("/profiles/me/publications", headers=h,
                    json={"title": "Paper", "venue": "NeurIPS", "year": 2021, "doi_url": "10.1145/3290605"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.put(f"/profiles/me/publications/{pid}", headers=h, json={"title": "Paper v2", "venue": "ICML", "year": 2022})
    assert r.json()["title"] == "Paper v2" and r.json()["doi_url"] is None
    assert client.delete(f"/profiles/me/publications/{pid}", headers=h).status_code == 204
    assert client.get("/profiles/me", headers=h).json()["publications"] == []


@pytest.mark.req("BR-007")
def test_publication_year_cannot_be_in_future(client, me):
    _, h = me
    r = client.post("/profiles/me/publications", headers=h, json={"title": "T", "venue": "V", "year": date.today().year + 1})
    assert r.status_code == 422


def test_publication_link_must_be_doi_or_http(client, me):
    _, h = me
    r = client.post("/profiles/me/publications", headers=h,
                    json={"title": "T", "venue": "V", "year": 2020, "doi_url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_publications_newest_first(client, me):
    _, h = me
    for year in (2019, 2024, 2021):
        client.post("/profiles/me/publications", headers=h, json={"title": f"P{year}", "venue": "V", "year": year})
    assert [p["year"] for p in client.get("/profiles/me", headers=h).json()["publications"]] == [2024, 2021, 2019]


# ---------- Projects ----------

@pytest.mark.req("FR-014", "FR-015")
def test_add_edit_delete_project(client, me):
    _, h = me
    r = client.post("/profiles/me/projects", headers=h, json={"title": "Grant", "status": "ongoing", "start_date": "2024-07-01"})
    assert r.status_code == 201
    pid = r.json()["id"]
    r = client.put(f"/profiles/me/projects/{pid}", headers=h,
                   json={"title": "Grant", "status": "past", "start_date": "2024-07-01", "end_date": "2025-03-01"})
    assert r.json()["status"] == "past"
    assert client.delete(f"/profiles/me/projects/{pid}", headers=h).status_code == 204


@pytest.mark.req("BR-008")
@pytest.mark.parametrize("end_date", [None, "2020-01-01", "2019-06-01"])
def test_past_project_needs_end_date_after_start(client, me, end_date):
    _, h = me
    r = client.post("/profiles/me/projects", headers=h,
                    json={"title": "P", "status": "past", "start_date": "2020-01-01", "end_date": end_date})
    assert r.status_code == 422


@pytest.mark.req("BR-008")
def test_database_also_enforces_past_project_rule(db, me):
    from sqlalchemy.exc import IntegrityError
    from app.models import FacultyProfile, Project, ProjectStatus
    user, _ = me
    profile = db.query(FacultyProfile).filter_by(user_id=user.id).one()
    db.add(Project(profile_id=profile.id, title="x", status=ProjectStatus.past, start_date=date(2020, 1, 1)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ---------- Ownership (BR-006) ----------

@pytest.mark.req("BR-006")
def test_cannot_edit_someone_elses_items(client, make, me, dept):
    _, h = me
    pid = client.post("/profiles/me/publications", headers=h, json={"title": "Mine", "venue": "V", "year": 2020}).json()["id"]
    other = make.user()
    oh = auth(other)
    client.post("/profiles/me", headers=oh, json=profile_body(dept))
    assert client.put(f"/profiles/me/publications/{pid}", headers=oh, json={"title": "Hijack", "venue": "V", "year": 2020}).status_code == 404
    assert client.delete(f"/profiles/me/publications/{pid}", headers=oh).status_code == 404


# ---------- Viewing others ----------

@pytest.mark.req("FR-017")
def test_view_another_active_profile(client, make, me):
    user, _ = me
    r = client.get(f"/profiles/{user.id}", headers=auth(make.user()))
    assert r.status_code == 200 and r.json()["full_name"] == "Alice Rao" and "is_discoverable" not in r.json()


@pytest.mark.req("BR-004", "FR-041")
def test_deactivated_profile_hidden_except_from_admin(client, make, me, db):
    user, _ = me
    user.status = UserStatus.inactive
    db.commit()
    assert client.get(f"/profiles/{user.id}", headers=auth(make.user())).status_code == 404
    assert client.get(f"/profiles/{user.id}", headers=auth(make.user(role=UserRole.admin))).status_code == 200


def test_designations_list(client, make):
    assert "Assistant Professor" in client.get("/profiles/designations", headers=auth(make.user())).json()
