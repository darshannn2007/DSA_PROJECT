"""Bounded LIFO stack for per-user undo history.
User-scoped with expiry. Not a global stack.
"""
from datetime import datetime, timezone
from typing import Any, Optional


class UndoAction:
    __slots__ = ("action_id", "user_id", "action_type", "target_type",
                 "target_id", "payload", "created_at", "expires_at", "consumed")

    def __init__(self, action_id: int, user_id: int, action_type: str,
                 target_type: str, target_id: int, payload: Any,
                 created_at: datetime, expires_at: datetime):
        self.action_id = action_id
        self.user_id = user_id
        self.action_type = action_type
        self.target_type = target_type
        self.target_id = target_id
        self.payload = payload
        self.created_at = created_at
        self.expires_at = expires_at
        self.consumed = False


class UndoStack:
    """Per-user bounded LIFO undo stack."""

    def __init__(self, max_size: int = 50):
        self._stacks: dict[int, list[UndoAction]] = {}
        self._max_size = max_size

    def push(self, action: UndoAction) -> None:
        """Push an undoable action. O(1). Evicts oldest if at capacity."""
        if action.user_id not in self._stacks:
            self._stacks[action.user_id] = []
        stack = self._stacks[action.user_id]
        if len(stack) >= self._max_size:
            stack.pop(0)
        stack.append(action)

    def peek(self, user_id: int) -> Optional[UndoAction]:
        """View most recent unexpired, unconsumed undo."""
        stack = self._stacks.get(user_id, [])
        now = datetime.now(timezone.utc)
        while stack and (stack[-1].consumed or stack[-1].expires_at < now):
            stack.pop()
        return stack[-1] if stack else None

    def pop(self, user_id: int) -> Optional[UndoAction]:
        """Pop and consume most recent valid undo action."""
        action = self.peek(user_id)
        if action:
            action.consumed = True
            self._stacks[user_id].pop()
            return action
        return None

    def clear_user(self, user_id: int) -> None:
        """Clear all undo history for a user."""
        self._stacks.pop(user_id, None)
