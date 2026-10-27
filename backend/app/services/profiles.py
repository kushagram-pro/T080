from datetime import datetime
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import FacultyProfile, ProjectStatus
from app.schemas.profile import OwnProfileOut, ProfileOut

T = TypeVar("T")


def load_profile(db: Session, *, user_id: int) -> FacultyProfile | None:
    """Profile with everything needed for a full response, in a fixed number of queries."""
    return db.scalar(
        select(FacultyProfile)
        .where(FacultyProfile.user_id == user_id)
        .options(
            selectinload(FacultyProfile.user),
            selectinload(FacultyProfile.department),
            selectinload(FacultyProfile.expertise_keywords),
            selectinload(FacultyProfile.research_interests),
            selectinload(FacultyProfile.publications),
            selectinload(FacultyProfile.projects),
        )
    )


def missing_for_discovery(p: FacultyProfile) -> list[str]:
    """Mirrors FacultyProfile.is_discoverable() (BR-005) but says what is missing."""
    missing = []
    if not p.full_name:
        missing.append("full name")
    if p.department_id is None:
        missing.append("department")
    if not p.designation:
        missing.append("designation")
    if not p.expertise_keywords:
        missing.append("at least one expertise keyword")
    return missing


def _base(p: FacultyProfile) -> dict:
    return dict(
        user_id=p.user_id,
        full_name=p.full_name,
        email=p.user.email,
        department=(
            dict(id=p.department.id, name=p.department.name, institute=p.department.institute)
            if p.department else None
        ),
        designation=p.designation,
        bio=p.bio,
        expertise_keywords=[k.keyword for k in sorted(p.expertise_keywords, key=lambda k: k.id)],
        research_interests=[r.topic for r in sorted(p.research_interests, key=lambda r: r.id)],
        # Newest publications first
        publications=[
            dict(id=x.id, title=x.title, venue=x.venue, year=x.year, doi_url=x.doi_url)
            for x in sorted(p.publications, key=lambda x: (-x.year, -x.id))
        ],
        # Ongoing projects first, then most recently started
        projects=[
            dict(id=x.id, title=x.title, description=x.description, status=x.status,
                 start_date=x.start_date, end_date=x.end_date)
            for x in sorted(
                p.projects,
                key=lambda x: (x.status != ProjectStatus.ongoing, -x.start_date.toordinal(), -x.id),
            )
        ],
        updated_at=p.updated_at,
    )


def to_profile_out(p: FacultyProfile) -> ProfileOut:
    return ProfileOut(**_base(p))


def to_own_profile_out(p: FacultyProfile) -> OwnProfileOut:
    missing = missing_for_discovery(p)
    return OwnProfileOut(**_base(p), is_discoverable=not missing, missing_for_discovery=missing)


def sync_keywords(collection: list[T], new_values: list[str], attr: str, factory: Callable[[str], T]) -> None:
    """Make `collection` match `new_values` without deleting and re-inserting unchanged rows.

    Replacing the whole list would insert new rows before deleting old ones and trip the
    case-insensitive unique index, so: keep matches, fix changed casing, delete the rest, add new.
    """
    wanted = {v.lower(): v for v in new_values}
    for item in list(collection):
        key = getattr(item, attr).lower()
        if key in wanted:
            setattr(item, attr, wanted.pop(key))  # same keyword, maybe new spelling
        else:
            collection.remove(item)  # delete-orphan removes the row
    for v in new_values:
        if v.lower() in wanted:
            collection.append(factory(v))


def touch(p: FacultyProfile) -> None:
    """Child rows changed; record it on the profile itself."""
    p.updated_at = datetime.utcnow()
