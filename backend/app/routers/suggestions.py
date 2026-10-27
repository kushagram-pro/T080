from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import require_faculty
from app.models import FacultyProfile, User
from app.schemas.discovery import Suggestion
from app.services.discovery import all_keywords_subquery, collaborator_ids, visible_profiles
from app.services.profiles import load_profile

router = APIRouter(prefix="/suggestions", tags=["suggestions"])

# Weighted overlap (locked-in decision): a keyword that is expertise for both people is the
# strongest signal; any other overlap (interest-interest, expertise-interest) counts once.
WEIGHT_SHARED_EXPERTISE = 2
WEIGHT_OTHER_OVERLAP = 1


@router.get("", response_model=list[Suggestion])
def suggestions(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(require_faculty),
):
    """FR-023 to FR-025 / UC-029. Exact (case-insensitive) keyword overlap, ranked by weighted score."""
    me = load_profile(db, user_id=user.id)
    if me is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create your profile to get suggestions")

    my_expertise = {k.keyword.lower() for k in me.expertise_keywords}
    my_all = my_expertise | {r.topic.lower() for r in me.research_interests}
    if not my_all:
        return []

    # Active, complete, not me (BR-015/016), and not someone I already collaborate with (BR-017 / FR-025)
    eligible = visible_profiles(user)
    exclude = collaborator_ids(db, user.id)
    if exclude:
        eligible = eligible.where(FacultyProfile.user_id.not_in(exclude))
    eligible_ids = eligible.with_only_columns(FacultyProfile.id).subquery()

    kw = all_keywords_subquery()
    rows = db.execute(
        select(kw.c.profile_id, kw.c.text, kw.c.source).where(
            func.lower(kw.c.text).in_(my_all),
            kw.c.profile_id.in_(select(eligible_ids.c.id)),
        )
    ).all()

    # profile_id -> {lowercased keyword: (display text, weight)}; a keyword listed as both their
    # expertise and their interest is counted once, at its higher weight
    shared: dict[int, dict[str, tuple[str, int]]] = {}
    for profile_id, text, source in rows:
        key = text.lower()
        weight = (
            WEIGHT_SHARED_EXPERTISE if source == "expertise" and key in my_expertise else WEIGHT_OTHER_OVERLAP
        )
        entry = shared.setdefault(profile_id, {})
        if key not in entry or entry[key][1] < weight:
            entry[key] = (text, weight)

    if not shared:
        return []

    profiles = {
        p.id: p
        for p in db.scalars(
            select(FacultyProfile)
            .where(FacultyProfile.id.in_(shared))
            .options(selectinload(FacultyProfile.department))
        )
    }

    ranked = sorted(
        shared.items(),
        key=lambda item: (
            -sum(w for _, w in item[1].values()),  # weighted score
            -len(item[1]),                          # then number of shared keywords
            profiles[item[0]].full_name.lower(),
        ),
    )[:limit]

    out = []
    for profile_id, words in ranked:
        p = profiles[profile_id]
        # Strongest overlaps first in the displayed list
        ordered = sorted(words.values(), key=lambda tw: (-tw[1], tw[0].lower()))
        out.append(
            Suggestion(
                user_id=p.user_id,
                full_name=p.full_name,
                department=(
                    dict(id=p.department.id, name=p.department.name, institute=p.department.institute)
                    if p.department else None
                ),
                designation=p.designation,
                shared_keywords=[t for t, _ in ordered],
                score=sum(w for _, w in ordered),
            )
        )
    return out
