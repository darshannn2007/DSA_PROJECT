"""Trie for prefix-based username and name search.

Insert: O(L) per key where L is key length.
Search: O(L) to reach prefix node, then bounded enumeration.
Space: O(total characters across all keys).
"""
import unicodedata


class TrieNode:
    __slots__ = ("children", "user_ids")

    def __init__(self):
        self.children: dict[str, "TrieNode"] = {}
        self.user_ids: set[int] = set()


class Trie:
    def __init__(self):
        self.root = TrieNode()

    @staticmethod
    def normalize(text: str) -> str:
        """NFKC normalize and casefold for consistent matching."""
        return unicodedata.normalize("NFKC", text.strip()).casefold()

    def insert(self, key: str, user_id: int) -> None:
        """Insert a normalized key mapped to a user ID. O(L)."""
        normalized = self.normalize(key)
        if not normalized:
            return
        node = self.root
        for char in normalized:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.user_ids.add(user_id)

    def search_prefix(self, prefix: str, limit: int = 10) -> list[int]:
        """Find user IDs matching prefix. O(L + result enumeration)."""
        normalized = self.normalize(prefix)
        if not normalized:
            return []
        node = self.root
        for char in normalized:
            if char not in node.children:
                return []
            node = node.children[char]
        result_ids: set[int] = set()
        stack = [node]
        while stack and len(result_ids) < limit:
            current = stack.pop()
            result_ids.update(current.user_ids)
            if len(result_ids) >= limit:
                break
            for child in current.children.values():
                stack.append(child)
        return list(result_ids)[:limit]

    def remove(self, key: str, user_id: int) -> None:
        """Remove a user_id from a key's terminal node."""
        normalized = self.normalize(key)
        if not normalized:
            return
        node = self.root
        for char in normalized:
            if char not in node.children:
                return
            node = node.children[char]
        node.user_ids.discard(user_id)

    def rebuild(self, entries: list[tuple[str, int]]) -> None:
        """Rebuild entire Trie from (key, user_id) pairs."""
        self.root = TrieNode()
        for key, user_id in entries:
            self.insert(key, user_id)
