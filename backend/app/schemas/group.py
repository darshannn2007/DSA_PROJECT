"""Group schemas."""
from datetime import datetime
from pydantic import BaseModel, field_validator


class GroupCreate(BaseModel):
    name: str
    description: str = ""
    visibility: str = "campus"
    membership_policy: str = "open"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 100:
            raise ValueError("Group name must be 2-100 characters")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in ("campus", "private"):
            raise ValueError("Visibility must be 'campus' or 'private'")
        return v

    @field_validator("membership_policy")
    @classmethod
    def validate_policy(cls, v: str) -> str:
        if v not in ("open", "request", "invite"):
            raise ValueError("Membership policy must be 'open', 'request', or 'invite'")
        return v


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str
    visibility: str
    membership_policy: str
    created_by: int
    member_count: int
    my_role: str | None = None
    my_status: str | None = None
    created_at: datetime


class GroupSuggestionResponse(BaseModel):
    id: int
    name: str
    description: str
    visibility: str
    membership_policy: str
    member_count: int
    score: float
    reason: str
