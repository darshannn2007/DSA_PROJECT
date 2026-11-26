"""Authentication request/response schemas."""
import re
from datetime import datetime
from pydantic import BaseModel, field_validator
from backend.app.core.security import validate_password_policy


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 30:
            raise ValueError("Username must be 3-30 characters")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_policy(v)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}


class MeResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}
