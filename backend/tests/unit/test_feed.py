"""Unit tests for heapq k-way feed merge."""
from datetime import datetime, timedelta, timezone
from backend.app.dsa.feed import FeedMerger


def test_merge_feeds_newest_first_and_cursor():
    t0 = datetime(2026, 11, 25, 12, 0, 0, tzinfo=timezone.utc)
    streams = {
        1: [
            {"id": 3, "author_id": 1, "body": "a3", "created_at": t0 + timedelta(minutes=3)},
            {"id": 1, "author_id": 1, "body": "a1", "created_at": t0 + timedelta(minutes=1)},
        ],
        2: [
            {"id": 4, "author_id": 2, "body": "b4", "created_at": t0 + timedelta(minutes=4)},
            {"id": 2, "author_id": 2, "body": "b2", "created_at": t0 + timedelta(minutes=2)},
        ],
    }

    page1 = FeedMerger.merge_feeds(streams, limit=2)
    assert [p["id"] for p in page1] == [4, 3]

    cursor = FeedMerger.make_cursor(page1[-1])
    parsed = FeedMerger.parse_cursor(cursor)
    assert parsed is not None

    page2 = FeedMerger.merge_feeds(streams, limit=2, after_cursor=parsed)
    assert [p["id"] for p in page2] == [2, 1]
