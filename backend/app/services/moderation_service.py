"""Service for blocking, reporting, admin moderation, export, deletion, and password reset."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from backend.app.core.security import generate_session_token, hash_password, hash_token
from backend.app.models.user import User
from backend.app.repositories.connection_repo import ConnectionRepository
from backend.app.repositories.moderation_repo import ModerationRepository
from backend.app.repositories.post_repo import PostRepository
from backend.app.repositories.profile_repo import ProfileRepository
from backend.app.repositories.user_repo import UserRepository
from backend.app.schemas.moderation import ReportCreate, ReportResolve, ReportResponse


class ModerationService:
    def __init__(self, db: Session):
        self.db = db
        self.mod_repo = ModerationRepository(db)
        self.user_repo = UserRepository(db)
        self.profile_repo = ProfileRepository(db)
        self.connection_repo = ConnectionRepository(db)
        self.post_repo = PostRepository(db)

    def block_user(self, blocker_id: int, username: str) -> None:
        target = self.user_repo.get_by_username(username)
        if target is None:
            raise NotFoundError("User not found")
        if target.id == blocker_id:
            raise ValidationError("Cannot block yourself")
        if self.mod_repo.get_block(blocker_id, target.id) is not None:
            raise ConflictError("User is already blocked")

        self.mod_repo.add_block(blocker_id, target.id)
        # Also remove any existing connection or pending request
        self.connection_repo.remove_connection(blocker_id, target.id)
        pending = self.connection_repo.get_any_pending_between(blocker_id, target.id)
        if pending is not None:
            self.connection_repo.cancel_request(pending)

    def unblock_user(self, blocker_id: int, username: str) -> None:
        target = self.user_repo.get_by_username(username)
        if target is None:
            raise NotFoundError("User not found")
        block = self.mod_repo.get_block(blocker_id, target.id)
        if block is None:
            raise NotFoundError("Block not found")
        self.mod_repo.remove_block(block)

    def create_report(self, reporter_id: int, data: ReportCreate) -> ReportResponse:
        if data.target_type == "user":
            if self.user_repo.get_by_id(data.target_id) is None:
                raise NotFoundError("Reported user not found")
        elif data.target_type == "post":
            if self.post_repo.get_by_id(data.target_id) is None:
                raise NotFoundError("Reported post not found")
        report = self.mod_repo.create_report(
            reporter_id=reporter_id,
            target_type=data.target_type,
            target_id=data.target_id,
            reason=data.reason,
        )
        return ReportResponse.model_validate(report, from_attributes=True)

    def list_reports(
        self, actor: User, status: str | None = None
    ) -> list[ReportResponse]:
        if actor.role not in ("admin", "moderator"):
            raise ForbiddenError("Moderator or admin role required")
        reports = self.mod_repo.list_reports(status=status)
        return [ReportResponse.model_validate(r, from_attributes=True) for r in reports]

    def resolve_report(
        self, actor: User, report_id: int, data: ReportResolve
    ) -> ReportResponse:
        if actor.role not in ("admin", "moderator"):
            raise ForbiddenError("Moderator or admin role required")
        report = self.mod_repo.get_report(report_id)
        if report is None:
            raise NotFoundError("Report not found")
        updated = self.mod_repo.resolve_report(
            report, data.status, data.resolution_note, actor.id
        )
        return ReportResponse.model_validate(updated, from_attributes=True)

    def export_user_data(self, user_id: int) -> dict:
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        profile = self.profile_repo.get_by_user_id(user_id)
        skills = self.profile_repo.get_skills(user_id)
        posts = self.post_repo.get_user_posts(user_id, limit=500, offset=0)
        conns = self.connection_repo.get_user_connections(user_id)
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "created_at": user.created_at.isoformat(),
            },
            "profile": {
                "display_name": profile.display_name if profile else "",
                "programme": profile.programme if profile else "",
                "year": profile.year if profile else 1,
                "bio": profile.bio if profile else "",
                "visibility": profile.visibility if profile else "campus",
                "skills": skills,
            },
            "connection_ids": [cid for cid, _ in conns],
            "posts": [
                {
                    "id": p.id,
                    "body": p.body,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ],
        }

    def delete_account(self, user_id: int) -> None:
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        self.db.query(User).filter(User.id == user_id).delete()
        self.db.commit()

    def request_password_reset(self, username: str) -> str | None:
        user = self.user_repo.get_by_username(username)
        if user is None or user.status != "active":
            return None
        raw_token = generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        self.mod_repo.create_reset_token(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
        return raw_token

    def confirm_password_reset(self, token: str, new_password: str) -> None:
        tok = self.mod_repo.get_valid_reset_token(hash_token(token))
        if tok is None:
            raise ValidationError("Invalid or expired password reset token")
        user = self.user_repo.get_by_id(tok.user_id)
        if user is None or user.status != "active":
            raise NotFoundError("User not found")
        user.password_hash = hash_password(new_password)
        self.mod_repo.mark_reset_token_used(tok)
        self.mod_repo.invalidate_all_reset_tokens(user.id)
        self.user_repo.revoke_all_sessions(user.id)
        self.db.commit()
