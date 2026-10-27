from pydantic import BaseModel

from app.schemas.profile import DepartmentBrief


class SearchResult(BaseModel):
    """FR-020: name, department, designation and the keywords that matched."""
    user_id: int
    full_name: str
    department: DepartmentBrief | None
    designation: str | None
    matched_keywords: list[str]
    expertise_keywords: list[str]
    research_interests: list[str]


class SearchPage(BaseModel):
    terms: list[str]  # the keywords actually searched for, after cleaning
    total: int
    page: int
    page_size: int
    results: list[SearchResult]


class Suggestion(BaseModel):
    """FR-024: name, department and the shared keywords behind the suggestion."""
    user_id: int
    full_name: str
    department: DepartmentBrief | None
    designation: str | None
    shared_keywords: list[str]
    score: int
