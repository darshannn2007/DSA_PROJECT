"""Notification repository."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.models.notification import Notification


class NotificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        recipient_id: int,
        actor_id: int,
        type: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        return notification

    def get_for_user(self, user_id: int, limit: int = 50) -> list[Notification]:
        return (
            self.db.query(Notification)
            .filter(Notification.recipient_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .all()
        )

    def get_unread_count(self, user_id: int) -> int:
        return (
            self.db.query(Notification)
            .filter(
                Notification.recipient_id == user_id,
                Notification.read_at.is_(None),
            )
            .count()
        )

    def mark_read(self, notification_id: int, user_id: int) -> Notification | None:
        notification = (
            self.db.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.recipient_id == user_id,
            )
            .first()
        )
        if notification is None:
            return None
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(notification)
        return notification

    def mark_all_read(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(Notification)
            .filter(
                Notification.recipient_id == user_id,
                Notification.read_at.is_(None),
            )
            .update({Notification.read_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return count

    def get_unread_ids_by_recipient(self, user_id: int) -> list[int]:
        rows = (
            self.db.query(Notification.id)
            .filter(
                Notification.recipient_id == user_id,
                Notification.read_at.is_(None),
            )
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .all()
        )
        return [row[0] for row in rows]
