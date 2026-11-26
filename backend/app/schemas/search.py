"""Search schemas."""
from pydantic import BaseModel
from backend.app.schemas.profile import ProfileSummary


class SearchResult(BaseModel):
    users: list[ProfileSummary]
    query: str
    count: int
