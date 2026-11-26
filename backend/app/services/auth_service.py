"""Authentication service."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.errors import ConflictError, UnauthorizedError
from backend.app.core.security import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)
from backend.app.models.user import User
from backend.app.repositories.user_repo import UserRepository


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def register(
        self,
        username: str,
        password: str,
        email: str | None = None,
    ) -> User:
        existing = self.user_repo.get_by_username(username)
        if existing is not None:
            raise ConflictError("Username already exists")

        password_hash = hash_password(password)
        return self.user_repo.create_user(
            username=username,
            password_hash=password_hash,
            email=email,
        )

    def login(self, username: str, password: str) -> tuple[User, str]:
        user = self.user_repo.get_by_username(username)
        if user is None or user.status != "active":
            raise UnauthorizedError("Invalid username or password")
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid username or password")

        raw_token = generate_session_token()
        token_hash = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.SESSION_EXPIRE_MINUTES
        )
        self.user_repo.create_session(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return user, raw_token

    def logout(self, token: str | None) -> None:
        if not token:
            return
        self.user_repo.revoke_session(hash_token(token))

    def get_current_user(self, token: str | None) -> User:
        if not token:
            raise UnauthorizedError("Not authenticated")
        session = self.user_repo.get_session_by_token(hash_token(token))
        if session is None:
            raise UnauthorizedError("Invalid or expired session")
        user = self.user_repo.get_by_id(session.user_id)
        if user is None or user.status != "active":
            raise UnauthorizedError("User not found or inactive")
        return user

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_token: str | None = None,
    ) -> str:
        """Verify current password, update Argon2id hash, rotate session, revoke others."""
        user = self.user_repo.get_by_id(user_id)
        if user is None or user.status != "active":
            raise UnauthorizedError("User not found")
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect")

        user.password_hash = hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        # Revoke all existing sessions and issue a fresh rotated session
        self.user_repo.revoke_all_sessions(user.id)

        raw_token = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.SESSION_EXPIRE_MINUTES
        )
        self.user_repo.create_session(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        return raw_token

    def list_active_sessions(self, user_id: int, current_token: str | None) -> list[dict]:
        current_hash = hash_token(current_token) if current_token else None
        sessions = self.user_repo.list_active_sessions(user_id)
        return [
            {
                "id": s.id,
                "created_at": s.created_at,
                "expires_at": s.expires_at,
                "is_current": s.token_hash == current_hash,
            }
            for s in sessions
        ]

    def revoke_session_by_id(self, user_id: int, session_id: int) -> bool:
        return self.user_repo.revoke_session_by_id(user_id, session_id)
