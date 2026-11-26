"""Notification service integrating durable SQLite storage with FIFO NotificationQueue."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.app.core.errors import NotFoundError
from backend.app.dsa.queue import NotificationQueue
from backend.app.models.notification import Notification
from backend.app.repositories.notification_repo import NotificationRepository
from backend.app.schemas.notification import NotificationList, NotificationResponse
from backend.app.services.profile_service import ProfileService


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

# Process-local FIFO working view; rebuilt from SQLite after restart
_notif_queue = NotificationQueue()
_loaded_users: set[int] = set()


class NotificationService:
    def __init__(self, db: Session):
        self.db = db
        self.notification_repo = NotificationRepository(db)
        self.profile_service = ProfileService(db)

    def _ensure_queue_loaded(self, user_id: int) -> None:
        if user_id not in _loaded_users:
            unread_ids = list(
                reversed(self.notification_repo.get_unread_ids_by_recipient(user_id))
            )
            for nid in unread_ids:
                _notif_queue.enqueue(user_id, nid)
            _loaded_users.add(user_id)

    def get_fifo_unread_ids(self, user_id: int) -> list[int]:
        """Return unread notification IDs in FIFO order from NotificationQueue."""
        self._ensure_queue_loaded(user_id)
        return _notif_queue.get_all(user_id)

    def create_notification(
        self,
        recipient_id: int,
        actor_id: int,
        type: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> Notification:
        notif = self.notification_repo.create(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self._ensure_queue_loaded(recipient_id)
        _notif_queue.enqueue(recipient_id, notif.id)
        return notif

    def get_notifications(
        self, user_id: int, limit: int = 50
    ) -> NotificationList:
        self._ensure_queue_loaded(user_id)
        notifications = self.notification_repo.get_for_user(user_id, limit=limit)
        actor_ids = list({n.actor_id for n in notifications if n.actor_id is not None})
        summaries = self.profile_service.get_multiple_summaries(actor_ids)
        items = [
            NotificationResponse(
                id=n.id,
                type=n.type,
                actor=summaries.get(n.actor_id),
                entity_type=n.entity_type,
                entity_id=n.entity_id,
                created_at=_ensure_utc(n.created_at),
                read_at=_ensure_utc(n.read_at),
            )
            for n in notifications
        ]
        unread_count = self.notification_repo.get_unread_count(user_id)
        return NotificationList(notifications=items, unread_count=unread_count)

    def mark_read(
        self, notification_id: int, user_id: int
    ) -> NotificationResponse:
        notification = self.notification_repo.mark_read(notification_id, user_id)
        if notification is None:
            raise NotFoundError("Notification not found")
        # Refresh user's FIFO queue view
        _loaded_users.discard(user_id)
        _notif_queue.clear_user(user_id)
        self._ensure_queue_loaded(user_id)

        actor = (
            self.profile_service.get_profile_summary(notification.actor_id)
            if notification.actor_id is not None
            else None
        )
        return NotificationResponse(
            id=notification.id,
            type=notification.type,
            actor=actor,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            created_at=_ensure_utc(notification.created_at),
            read_at=_ensure_utc(notification.read_at),
        )

    def mark_all_read(self, user_id: int) -> dict[str, int]:
        count = self.notification_repo.mark_all_read(user_id)
        _notif_queue.clear_user(user_id)
        _loaded_users.add(user_id)
        return {"marked_read": count}

    def get_unread_count(self, user_id: int) -> dict[str, int]:
        count = self.notification_repo.get_unread_count(user_id)
        return {"unread_count": count}
