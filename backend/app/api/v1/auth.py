"""Authentication, password change/reset, and session management routes."""
from fastapi import APIRouter, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from backend.app.api.v1.deps import get_current_user
from backend.app.core.config import settings
from backend.app.core.errors import AppError
from backend.app.core.security import (
    generate_csrf_token,
    rate_limiter,
    validate_password_policy,
)
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RegisterRequest,
    UserResponse,
)
from backend.app.schemas.moderation import (
    PasswordResetConfirmBody,
    PasswordResetRequestBody,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.moderation_service import ModerationService
from backend.app.services.notification_service import NotificationService

router = APIRouter(tags=["auth"])


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_pw(cls, v: str) -> str:
        return validate_password_policy(v)


def _set_auth_cookies(response: Response, raw_token: str) -> None:
    max_age = settings.SESSION_EXPIRE_MINUTES * 60
    response.set_cookie(
        key="session_token",
        value=raw_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        key="csrf_token",
        value=generate_csrf_token(),
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/auth/register", response_model=UserResponse, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        rate_limiter.check("register", _client_ip(request), limit=20, window_seconds=60)
        auth_service = AuthService(db)
        auth_service.register(
            username=payload.username,
            password=payload.password,
            email=payload.email,
        )
        user, raw_token = auth_service.login(
            username=payload.username,
            password=payload.password,
        )
        _set_auth_cookies(response, raw_token)
        return UserResponse.model_validate(user)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/auth/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        ip = _client_ip(request)
        rate_limiter.check("login_ip", ip, limit=30, window_seconds=60)
        rate_limiter.check("login_user", payload.username.strip().lower(), limit=15, window_seconds=60)
        user, raw_token = AuthService(db).login(
            username=payload.username,
            password=payload.password,
        )
        _set_auth_cookies(response, raw_token)
        return UserResponse.model_validate(user)
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/auth/logout")
def logout(
    response: Response,
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
):
    try:
        AuthService(db).logout(session_token)
        response.delete_cookie(key="session_token", path="/")
        response.delete_cookie(key="csrf_token", path="/")
        return {"status": "logged_out"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/auth/me", response_model=MeResponse)
def me(current_user: User = Depends(get_current_user)):
    return MeResponse.model_validate(current_user)


@router.post("/auth/password-reset/request")
def request_password_reset(
    payload: PasswordResetRequestBody,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        rate_limiter.check("reset_req", _client_ip(request), limit=10, window_seconds=60)
        token = ModerationService(db).request_password_reset(payload.username)
        body = {
            "status": "ok",
            "message": "If the account exists, password reset instructions have been sent.",
        }
        if settings.EXPOSE_RESET_TOKEN_FOR_TESTS and token is not None:
            body["reset_token"] = token
        return body
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/auth/password-reset/confirm")
def confirm_password_reset(
    payload: PasswordResetConfirmBody,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        rate_limiter.check("reset_confirm", _client_ip(request), limit=10, window_seconds=60)
        ModerationService(db).confirm_password_reset(payload.token, payload.new_password)
        return {"status": "password_updated"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.post("/me/password")
def change_password(
    payload: ChangePasswordBody,
    response: Response,
    session_token: str | None = Cookie(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        new_token = AuthService(db).change_password(
            user_id=current_user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            current_token=session_token,
        )
        NotificationService(db).create_notification(
            recipient_id=current_user.id,
            actor_id=current_user.id,
            type="password_changed",
            entity_type="user",
            entity_id=current_user.id,
        )
        _set_auth_cookies(response, new_token)
        return {"status": "password_updated"}
    except AppError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )


@router.get("/me/sessions")
def list_my_sessions(
    session_token: str | None = Cookie(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return AuthService(db).list_active_sessions(current_user.id, session_token)


@router.delete("/me/sessions/{session_id}")
def revoke_my_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    revoked = AuthService(db).revoke_session_by_id(current_user.id, session_id)
    if not revoked:
        return JSONResponse(
            status_code=404,
            content={"code": "not_found", "message": "Session not found"},
        )
    return {"status": "revoked"}
