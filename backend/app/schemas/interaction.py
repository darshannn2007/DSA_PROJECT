"""Like and comment schemas."""
from datetime import datetime
from pydantic import BaseModel, field_validator
from backend.app.schemas.profile import ProfileSummary


class CommentCreate(BaseModel):
    body: str
    parent_comment_id: int | None = None

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment cannot be empty")
        if len(v) > 1000:
            raise ValueError("Comment must be at most 1000 characters")
        return v


class CommentResponse(BaseModel):
    id: int
    post_id: int
    author: ProfileSummary
    parent_comment_id: int | None = None
    body: str
    created_at: datetime
    replies: list["CommentResponse"] = []


class LikeToggleResponse(BaseModel):
    post_id: int
    liked: bool
    like_count: int
