"""Read-only oversight reports (SRS 13.8).

Aggregation is done in Python over one institute's data: a few hundred faculty at most,
so this stays fast and much easier to follow than one large SQL query.
"""
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies.auth import require_roles
from app.models import (
    Collaboration,
    CollaborationRequest,
    Department,
    FacultyProfile,
    RequestStatus,
    User,
    UserRole,
    UserStatus,
)

router = APIRouter(prefix="/reports", tags=["reports"])

TOP_N = 15


# ---------- Response shapes ----------

class KeywordCount(BaseModel):
    keyword: str
    count: int


class DepartmentRow(BaseModel):
    department_id: int
    department: str
    faculty: int
    discoverable_profiles: int
    collaborations: int          # involving at least one member of this department
    cross_department: int        # ...where the partner is in a different department
    pending_requests: int


class MonthCount(BaseModel):
    month: str  # "2026-10"
    count: int


class ActivityReport(BaseModel):
    """FR-043: collaboration activity across all departments."""
    generated_at: datetime
    active_faculty: int
    discoverable_profiles: int
    collaborations: int
    cross_department_collaborations: int
    requests: dict[str, int]          # by status
    acceptance_rate: float | None     # accepted / (accepted + declined)
    by_department: list[DepartmentRow]
    top_expertise: list[KeywordCount]
    top_interests: list[KeywordCount]
    collaborations_by_month: list[MonthCount]


class FacultyRow(BaseModel):
    user_id: int
    full_name: str
    designation: str | None
    expertise: list[str]
    publications: int
    projects: int
    collaborations: int
    discoverable: bool


class PartnerRow(BaseModel):
    member: str
    partner: str
    partner_department: str | None
    since: datetime


class DepartmentReport(BaseModel):
    """FR-044: one department's expertise and collaboration activity."""
    generated_at: datetime
    department_id: int
    department: str
    institute: str
    faculty: list[FacultyRow]
    top_expertise: list[KeywordCount]
    top_interests: list[KeywordCount]
    collaborations: list[PartnerRow]
    requests: dict[str, int]


# ---------- Shared loading ----------

def _active_faculty_profiles(db: Session) -> list[FacultyProfile]:
    return db.scalars(
        select(FacultyProfile)
        .join(User, User.id == FacultyProfile.user_id)
        .where(User.role == UserRole.faculty, User.status == UserStatus.active)
        .options(
            selectinload(FacultyProfile.expertise_keywords),
            selectinload(FacultyProfile.research_interests),
            selectinload(FacultyProfile.publications),
            selectinload(FacultyProfile.projects),
            selectinload(FacultyProfile.department),
        )
    ).all()


def _top(words, n=TOP_N) -> list[KeywordCount]:
    """Count case-insensitively, display the most common spelling."""
    counts, spelling = Counter(), {}
    for w in words:
        key = w.lower()
        counts[key] += 1
        spelling.setdefault(key, Counter())[w] += 1
    return [KeywordCount(keyword=spelling[k].most_common(1)[0][0], count=c) for k, c in counts.most_common(n)]


def _request_counts(reqs) -> dict[str, int]:
    out = {s.value: 0 for s in RequestStatus}
    for r in reqs:
        out[r.status.value] += 1
    return out


# ---------- FR-043 ----------

