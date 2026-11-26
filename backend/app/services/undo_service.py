"""Durable per-user UndoService backed by UndoStack (LIFO) + SQLite."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from backend.app.core.errors import ForbiddenError, NotFoundError, ValidationError
from backend.app.dsa.stack import UndoAction, UndoStack
from backend.app.models.extras import UndoActionRecord
from backend.app.models.post import Post


class UndoService:
    """User-scoped LIFO undo history for recent soft-deleted posts."""

    def __init__(self, db: Session):
        self.db = db

    def record_post_delete(
        self, user_id: int, post_id: int, ttl_seconds: int = 120
    ) -> UndoActionRecord:
        now = datetime.now(timezone.utc)
        rec = UndoActionRecord(
            user_id=user_id,
            action_type="restore_post",
            target_type="post",
            target_id=post_id,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def _build_user_stack(self, user_id: int) -> UndoStack:
        """Rebuild the user's bounded LIFO UndoStack from durable SQLite records."""
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(UndoActionRecord)
            .filter(
                UndoActionRecord.user_id == user_id,
                UndoActionRecord.consumed_at.is_(None),
            )
            .order_by(UndoActionRecord.created_at.asc(), UndoActionRecord.id.asc())
            .all()
        )
        stack = UndoStack(max_size=50)
        for r in rows:
            exp = r.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp <= now:
                continue
            created = r.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            stack.push(
                UndoAction(
                    action_id=r.id,
                    user_id=r.user_id,
                    action_type=r.action_type,
                    target_type=r.target_type,
                    target_id=r.target_id,
                    payload=None,
                    created_at=created,
                    expires_at=exp,
                )
            )
        return stack

    def undo_latest(self, user_id: int) -> dict:
        stack = self._build_user_stack(user_id)
        action = stack.pop(user_id)
        if action is None:
            raise NotFoundError("No unexpired undoable action found")

        rec = (
            self.db.query(UndoActionRecord)
            .filter(
                UndoActionRecord.id == action.action_id,
                UndoActionRecord.user_id == user_id,
                UndoActionRecord.consumed_at.is_(None),
            )
            .first()
        )
        if rec is None:
            raise NotFoundError("Undo action already consumed")

        if action.action_type == "restore_post" and action.target_type == "post":
            post = self.db.query(Post).filter(Post.id == action.target_id).first()
            if post is None:
                raise NotFoundError("Post no longer exists")
            if post.author_id != user_id:
                raise ForbiddenError("Cannot undo another user's post")
            post.deleted_at = None
            rec.consumed_at = datetime.now(timezone.utc)
            self.db.commit()
            return {"status": "restored", "target_type": "post", "target_id": post.id}

        raise ValidationError("Unsupported undo action")
