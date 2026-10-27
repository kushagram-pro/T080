import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import FacultyProfile, User
from app.schemas.discovery import SearchPage, SearchResult
from app.schemas.profile import DESIGNATIONS
from app.services.discovery import all_keywords_subquery, like_pattern, visible_profiles

router = APIRouter(prefix="/search", tags=["search"])

MAX_TERMS = 10
MIN_TERM_LEN = 2  # a single letter would match almost every keyword


def parse_terms(q: str) -> list[str]:
    """Comma/semicolon separated keywords -> cleaned, de-duplicated list."""
    seen, terms = set(), []
    for raw in re.split(r"[,;]", q):
        t = " ".join(raw.split())[:100]
        if len(t) >= MIN_TERM_LEN and t.lower() not in seen:
            seen.add(t.lower())
            terms.append(t)
    return terms[:MAX_TERMS]


def _bad_request(msg: str):
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[{"loc": ["query", "q"], "msg": msg, "type": "value_error"}],
    )


@router.get("", response_model=SearchPage)
def search(
    q: str = Query("", max_length=500, description="Keywords, comma separated"),
    department_id: int | None = None,
    designation: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    """FR-018 to FR-022 / UC-010 / UC-011.

    Keywords match expertise and research interests (case-insensitive, partial: "learning"
    finds "Machine Learning"). Results are ranked by how many of the keywords matched.
    With no keywords, a department and/or designation filter browses those faculty by name.
    """
    terms = parse_terms(q)
    if designation is not None and designation not in DESIGNATIONS:
        _bad_request(f"Unknown designation. Choose one of: {', '.join(DESIGNATIONS)}")
    if not terms and department_id is None and not designation:
        # AC-020
        _bad_request("Enter at least one keyword (2+ characters), or choose a department or designation")

    query = visible_profiles(viewer)
    if department_id is not None:
        query = query.where(FacultyProfile.department_id == department_id)  # FR-019 / AC-026
    if designation:
        query = query.where(FacultyProfile.designation == designation)

    if terms:
        kw = all_keywords_subquery()
        matches = [kw.c.text.ilike(like_pattern(t), escape="\\") for t in terms]
        # How many distinct search terms this profile matched, and how many of its keywords matched
        terms_matched = sum(func.max(case((m, 1), else_=0)) for m in matches)
        keyword_hits = func.count()
        score = (
            select(kw.c.profile_id, terms_matched.label("terms_matched"), keyword_hits.label("keyword_hits"))
            .where(or_(*matches))
            .group_by(kw.c.profile_id)
            .subquery("score")
        )
        query = query.join(score, score.c.profile_id == FacultyProfile.id).order_by(
            desc(score.c.terms_matched), desc(score.c.keyword_hits), FacultyProfile.full_name, FacultyProfile.id
        )
    else:
        query = query.order_by(FacultyProfile.full_name, FacultyProfile.id)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    profiles = db.scalars(
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .options(
            selectinload(FacultyProfile.department),
            selectinload(FacultyProfile.expertise_keywords),
            selectinload(FacultyProfile.research_interests),
        )
    ).all()

    lowered = [t.lower() for t in terms]

    def matched(words: list[str]) -> list[str]:
        return [w for w in words if any(t in w.lower() for t in lowered)]

    results = []
    for p in profiles:
        expertise = [k.keyword for k in sorted(p.expertise_keywords, key=lambda k: k.id)]
        interests = [r.topic for r in sorted(p.research_interests, key=lambda r: r.id)]
        results.append(
            SearchResult(
                user_id=p.user_id,
                full_name=p.full_name,
                department=(
                    dict(id=p.department.id, name=p.department.name, institute=p.department.institute)
                    if p.department else None
                ),
                designation=p.designation,
                matched_keywords=matched(expertise + interests),
                expertise_keywords=expertise,
                research_interests=interests,
            )
        )

    return SearchPage(terms=terms, total=total, page=page, page_size=page_size, results=results)
