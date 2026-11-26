"""API v1 dependencies for authentication."""
from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.db.database import get_db
from backend.app.models.user import User
from backend.app.services.auth_service import AuthService


def get_current_user(
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Require a valid authenticated session cookie."""
    return AuthService(db).get_current_user(session_token)


def get_optional_user(
    session_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user if a valid session cookie is present, else None."""
    if not session_token:
        return None
    try:
        return AuthService(db).get_current_user(session_token)
    except AppError:
        return None
