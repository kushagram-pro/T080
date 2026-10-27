import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Text, Integer, ForeignKey, Date, Enum, DateTime, Index, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ProjectStatus(str, enum.Enum):
    ongoing = "ongoing"
    past = "past"

class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int]=mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str]=mapped_column(String(255), nullable=False)
    institute: Mapped[str]=mapped_column(String(255), nullable=False)

    # "Computer Science" and "computer science" in the same institute are the same department
    __table_args__ = (
        Index("uq_department_name_institute", func.lower(name), func.lower(institute), unique=True),
    )

    profiles: Mapped[list["FacultyProfile"]] = relationship("FacultyProfile", back_populates="department")

class FacultyProfile(Base):
    __tablename__ = "faculty_profiles"

    id:            Mapped[int]      = mapped_column(primary_key=True, index=True)
    user_id:       Mapped[int]      = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    full_name:     Mapped[str]      = mapped_column(String(150), nullable=False)
    designation:   Mapped[str | None] = mapped_column(String(150), nullable=True)
    bio:           Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at:    Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user:               Mapped["User"]                = relationship("User", back_populates="profile")
    department:         Mapped["Department"]          = relationship("Department", back_populates="profiles")
    expertise_keywords: Mapped[list["ExpertiseKeyword"]]  = relationship("ExpertiseKeyword", back_populates="profile", cascade="all, delete-orphan")
    research_interests: Mapped[list["ResearchInterest"]]  = relationship("ResearchInterest", back_populates="profile", cascade="all, delete-orphan")
    projects:           Mapped[list["Project"]]       = relationship("Project", back_populates="profile", cascade="all, delete-orphan")
    publications:       Mapped[list["Publication"]]   = relationship("Publication", back_populates="profile", cascade="all, delete-orphan")

    def is_discoverable(self) -> bool:
        return (
            bool(self.full_name) and
            self.department_id is not None and
            bool(self.designation) and
            len(self.expertise_keywords)> 0
        )

class ExpertiseKeyword(Base):
    __tablename__ = "expertise_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("faculty_profiles.id"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        Index("uq_expertise_profile_keyword", "profile_id", func.lower(keyword), unique=True),
    )

    profile: Mapped["FacultyProfile"] = relationship("FacultyProfile", back_populates="expertise_keywords")

class ResearchInterest(Base):
    __tablename__ = "research_interests"

    id:         Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("faculty_profiles.id"), nullable=False, index=True)
    topic:      Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        Index("uq_interest_profile_topic", "profile_id", func.lower(topic), unique=True),
    )

    profile: Mapped["FacultyProfile"] = relationship("FacultyProfile", back_populates="research_interests")

class Project(Base):
    __tablename__ = "projects"

    id:          Mapped[int]            = mapped_column(primary_key=True)
    profile_id:  Mapped[int]            = mapped_column(ForeignKey("faculty_profiles.id"), nullable=False, index=True)
    title:       Mapped[str]            = mapped_column(String(200), nullable=False)
    description: Mapped[str | None]     = mapped_column(Text, nullable=True)
    status:      Mapped[ProjectStatus]  = mapped_column(Enum(ProjectStatus), default=ProjectStatus.ongoing, nullable=False)
    start_date:  Mapped[date]           = mapped_column(Date, nullable=False)  # FR-014
    end_date:    Mapped[date | None]    = mapped_column(Date, nullable=True)

    __table_args__ = (
        # SRS BR-008: a past project needs an end date later than its start date
        CheckConstraint(
            "status <> 'past' OR (end_date IS NOT NULL AND end_date > start_date)",
            name="ck_project_past_has_end_date",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_project_end_after_start"),
    )

    profile: Mapped["FacultyProfile"] = relationship("FacultyProfile", back_populates="projects")

class Publication(Base):
    __tablename__ = "publications"

    id:          Mapped[int]        = mapped_column(primary_key=True)
    profile_id:  Mapped[int]        = mapped_column(ForeignKey("faculty_profiles.id"), nullable=False, index=True)
    title:       Mapped[str]        = mapped_column(String(300), nullable=False)
    venue:       Mapped[str]        = mapped_column(String(200), nullable=False)  # FR-012
    year:        Mapped[int]        = mapped_column(Integer, nullable=False)
    doi_url:     Mapped[str | None] = mapped_column(String(500), nullable=True)

    # BR-007 (no future year) depends on today's date, so it is checked in the schema, not here
    __table_args__ = (CheckConstraint("year >= 1900", name="ck_publication_year_min"),)

    profile: Mapped["FacultyProfile"] = relationship("FacultyProfile", back_populates="publications")