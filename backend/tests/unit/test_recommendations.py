"""Unit tests for Jaccard people-you-may-know recommendations."""
from backend.app.dsa.graph import build_adjacency_list
from backend.app.dsa.recommendations import get_recommendations


def test_jaccard_recommendations_ranking_and_exclusions():
    # User 1 connected to 2, 3
    # User 4 connected to 2, 3 (2 mutual, J = 2/2 = 1.0)
    # User 5 connected to 2, 6 (1 mutual, J = 1/3 = 0.3333)
    # User 6 connected to 5 (0 mutual, 3-hop, not candidate)
    adj = build_adjacency_list(
        [1, 2, 3, 4, 5, 6],
        [(1, 2), (1, 3), (2, 4), (3, 4), (2, 5), (5, 6)],
    )
    recs = get_recommendations(
        adj=adj,
        user_id=1,
        pending_pairs=set(),
        blocked_ids=set(),
        inactive_ids=set(),
        username_map={1: "u1", 2: "u2", 3: "u3", 4: "u4", 5: "u5", 6: "u6"},
        limit=10,
    )
    assert [r["user_id"] for r in recs] == [4, 5]
    assert recs[0]["score"] == 1.0
    assert recs[0]["mutual_count"] == 2
    assert recs[1]["mutual_count"] == 1

    # Exclude pending
    recs_filtered = get_recommendations(
        adj=adj,
        user_id=1,
        pending_pairs={(1, 4)},
        blocked_ids=set(),
        inactive_ids=set(),
        username_map={1: "u1", 2: "u2", 3: "u3", 4: "u4", 5: "u5", 6: "u6"},
        limit=10,
    )
    assert [r["user_id"] for r in recs_filtered] == [5]
