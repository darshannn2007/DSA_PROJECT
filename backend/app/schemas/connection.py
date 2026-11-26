"""Connection schemas."""
from datetime import datetime
from pydantic import BaseModel
from backend.app.schemas.profile import ProfileSummary


class ConnectionRequestResponse(BaseModel):
    id: int
    sender: ProfileSummary
    receiver: ProfileSummary
    status: str
    created_at: datetime


class ConnectionResponse(BaseModel):
    user: ProfileSummary
    connected_since: datetime


class MutualConnectionsResponse(BaseModel):
    user_id: int
    other_user_id: int
    mutual_connections: list[ProfileSummary]
    count: int


class SuggestionResponse(BaseModel):
    user: ProfileSummary
    score: float
    mutual_count: int
    reason: str


class PathResponse(BaseModel):
    path: list[ProfileSummary]
    hop_count: int
    degree_label: str
