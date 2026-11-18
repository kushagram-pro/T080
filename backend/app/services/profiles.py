from datetime import datetime
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import FacultyProfile, Project, ProjectMember, ProjectStatus, User, UserStatus
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
            selectinload(FacultyProfile.projects).selectinload(Project.members).selectinload(ProjectMember.user),
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


def _person(u: User) -> dict:
    return dict(user_id=u.id, full_name=u.full_name)


def project_dict(x: Project) -> dict:
    return dict(
        id=x.id, title=x.title, description=x.description, status=x.status,
        start_date=x.start_date, end_date=x.end_date,
        # Deactivated members drop out of view (BR-004)
        members=[_person(m.user) for m in sorted(x.members, key=lambda m: m.added_at)
                 if m.user.status == UserStatus.active],
    )


def _project_order(x: Project):
    # Ongoing projects first, then most recently started
    return (x.status != ProjectStatus.ongoing, -x.start_date.toordinal(), -x.id)


def joint_projects(db: Session, user_id: int) -> list[dict]:
    """Projects other (active) faculty own and list this user on."""
    projects = db.scalars(
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(FacultyProfile, FacultyProfile.id == Project.profile_id)
        .join(User, User.id == FacultyProfile.user_id)
        .where(ProjectMember.user_id == user_id, User.status == UserStatus.active)
        .options(
            selectinload(Project.members).selectinload(ProjectMember.user),
            selectinload(Project.profile).selectinload(FacultyProfile.user),
        )
    ).all()
    return [
        dict(**project_dict(x), owner=_person(x.profile.user))
        for x in sorted(projects, key=_project_order)
    ]


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
        projects=[project_dict(x) for x in sorted(p.projects, key=_project_order)],
        updated_at=p.updated_at,
    )


def to_profile_out(db: Session, p: FacultyProfile) -> ProfileOut:
    return ProfileOut(**_base(p), joint_projects=joint_projects(db, p.user_id))


def to_own_profile_out(db: Session, p: FacultyProfile) -> OwnProfileOut:
    missing = missing_for_discovery(p)
    return OwnProfileOut(
        **_base(p), joint_projects=joint_projects(db, p.user_id),
        is_discoverable=not missing, missing_for_discovery=missing, is_hidden=p.is_hidden,
    )


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
