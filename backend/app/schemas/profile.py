import re
from datetime import date, datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import ProjectStatus

# FR-019 filters by designation, so it is a fixed list rather than free text
DESIGNATIONS = [
    "Professor",
    "Associate Professor",
    "Assistant Professor",
    "Professor of Practice",
    "Adjunct Professor",
    "Visiting Faculty",
]

MAX_KEYWORDS = 20
KEYWORD_MAX_LEN = 100
BIO_MAX_LEN = 2000
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")


def _clean_text(v: str) -> str:
    return " ".join(v.split())


def _clean_keywords(values: list[str]) -> list[str]:
    """Trim, collapse spaces, drop blanks and case-insensitive duplicates (first spelling wins)."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        k = _clean_text(raw)
        if not k:
            continue
        if len(k) > KEYWORD_MAX_LEN:
            raise ValueError(f'"{k[:30]}…" is too long (max {KEYWORD_MAX_LEN} characters)')
        if k.lower() not in seen:
            seen.add(k.lower())
            out.append(k)
    if len(out) > MAX_KEYWORDS:
        raise ValueError(f"At most {MAX_KEYWORDS} keywords")
    return out


def _check_designation(v: str) -> str:
    v = _clean_text(v)
    if v not in DESIGNATIONS:
        raise ValueError(f"Choose one of: {', '.join(DESIGNATIONS)}")
    return v


# ---------- Profile ----------

class ProfileCreate(BaseModel):
    """FR-008 / UC-004. Name defaults to the account name if omitted."""
    full_name: str | None = Field(default=None, max_length=150)
    department_id: int
    designation: str
    bio: str | None = Field(default=None, max_length=BIO_MAX_LEN)
    expertise_keywords: list[str]
    research_interests: list[str] = []

    @field_validator("full_name")
    @classmethod
    def name(cls, v):
        if v is None:
            return None
        v = _clean_text(v)
        if not v:
            raise ValueError("Full name is required")
        return v

    @field_validator("designation")
    @classmethod
    def designation_valid(cls, v):
        return _check_designation(v)

    @field_validator("bio")
    @classmethod
    def bio_clean(cls, v):
        return (v.strip() or None) if v is not None else None

    @field_validator("expertise_keywords")
    @classmethod
    def expertise(cls, v):
        v = _clean_keywords(v)
        if not v:
            raise ValueError("Add at least one expertise keyword")  # BR-005 / AC-013
        return v

    @field_validator("research_interests")
    @classmethod
    def interests(cls, v):
        return _clean_keywords(v)


class ProfileUpdate(BaseModel):
    """FR-009. Only the fields sent are changed. Keyword lists replace the existing list."""
    full_name: str | None = Field(default=None, max_length=150)
    department_id: int | None = None
    designation: str | None = None
    bio: str | None = Field(default=None, max_length=BIO_MAX_LEN)  # send null or "" to clear
    expertise_keywords: list[str] | None = None
    research_interests: list[str] | None = None

    @field_validator("full_name")
    @classmethod
    def name(cls, v):
        if v is None:
            return None
        v = _clean_text(v)
        if not v:
            raise ValueError("Full name can't be blank")
        return v

    @field_validator("designation")
    @classmethod
    def designation_valid(cls, v):
        return None if v is None else _check_designation(v)

    @field_validator("bio")
    @classmethod
    def bio_clean(cls, v):
        return (v.strip() or None) if v is not None else None

    @field_validator("expertise_keywords")
    @classmethod
    def expertise(cls, v):
        if v is None:
            return None
        v = _clean_keywords(v)
        if not v:
            raise ValueError("Keep at least one expertise keyword")  # BR-005
        return v

    @field_validator("research_interests")
    @classmethod
    def interests(cls, v):
        return None if v is None else _clean_keywords(v)

    @model_validator(mode="after")
    def not_null_where_required(self):
        # Explicit null is only meaningful for bio
        for f in ("full_name", "department_id", "designation", "expertise_keywords", "research_interests"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} can't be null")
        return self


# ---------- Publications (FR-012 / FR-013) ----------

class PublicationIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    venue: str = Field(min_length=1, max_length=200)
    year: int
    doi_url: str | None = Field(default=None, max_length=500)

    @field_validator("title", "venue")
    @classmethod
    def clean(cls, v):
        v = _clean_text(v)
        if not v:
            raise ValueError("Required")
        return v

    @field_validator("year")
    @classmethod
    def year_not_future(cls, v):
        this_year = date.today().year
        if v > this_year:
            raise ValueError(f"Year can't be in the future (max {this_year})")  # BR-007
        if v < 1900:
            raise ValueError("Year must be 1900 or later")
        return v

    @field_validator("doi_url")
    @classmethod
    def doi_or_url(cls, v):
        if v is None or not v.strip():
            return None
        v = v.strip()
        if DOI_RE.match(v):
            return v
        # Only http(s) links: the frontend renders this as a link, so no javascript: etc.
        parsed = urlparse(v)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return v
        raise ValueError("Enter a DOI (e.g. 10.1145/12345) or a link starting with http:// or https://")


# ---------- Projects (FR-014 / FR-015) ----------

class ProjectIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=BIO_MAX_LEN)
    status: ProjectStatus
    start_date: date
    end_date: date | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, v):
        v = _clean_text(v)
        if not v:
            raise ValueError("Required")
        return v

    @field_validator("description")
    @classmethod
    def clean_desc(cls, v):
        return (v.strip() or None) if v is not None else None

    @model_validator(mode="after")
    def dates(self):
        if self.status == ProjectStatus.past:
            # SRS BR-008
            if self.end_date is None:
                raise ValueError("A past project needs an end date")
            if self.end_date <= self.start_date:
                raise ValueError("End date must be after the start date")
        elif self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date can't be before the start date")
        return self


# ---------- Responses ----------

class DepartmentBrief(BaseModel):
    id: int
    name: str
    institute: str


class PublicationOut(BaseModel):
    id: int
    title: str
    venue: str
    year: int
    doi_url: str | None


class ProjectOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: ProjectStatus
    start_date: date
    end_date: date | None


class ProfileOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    department: DepartmentBrief | None
    designation: str | None
    bio: str | None
    expertise_keywords: list[str]
    research_interests: list[str]
    publications: list[PublicationOut]
    projects: list[ProjectOut]
    updated_at: datetime


class OwnProfileOut(ProfileOut):
    # Lets the owner see why they might not appear in search (BR-005)
    is_discoverable: bool
    missing_for_discovery: list[str]
