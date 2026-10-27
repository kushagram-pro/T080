from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_admin
from app.models import AuditAction, Department, FacultyProfile, User
from app.schemas.department import DepartmentCreate, DepartmentOut, DepartmentUpdate
from app.services import audit

router = APIRouter(prefix="/departments", tags=["departments"])

DUPLICATE = "A department with this name already exists in this institute"


def _with_counts():
    count = func.count(FacultyProfile.id).label("faculty_count")
    return (
        select(Department, count)
        .outerjoin(FacultyProfile, FacultyProfile.department_id == Department.id)
        .group_by(Department.id)
    )


def _out(dept: Department, faculty_count: int) -> DepartmentOut:
    return DepartmentOut(id=dept.id, name=dept.name, institute=dept.institute, faculty_count=faculty_count)


def _get_or_404(db: Session, dept_id: int) -> Department:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return dept


def _faculty_count(db: Session, dept_id: int) -> int:
    return db.scalar(select(func.count(FacultyProfile.id)).where(FacultyProfile.department_id == dept_id))


# --- Read: any logged-in user (profile form needs the list; NFR-007 keeps it off for anonymous users) ---

@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    rows = db.execute(_with_counts().order_by(Department.institute, Department.name)).all()
    return [_out(d, n) for d, n in rows]


@router.get("/{dept_id}", response_model=DepartmentOut)
def get_department(dept_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    row = db.execute(_with_counts().where(Department.id == dept_id)).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return _out(*row)


# --- Write: admin only (FR-039 / UC-024) ---

@router.post("", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(body: DepartmentCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    dept = Department(name=body.name, institute=body.institute)
    db.add(dept)
    try:
        db.flush()  # get the id for the audit row; also surfaces a duplicate here
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE)
    audit.record(db, admin, AuditAction.department_created, details=f"#{dept.id} {dept.name} ({dept.institute})")
    db.commit()
    return _out(dept, 0)


@router.patch("/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: int, body: DepartmentUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    dept = _get_or_404(db, dept_id)
    before = f"{dept.name} ({dept.institute})"
    if body.name is not None:
        dept.name = body.name
    if body.institute is not None:
        dept.institute = body.institute
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=DUPLICATE)
    audit.record(
        db, admin, AuditAction.department_updated,
        details=f"#{dept.id} {before} -> {dept.name} ({dept.institute})",
    )
    db.commit()
    return _out(dept, _faculty_count(db, dept.id))


@router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(dept_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    dept = _get_or_404(db, dept_id)
    n = _faculty_count(db, dept.id)
    if n:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{n} faculty profile(s) belong to this department. Move them to another department first.",
        )
    managers = db.scalar(select(func.count(User.id)).where(User.department_id == dept.id))
    if managers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{managers} department manager account(s) are assigned to this department. Reassign them first.",
        )
    audit.record(db, admin, AuditAction.department_deleted, details=f"#{dept.id} {dept.name} ({dept.institute})")
    db.delete(dept)
    db.commit()
