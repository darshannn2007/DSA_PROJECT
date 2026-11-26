"""Profile request/response schemas."""
from pydantic import BaseModel, field_validator, model_validator


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    programme: str | None = None
    degree_level: str | None = None
    year: int | None = None
    bio: str | None = None
    skills: list[str] | None = None
    visibility: str | None = None

    @field_validator("degree_level")
    @classmethod
    def validate_degree_level(cls, v):
        if v is not None and v not in ("UG", "PG"):
            raise ValueError("Degree level must be 'UG' or 'PG'")
        return v

    @model_validator(mode="after")
    def validate_year_for_degree(self):
        if self.year is not None:
            level = self.degree_level or "UG"
            max_year = 2 if level == "PG" else 4
            if self.year < 1 or self.year > max_year:
                raise ValueError(f"Year for {level} must be between 1 and {max_year}")
        return self

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v):
        if v is not None and v not in ("campus", "connections"):
            raise ValueError("Visibility must be 'campus' or 'connections'")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v):
        if v is not None and len(v) > 100:
            raise ValueError("Display name must be at most 100 characters")
        return v

    @field_validator("year")
    @classmethod
    def validate_year(cls, v):
        if v is not None and (v < 1 or v > 6):
            raise ValueError("Year must be between 1 and 6")
        return v

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, v):
        if v is not None and len(v) > 500:
            raise ValueError("Bio must be at most 500 characters")
        return v

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v):
        if v is not None and len(v) > 20:
            raise ValueError("Maximum 20 skills allowed")
        return v


class ProfileResponse(BaseModel):
    user_id: int
    username: str
    display_name: str
    programme: str
    degree_level: str = "UG"
    year: int
    bio: str
    skills: list[str] = []
    visibility: str = "campus"
    avatar_url: str | None = None
    is_connected: bool = False
    connection_status: str | None = None
    is_blocked: bool = False
    model_config = {"from_attributes": True}


class ProfileSummary(BaseModel):
    user_id: int
    username: str
    display_name: str
    programme: str = ""
    degree_level: str = "UG"
    year: int = 1
    avatar_url: str | None = None
    model_config = {"from_attributes": True}
