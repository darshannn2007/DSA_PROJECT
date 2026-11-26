"""Unit tests for time-decayed trending posts ranking."""
from datetime import datetime, timedelta, timezone
from backend.app.dsa.trending import compute_trending_posts


def test_trending_posts_formula_and_filtering():
    now = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)
    posts = [
        {"id": 1, "author_id": 2, "body": "old", "created_at": now - timedelta(days=10)},
        {"id": 2, "author_id": 2, "body": "liked", "created_at": now - timedelta(days=1)},
        {"id": 3, "author_id": 2, "body": "commented", "created_at": now - timedelta(hours=1)},
    ]
    likes = {2: {3, 4}, 3: set()}          # post 2: 2 likes -> engagement 2, age 1 -> score 1.0
    comments = {2: [], 3: [3, 4]}          # post 3: 2 comments -> engagement 4, age ~0.04 -> score ~3.84
    viewer_conns = {2, 3, 4}

    ranked = compute_trending_posts(
        posts=posts,
        likes_by_post=likes,
        comments_by_post=comments,
        viewer_connections=viewer_conns,
        now_utc=now,
        limit=10,
    )
    assert [p["id"] for p in ranked] == [3, 2]
    assert ranked[0]["trending_score"] > ranked[1]["trending_score"]
    assert "from your connections this week" in ranked[0]["trending_reason"]
