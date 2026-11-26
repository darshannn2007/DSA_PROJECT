"""Post schemas."""
from datetime import datetime
from pydantic import BaseModel, field_validator
from backend.app.schemas.profile import ProfileSummary


class PostCreate(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Post body cannot be empty")
        if len(v) > 5000:
            raise ValueError("Post body must be at most 5000 characters")
        return v


class PostResponse(BaseModel):
    id: int
    author: ProfileSummary
    body: str
    image_url: str | None = None
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    trending_score: float | None = None
    trending_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class FeedResponse(BaseModel):
    posts: list[PostResponse]
    next_cursor: str | None = None
