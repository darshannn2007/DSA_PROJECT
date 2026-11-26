"""K-way merge of per-author post streams using heapq.

For C author streams and K returned posts:
Time: O(K log C). Space: O(C) for heap.
Total order: created_at DESC, post_id DESC, author_id ASC.
"""
import base64
import heapq
import json
from datetime import datetime
from typing import Optional


class FeedMerger:
    """Merge multiple author post streams into one newest-first feed."""

    @staticmethod
    def merge_feeds(author_streams: dict[int, list[dict]], limit: int = 20,
                    after_cursor: Optional[tuple] = None) -> list[dict]:
        """Merge bounded per-author streams into global newest-first order."""
        heap: list[tuple] = []
        stream_indices: dict[int, int] = {}
        for author_id, posts in author_streams.items():
            if not posts:
                continue
            stream_indices[author_id] = 0
            post = posts[0]
            created_at = post["created_at"]
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            heapq.heappush(heap, (-created_at.timestamp(), -post["id"], author_id, post))
        result: list[dict] = []
        while heap and len(result) < limit:
            neg_ts, neg_pid, author_id, post = heapq.heappop(heap)
            if after_cursor is not None:
                cursor_ts, cursor_pid, cursor_aid = after_cursor
                post_key = (-neg_ts, -neg_pid, author_id)
                cursor_key = (cursor_ts, cursor_pid, cursor_aid)
                if post_key >= cursor_key:
                    idx = stream_indices[author_id] + 1
                    posts_list = author_streams[author_id]
                    if idx < len(posts_list):
                        stream_indices[author_id] = idx
                        np = posts_list[idx]
                        nt = np["created_at"]
                        if isinstance(nt, str):
                            nt = datetime.fromisoformat(nt)
                        heapq.heappush(heap, (-nt.timestamp(), -np["id"], author_id, np))
                    continue
            result.append(post)
            idx = stream_indices[author_id] + 1
            pl = author_streams[author_id]
            if idx < len(pl):
                stream_indices[author_id] = idx
                np = pl[idx]
                nt = np["created_at"]
                if isinstance(nt, str):
                    nt = datetime.fromisoformat(nt)
                heapq.heappush(heap, (-nt.timestamp(), -np["id"], author_id, np))
        return result

    @staticmethod
    def make_cursor(post: dict) -> str:
        """Create opaque cursor from last post in page."""
        created_at = post["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        data = json.dumps([created_at, post["id"], post["author_id"]])
        return base64.urlsafe_b64encode(data.encode()).decode()

    @staticmethod
    def parse_cursor(cursor: str) -> Optional[tuple]:
        """Parse cursor back to (timestamp, post_id, author_id)."""
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor).decode())
            ts = datetime.fromisoformat(data[0]).timestamp()
            return (ts, data[1], data[2])
        except Exception:
            return None
