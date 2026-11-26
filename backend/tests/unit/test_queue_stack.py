"""Unit tests for NotificationQueue (FIFO) and UndoStack (LIFO)."""
from datetime import datetime, timedelta, timezone
from backend.app.dsa.queue import NotificationQueue
from backend.app.dsa.stack import UndoAction, UndoStack


def test_notification_queue_fifo_and_rebuild():
    q = NotificationQueue()
    q.enqueue(1, 101)
    q.enqueue(1, 102)
    q.enqueue(2, 201)

    assert q.get_all(1) == [101, 102]
    assert q.dequeue(1) == 101
    assert q.dequeue(1) == 102
    assert q.dequeue(1) is None

    q.rebuild({1: [301, 302]})
    assert q.get_all(1) == [301, 302]
    assert q.count(2) == 0


def test_undo_stack_lifo_expiry_and_isolation():
    now = datetime.now(timezone.utc)
    s = UndoStack(max_size=10)
    a1 = UndoAction(1, 10, "restore_post", "post", 50, None, now, now + timedelta(minutes=2))
    a2 = UndoAction(2, 10, "restore_post", "post", 51, None, now, now + timedelta(minutes=2))
    expired = UndoAction(3, 10, "restore_post", "post", 52, None, now, now - timedelta(seconds=1))
    other = UndoAction(4, 20, "restore_post", "post", 99, None, now, now + timedelta(minutes=2))

    s.push(a1)
    s.push(a2)
    s.push(expired)
    s.push(other)

    # Expired action skipped; LIFO pops a2 then a1 for user 10
    assert s.pop(10).target_id == 51
    assert s.pop(10).target_id == 50
    assert s.pop(10) is None
    # User 20's stack is isolated
    assert s.pop(20).target_id == 99
