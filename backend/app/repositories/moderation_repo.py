"""Repository for UserBlock, Report, and PasswordResetToken."""
from datetime import datetime, timezone
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.models.moderation import UserBlock, Report, PasswordResetToken


class ModerationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_block(self, blocker_id: int, blocked_id: int) -> UserBlock | None:
        return (
            self.db.query(UserBlock)
            .filter(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == blocked_id,
            )
            .first()
        )

    def add_block(self, blocker_id: int, blocked_id: int) -> UserBlock:
        block = UserBlock(blocker_id=blocker_id, blocked_id=blocked_id)
        self.db.add(block)
        self.db.commit()
        return block

    def remove_block(self, block: UserBlock) -> None:
        self.db.delete(block)
        self.db.commit()

    def get_blocked_ids_for_user(self, user_id: int) -> set[int]:
        """Return all user IDs blocked by or blocking user_id."""
        rows = (
            self.db.query(UserBlock.blocker_id, UserBlock.blocked_id)
            .filter(
                or_(
                    UserBlock.blocker_id == user_id,
                    UserBlock.blocked_id == user_id,
                )
            )
            .all()
        )
        blocked: set[int] = set()
        for b1, b2 in rows:
            blocked.add(b2 if b1 == user_id else b1)
        return blocked

    def create_report(
        self, reporter_id: int, target_type: str, target_id: int, reason: str
    ) -> Report:
        report = Report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def list_reports(self, status: str | None = None) -> list[Report]:
        q = self.db.query(Report)
        if status:
            q = q.filter(Report.status == status)
        return q.order_by(Report.created_at.desc()).all()

    def get_report(self, report_id: int) -> Report | None:
        return self.db.query(Report).filter(Report.id == report_id).first()

    def resolve_report(
        self, report: Report, status: str, resolution_note: str, reviewer_id: int
    ) -> Report:
        report.status = status
        report.resolution_note = resolution_note
        report.reviewed_by = reviewer_id
        report.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(report)
        return report

    def create_reset_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> PasswordResetToken:
        tok = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.db.add(tok)
        self.db.commit()
        self.db.refresh(tok)
        return tok

    def get_valid_reset_token(self, token_hash: str) -> PasswordResetToken | None:
        tok = (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
            )
            .first()
        )
        if tok is None:
            return None
        now = datetime.now(timezone.utc)
        exp = tok.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now:
            return None
        return tok

    def mark_reset_token_used(self, tok: PasswordResetToken) -> None:
        tok.used_at = datetime.now(timezone.utc)
        self.db.commit()

    def invalidate_all_reset_tokens(self, user_id: int) -> None:
        now = datetime.now(timezone.utc)
        (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
            )
            .update({PasswordResetToken.used_at: now}, synchronize_session=False)
        )
        self.db.commit()
