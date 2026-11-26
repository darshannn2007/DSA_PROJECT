"""Moderation, report, and password reset schemas."""
from datetime import datetime
from pydantic import BaseModel, field_validator
from backend.app.core.security import validate_password_policy


class ReportCreate(BaseModel):
    target_type: str  # user | post
    target_id: int
    reason: str

    @field_validator("target_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("user", "post"):
            raise ValueError("target_type must be 'user' or 'post'")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 500:
            raise ValueError("Reason must be 3-500 characters")
        return v


class ReportResolve(BaseModel):
    status: str  # resolved | dismissed
    resolution_note: str = ""

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("resolved", "dismissed"):
            raise ValueError("Status must be 'resolved' or 'dismissed'")
        return v


class ReportResponse(BaseModel):
    id: int
    reporter_id: int
    target_type: str
    target_id: int
    reason: str
    status: str
    resolution_note: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class PasswordResetRequestBody(BaseModel):
    username: str


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_pw(cls, v: str) -> str:
        return validate_password_policy(v)
