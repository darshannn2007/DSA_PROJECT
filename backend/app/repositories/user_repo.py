"""User and session repository."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.profile import Profile
from backend.app.models.session import UserSession


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(
        self,
        username: str,
        password_hash: str,
        email: str | None = None,
        role: str = "student",
    ) -> User:
        clean_username = username.strip()
        user = User(
            username=clean_username,
            username_normalized=clean_username.lower(),
            email=email,
            password_hash=password_hash,
            role=role,
            status="active",
        )
        self.db.add(user)
        self.db.flush()

        profile = Profile(
            user_id=user.id,
            display_name=clean_username,
        )
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_username(self, username: str) -> User | None:
        normalized = username.strip().lower()
        return (
            self.db.query(User)
            .filter(User.username_normalized == normalized)
            .first()
        )

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_active_ids(self) -> list[int]:
        rows = self.db.query(User.id).filter(User.status == "active").all()
        return [row[0] for row in rows]

    def get_all_active_users(self) -> list[User]:
        return self.db.query(User).filter(User.status == "active").all()

    def create_session(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
    ) -> UserSession:
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session_by_token(self, token_hash: str) -> UserSession | None:
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
            )
            .first()
        )
        if session is None:
            return None

        now = datetime.now(timezone.utc)
        expires_at = session.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return None
        return session

    def revoke_session(self, token_hash: str) -> None:
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.token_hash == token_hash,
                UserSession.revoked_at.is_(None),
            )
            .first()
        )
        if session is not None:
            session.revoked_at = datetime.now(timezone.utc)
            self.db.commit()

    def list_active_sessions(self, user_id: int) -> list[UserSession]:
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .order_by(UserSession.created_at.desc())
            .all()
        )
        active = []
        for s in rows:
            exp = s.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                active.append(s)
        return active

    def revoke_other_sessions(self, user_id: int, keep_token_hash: str) -> int:
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.token_hash != keep_token_hash,
                UserSession.revoked_at.is_(None),
            )
            .update({UserSession.revoked_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def revoke_all_sessions(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .update({UserSession.revoked_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def revoke_session_by_id(self, user_id: int, session_id: int) -> bool:
        s = (
            self.db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .first()
        )
        if s is None:
            return False
        s.revoked_at = datetime.now(timezone.utc)
        self.db.commit()
        return True
