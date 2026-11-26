"""Per-recipient FIFO notification queue using collections.deque.
The deque is a working in-memory view of pending notification IDs.
SQLite notification rows are the durable source of truth.
"""
from collections import deque


class NotificationQueue:
    """Per-user FIFO notification queue."""

    def __init__(self):
        self._queues: dict[int, deque[int]] = {}

    def enqueue(self, recipient_id: int, notification_id: int) -> None:
        """Add notification to recipient's queue. O(1)."""
        if recipient_id not in self._queues:
            self._queues[recipient_id] = deque()
        self._queues[recipient_id].append(notification_id)

    def dequeue(self, recipient_id: int) -> int | None:
        """Remove and return oldest notification. O(1)."""
        q = self._queues.get(recipient_id)
        if q:
            return q.popleft()
        return None

    def count(self, recipient_id: int) -> int:
        """Number of pending notifications. O(1)."""
        return len(self._queues.get(recipient_id, deque()))

    def get_all(self, recipient_id: int) -> list[int]:
        """List all pending notification IDs in FIFO order. O(n)."""
        return list(self._queues.get(recipient_id, deque()))

    def rebuild(self, notifications: dict[int, list[int]]) -> None:
        """Rebuild all queues from durable records after restart."""
        self._queues.clear()
        for recipient_id, notif_ids in notifications.items():
            self._queues[recipient_id] = deque(notif_ids)

    def clear_user(self, recipient_id: int) -> None:
        """Clear all notifications for a user. O(1)."""
        self._queues.pop(recipient_id, None)
