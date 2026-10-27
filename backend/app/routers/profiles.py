from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user, require_faculty
from app.models import (
    Department,
    ExpertiseKeyword,
    FacultyProfile,
    Project,
    Publication,
    ResearchInterest,
    User,
    UserRole,
    UserStatus,
)
from app.schemas.profile import (
    DESIGNATIONS,
    OwnProfileOut,
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    ProjectIn,
    ProjectOut,
    PublicationIn,
    PublicationOut,
)
from app.services.profiles import load_profile, sync_keywords, to_own_profile_out, to_profile_out, touch

router = APIRouter(prefix="/profiles", tags=["profiles"])

NO_PROFILE = "You haven't created your profile yet"


def _require_department(db: Session, department_id: int) -> None:
    # AC-014 / UC-004 alt flow ii
    if db.get(Department, department_id) is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": ["body", "department_id"], "msg": "Please choose a department from the list", "type": "value_error"}],
        )


def _own_profile(db: Session, user: User) -> FacultyProfile:
    profile = load_profile(db, user_id=user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NO_PROFILE)
    return profile


def _own_row(db: Session, model, row_id: int, profile: FacultyProfile, what: str):
    # BR-006: filtering by profile_id means another faculty's rows simply aren't found
    row = db.scalar(select(model).where(model.id == row_id, model.profile_id == profile.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")
    return row


@router.get("/designations", response_model=list[str])
def list_designations(_user: User = Depends(get_current_user)):
    """Allowed designation values, for the profile form and the search filter."""
    return DESIGNATIONS


# ---------- Own profile (BR-006: faculty only ever touch their own) ----------

@router.get("/me", response_model=OwnProfileOut)
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    """FR-016."""
    return to_own_profile_out(_own_profile(db, user))


@router.post("/me", response_model=OwnProfileOut, status_code=status.HTTP_201_CREATED)
def create_my_profile(body: ProfileCreate, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    """FR-008 / UC-004."""
    if db.scalar(select(FacultyProfile.id).where(FacultyProfile.user_id == user.id)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a profile")  # AC-012
    _require_department(db, body.department_id)

    full_name = body.full_name or user.full_name
    profile = FacultyProfile(
        user_id=user.id,
        full_name=full_name,
        department_id=body.department_id,
        designation=body.designation,
        bio=body.bio,
        expertise_keywords=[ExpertiseKeyword(keyword=k) for k in body.expertise_keywords],
        research_interests=[ResearchInterest(topic=t) for t in body.research_interests],
    )
    user.full_name = full_name  # keep the account name in step with the profile
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:  # double-submit race on user_id
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have a profile")
    return to_own_profile_out(load_profile(db, user_id=user.id))


@router.patch("/me", response_model=OwnProfileOut)
def update_my_profile(body: ProfileUpdate, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    """FR-009 / FR-010 / FR-011."""
    profile = _own_profile(db, user)
    sent = body.model_fields_set

    if "department_id" in sent:
        _require_department(db, body.department_id)
        profile.department_id = body.department_id
    if "full_name" in sent:
        profile.full_name = body.full_name
        user.full_name = body.full_name
    if "designation" in sent:
        profile.designation = body.designation
    if "bio" in sent:
        profile.bio = body.bio
    if "expertise_keywords" in sent:
        sync_keywords(profile.expertise_keywords, body.expertise_keywords, "keyword",
                      lambda k: ExpertiseKeyword(keyword=k))
    if "research_interests" in sent:
        sync_keywords(profile.research_interests, body.research_interests, "topic",
                      lambda t: ResearchInterest(topic=t))

    touch(profile)
    db.commit()
    db.expire_all()
    return to_own_profile_out(load_profile(db, user_id=user.id))


# ---------- Publications (FR-012 / FR-013) ----------

@router.post("/me/publications", response_model=PublicationOut, status_code=status.HTTP_201_CREATED)
def add_publication(body: PublicationIn, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    pub = Publication(profile_id=profile.id, **body.model_dump())
    db.add(pub)
    touch(profile)
    db.commit()
    return PublicationOut(id=pub.id, **body.model_dump())


@router.put("/me/publications/{pub_id}", response_model=PublicationOut)
def edit_publication(pub_id: int, body: PublicationIn, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    pub = _own_row(db, Publication, pub_id, profile, "Publication")
    for k, v in body.model_dump().items():
        setattr(pub, k, v)
    touch(profile)
    db.commit()
    return PublicationOut(id=pub.id, **body.model_dump())


@router.delete("/me/publications/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publication(pub_id: int, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    db.delete(_own_row(db, Publication, pub_id, profile, "Publication"))
    touch(profile)
    db.commit()


# ---------- Projects (FR-014 / FR-015) ----------

@router.post("/me/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def add_project(body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    proj = Project(profile_id=profile.id, **body.model_dump())
    db.add(proj)
    touch(profile)
    db.commit()
    return ProjectOut(id=proj.id, **body.model_dump())


@router.put("/me/projects/{project_id}", response_model=ProjectOut)
def edit_project(project_id: int, body: ProjectIn, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    proj = _own_row(db, Project, project_id, profile, "Project")
    for k, v in body.model_dump().items():
        setattr(proj, k, v)
    touch(profile)
    db.commit()
    return ProjectOut(id=proj.id, **body.model_dump())


@router.delete("/me/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(require_faculty)):
    profile = _own_profile(db, user)
    db.delete(_own_row(db, Project, project_id, profile, "Project"))
    touch(profile)
    db.commit()


# ---------- Other people's profiles ----------

@router.get("/{user_id}", response_model=ProfileOut)
def get_profile(user_id: int, db: Session = Depends(get_db), viewer: User = Depends(get_current_user)):
    """FR-017 (any logged-in user, active faculty only) and FR-041 (admins see any profile)."""
    profile = load_profile(db, user_id=user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    # BR-004: deactivated faculty are hidden; same 404 so we don't reveal they exist
    if profile.user.status != UserStatus.active and viewer.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return to_profile_out(profile)
