"""Shared rules for who can be found: used by /search and /suggestions."""
from sqlalchemy import Select, and_, exists, func, literal, or_, select, union_all

from app.models import (
    Collaboration,
    ExpertiseKeyword,
    FacultyProfile,
    ResearchInterest,
    User,
    UserRole,
    UserStatus,
)

# Roles that see every active profile, complete or not (Research Admin, Dept Mgmt, Admin).
# Faculty only see complete profiles (BR-005).
OVERSIGHT_ROLES = {UserRole.admin, UserRole.research_admin, UserRole.dept_mgmt}


def is_discoverable_sql():
    """SQL version of FacultyProfile.is_discoverable() (BR-005). Keep the two in step."""
    return and_(
        func.coalesce(FacultyProfile.full_name, "") != "",
        FacultyProfile.department_id.is_not(None),
        func.coalesce(FacultyProfile.designation, "") != "",
        exists().where(ExpertiseKeyword.profile_id == FacultyProfile.id),
    )


def visible_profiles(viewer: User) -> Select:
    """Profiles this viewer may find: active faculty (BR-004, BR-015), never themselves (BR-016)."""
    q = (
        select(FacultyProfile)
        .join(User, User.id == FacultyProfile.user_id)
        .where(User.status == UserStatus.active, User.role == UserRole.faculty, User.id != viewer.id)
    )
    if viewer.role not in OVERSIGHT_ROLES:
        q = q.where(is_discoverable_sql())
    return q


def all_keywords_subquery():
    """One row per keyword: (profile_id, text, source) where source is 'expertise' or 'interest'."""
    return union_all(
        select(
            ExpertiseKeyword.profile_id.label("profile_id"),
            ExpertiseKeyword.keyword.label("text"),
            literal("expertise").label("source"),
        ),
        select(
            ResearchInterest.profile_id.label("profile_id"),
            ResearchInterest.topic.label("text"),
            literal("interest").label("source"),
        ),
    ).subquery("kw")


def collaborator_ids(db, user_id: int) -> set[int]:
    """Users with an accepted collaboration with `user_id`, either direction (BR-014 / BR-017)."""
    rows = db.execute(
        select(Collaboration.faculty_a, Collaboration.faculty_b).where(
            or_(Collaboration.faculty_a == user_id, Collaboration.faculty_b == user_id)
        )
    ).all()
    return {b if a == user_id else a for a, b in rows}


def like_pattern(term: str) -> str:
    """%term% with LIKE wildcards in the user's input escaped (so '50%' means a literal %)."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
