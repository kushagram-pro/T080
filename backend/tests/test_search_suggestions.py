"""Search & suggestions: FR-018..FR-025, FR-042, BR-004, BR-005, BR-015..BR-017, AC-019..AC-026."""
import pytest

from app.models import UserRole, UserStatus
from tests.conftest import auth


@pytest.fixture
def people(make):
    cse, physics = make.department("CSE"), make.department("Physics")
    p = {
        "me": make.faculty("Me", department=cse, expertise=["Machine Learning", "Computer Vision"], interests=["Medical Imaging"]),
        "alpha": make.faculty("Alpha", department=cse, designation="Assistant Professor",
                              expertise=["Deep Learning", "Machine Learning"], interests=["Robotics"]),
        "beta": make.faculty("Beta", department=physics, expertise=["Computer Vision"], interests=["Machine Learning"]),
        "incomplete": make.faculty("Incomplete", department=cse, designation=None, expertise=["Machine Learning"]),
        "gone": make.faculty("Gone", department=cse, expertise=["Machine Learning"], status=UserStatus.inactive),
        "vlsi": make.faculty("Vlsi", department=physics, expertise=["VLSI"]),
        "collab": make.faculty("Collab", department=cse, expertise=["Medical Imaging"]),
        "wild": make.faculty("Wild", department=cse, expertise=["50% Off_Topic"]),
    }
    make.collaborate(p["me"], p["collab"])
    p["depts"] = {"cse": cse, "physics": physics}
    return p


def names(r):
    return [x["full_name"] for x in r.json()["results"]]


def search(client, user, **params):
    return client.get("/search", headers=auth(user), params=params)


# ---------- Search ----------

@pytest.mark.req("FR-018", "FR-020", "BR-004", "BR-005", "BR-015", "BR-016", "AC-021", "AC-022", "AC-023")
def test_keyword_search_partial_match_ranked_and_filtered(client, people):
    r = search(client, people["me"], q="learning")
    assert names(r) == ["Alpha", "Beta"]  # Alpha matches 2 keywords; Me, Incomplete, Gone excluded
    first = r.json()["results"][0]
    assert first["matched_keywords"] == ["Deep Learning", "Machine Learning"]
    assert first["designation"] == "Assistant Professor" and first["department"]["name"] == "CSE"


@pytest.mark.req("FR-018")
def test_multiple_keywords_rank_by_terms_matched(client, people):
    r = search(client, people["me"], q="machine learning, VISION")
    assert names(r)[0] == "Beta" and r.json()["terms"] == ["machine learning", "VISION"]
    assert sorted(r.json()["results"][0]["matched_keywords"]) == ["Computer Vision", "Machine Learning"]


@pytest.mark.req("FR-019", "AC-026")
def test_filters_by_department_and_designation(client, people):
    assert names(search(client, people["me"], q="learning", department_id=people["depts"]["physics"].id)) == ["Beta"]
    assert names(search(client, people["me"], designation="Assistant Professor")) == ["Alpha"]
    assert names(search(client, people["me"], department_id=people["depts"]["physics"].id)) == ["Beta", "Vlsi"]


@pytest.mark.req("AC-020")
@pytest.mark.parametrize("params", [{}, {"q": "a"}, {"q": " , ; "}])
def test_empty_search_prompts_for_keyword(client, people, params):
    assert search(client, people["me"], **params).status_code == 422


@pytest.mark.req("FR-021", "AC-024")
def test_no_results_returns_empty_list(client, people):
    r = search(client, people["me"], q="quantum gravity")
    assert r.status_code == 200 and r.json()["total"] == 0 and r.json()["results"] == []


@pytest.mark.req("FR-022", "AC-025")
def test_each_result_opens_full_profile(client, people):
    h = auth(people["me"])
    for result in client.get("/search", headers=h, params={"q": "learning"}).json()["results"]:
        assert client.get(f"/profiles/{result['user_id']}", headers=h).status_code == 200


def test_like_wildcards_in_input_are_literal(client, people):
    assert names(search(client, people["me"], q="50%")) == ["Wild"]
    assert names(search(client, people["me"], q="50_")) == []


def test_pagination(client, people):
    full = search(client, people["me"], q="learning").json()
    page2 = search(client, people["me"], q="learning", page=2, page_size=1).json()
    assert page2["total"] == full["total"] == 2 and page2["results"][0]["user_id"] == full["results"][1]["user_id"]


def test_unknown_designation_rejected(client, people):
    assert search(client, people["me"], q="x", designation="Wizard").status_code == 422


@pytest.mark.req("FR-042", "BR-015")
def test_research_admin_sees_incomplete_but_not_inactive(client, people, make):
    ra = make.user(role=UserRole.research_admin)
    found = set(names(search(client, ra, q="machine learning")))
    assert {"Incomplete", "Me", "Alpha", "Beta"} <= found and "Gone" not in found


@pytest.mark.req("AC-019")
def test_search_requires_login(client):
    assert client.get("/search", params={"q": "learning"}).status_code == 401


# ---------- Suggestions ----------

@pytest.mark.req("FR-023", "FR-024", "BR-015", "BR-016", "BR-017", "FR-025")
def test_suggestions_ranked_by_weighted_overlap(client, people):
    s = client.get("/suggestions", headers=auth(people["me"])).json()
    assert [x["full_name"] for x in s] == ["Beta", "Alpha"]
    # Beta: shared expertise CV (2) + ML as their interest (1) = 3; strongest overlap listed first
    assert s[0]["score"] == 3 and s[0]["shared_keywords"] == ["Computer Vision", "Machine Learning"]
    assert s[0]["department"]["name"] == "Physics"
    assert s[1]["score"] == 2 and s[1]["shared_keywords"] == ["Machine Learning"]


def test_suggestions_limit_and_empty(client, people):
    assert len(client.get("/suggestions", headers=auth(people["me"]), params={"limit": 1}).json()) == 1
    assert client.get("/suggestions", headers=auth(people["vlsi"])).json() == []


def test_suggestions_need_profile_and_faculty_role(client, make):
    assert client.get("/suggestions", headers=auth(make.user())).status_code == 404
    assert client.get("/suggestions", headers=auth(make.user(role=UserRole.admin))).status_code == 403
