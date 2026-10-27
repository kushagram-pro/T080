from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Must not be blank")
    return v


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    institute: str = Field(default="LNMIIT", min_length=1, max_length=255)  # SRS: single institution for now

    @field_validator("name", "institute")
    @classmethod
    def clean(cls, v: str) -> str:
        return _clean(v)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    institute: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name", "institute")
    @classmethod
    def clean(cls, v: str | None) -> str | None:
        return None if v is None else _clean(v)

    @model_validator(mode="after")
    def at_least_one(self):
        if self.name is None and self.institute is None:
            raise ValueError("Provide a name and/or institute to update")
        return self


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    institute: str
    faculty_count: int = 0
