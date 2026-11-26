"""Time-decayed trending posts ranking using heapq in pure Python.

Formula (Plan Section 21.4):
  age_days = max(0.0, (now_utc - post.created_at).total_seconds() / 86400)
  engagement = likes_from_connections + 2 * comments_from_connections
  score = engagement / (1.0 + age_days)

Rank with heapq; stable tie-breakers are recency then post_id.
"""
import heapq
from datetime import datetime, timezone


def compute_trending_posts(
    posts: list[dict],
    likes_by_post: dict[int, set[int]],
    comments_by_post: dict[int, list[int]],
    viewer_connections: set[int],
    now_utc: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """Rank eligible posts by time-decayed connection engagement using heapq."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    heap: list[tuple] = []
    for post in posts:
        pid = post["id"]
        author_id = post["author_id"]
        created_at = post["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age_days = max(0.0, (now_utc - created_at).total_seconds() / 86400.0)
        if age_days > 7.0:
            continue

        # Count only interactions from viewer's accepted connections (excluding author)
        like_users = likes_by_post.get(pid, set())
        likes_from_conn = sum(
            1 for uid in like_users if uid in viewer_connections and uid != author_id
        )
        comment_authors = comments_by_post.get(pid, [])
        comments_from_conn = sum(
            1 for uid in comment_authors if uid in viewer_connections and uid != author_id
        )

        engagement = likes_from_conn + 2 * comments_from_conn
        if engagement <= 0:
            continue

        score = engagement / (1.0 + age_days)
        reason = (
            f"{likes_from_conn} like{'s' if likes_from_conn != 1 else ''} and "
            f"{comments_from_conn} comment{'s' if comments_from_conn != 1 else ''} "
            f"from your connections this week"
        )
        # Max-heap via negated score, negated timestamp, negated post_id
        heapq.heappush(
            heap,
            (
                -score,
                -created_at.timestamp(),
                -pid,
                {
                    **post,
                    "trending_score": round(score, 4),
                    "trending_reason": reason,
                },
            ),
        )

    results: list[dict] = []
    while heap and len(results) < limit:
        results.append(heapq.heappop(heap)[3])
    return results