@router.get("/activity", response_model=ActivityReport)
def activity(
    db: Session = Depends(get_db),
    _viewer: User = Depends(require_roles(UserRole.research_admin, UserRole.admin)),
):
    profiles = _active_faculty_profiles(db)
    dept_of = {p.user_id: p.department_id for p in profiles}  # active faculty only
    collabs = [
        c for c in db.scalars(select(Collaboration)).all()
        if c.faculty_a in dept_of and c.faculty_b in dept_of  # both still active
    ]
    reqs = db.scalars(select(CollaborationRequest)).all()
    counts = _request_counts(reqs)
    decided = counts["accepted"] + counts["declined"]

    rows = []
    for d in db.scalars(select(Department).order_by(Department.name)).all():
        members = {uid for uid, did in dept_of.items() if did == d.id}
        involving = [c for c in collabs if c.faculty_a in members or c.faculty_b in members]
        rows.append(DepartmentRow(
            department_id=d.id,
            department=d.name,
            faculty=len(members),
            discoverable_profiles=sum(1 for p in profiles if p.department_id == d.id and p.is_discoverable()),
            collaborations=len(involving),
            cross_department=sum(1 for c in involving if dept_of[c.faculty_a] != dept_of[c.faculty_b]),
            pending_requests=sum(
                1 for r in reqs
                if r.status == RequestStatus.pending and (r.sender_id in members or r.recipient_id in members)
            ),
        ))

    # Last 12 months, oldest first, including empty months
    now = datetime.utcnow()
    months = []
    y, m = now.year, now.month
    for _ in range(12):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    by_month = Counter(c.created_at.strftime("%Y-%m") for c in collabs)

    return ActivityReport(
        generated_at=now,
        active_faculty=len(profiles),
        discoverable_profiles=sum(1 for p in profiles if p.is_discoverable()),
        collaborations=len(collabs),
        cross_department_collaborations=sum(1 for c in collabs if dept_of[c.faculty_a] != dept_of[c.faculty_b]),
        requests=counts,
        acceptance_rate=round(counts["accepted"] / decided, 3) if decided else None,
        by_department=rows,
        top_expertise=_top(k.keyword for p in profiles for k in p.expertise_keywords),
        top_interests=_top(r.topic for p in profiles for r in p.research_interests),
        collaborations_by_month=[MonthCount(month=mo, count=by_month.get(mo, 0)) for mo in reversed(months)],
    )


# ---------- FR-044 ----------

@router.get("/department", response_model=DepartmentReport)
def department_summary(
    department_id: int | None = Query(None, description="Required for Admin / Research Admin; ignored for Dept. Management"),
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.dept_mgmt, UserRole.research_admin, UserRole.admin)),
):
    if viewer.role == UserRole.dept_mgmt:
        # SRS 11.4: Department Management is limited to their own department
        if viewer.department_id is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Your account isn't linked to a department yet. Ask an administrator.")
        department_id = viewer.department_id
    elif department_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Choose a department")

    dept = db.get(Department, department_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    profiles = _active_faculty_profiles(db)
    by_user = {p.user_id: p for p in profiles}
    members = {p.user_id: p for p in profiles if p.department_id == dept.id}

    collabs = [
        c for c in db.scalars(select(Collaboration).order_by(Collaboration.created_at.desc())).all()
        if c.faculty_a in by_user and c.faculty_b in by_user
        and (c.faculty_a in members or c.faculty_b in members)
    ]
    per_member = Counter()
    partner_rows = []
    for c in collabs:
        for me, other in ((c.faculty_a, c.faculty_b), (c.faculty_b, c.faculty_a)):
            if me in members:
                per_member[me] += 1
                # A collaboration between two members of this department is listed once
                if other in members and me > other:
                    continue
                partner = by_user[other]
                partner_rows.append(PartnerRow(
                    member=members[me].full_name,
                    partner=partner.full_name,
                    partner_department=partner.department.name if partner.department else None,
                    since=c.created_at,
                ))

    reqs = db.scalars(
        select(CollaborationRequest).where(
            (CollaborationRequest.sender_id.in_(members)) | (CollaborationRequest.recipient_id.in_(members))
        )
    ).all() if members else []

    faculty_rows = sorted(
        (
            FacultyRow(
                user_id=p.user_id,
                full_name=p.full_name,
                designation=p.designation,
                expertise=[k.keyword for k in sorted(p.expertise_keywords, key=lambda k: k.id)],
                publications=len(p.publications),
                projects=len(p.projects),
                collaborations=per_member[p.user_id],
                discoverable=p.is_discoverable(),
            )
            for p in members.values()
        ),
        key=lambda r: r.full_name.lower(),
    )

    return DepartmentReport(
        generated_at=datetime.utcnow(),
        department_id=dept.id,
        department=dept.name,
        institute=dept.institute,
        faculty=faculty_rows,
        top_expertise=_top(k.keyword for p in members.values() for k in p.expertise_keywords),
        top_interests=_top(r.topic for p in members.values() for r in p.research_interests),
        collaborations=partner_rows,
        requests=_request_counts(reqs),
    )
