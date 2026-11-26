"""Unit tests for closely-connected group discovery."""
from backend.app.dsa.graph import build_adjacency_list
from backend.app.dsa.groups import suggest_groups


def test_suggest_groups_density_and_skill_jaccard():
    # Group 1 members {2, 3, 4} form a triangle (density = 1.0) + share Python
    # Group 2 members {5, 6, 7} have no edges (density = 0.0) + no shared skills
    adj = build_adjacency_list([1, 2, 3, 4, 5, 6, 7], [(2, 3), (3, 4), (2, 4)])
    groups = [
        {
            "id": 1,
            "name": "Algo Club",
            "description": "Graphs",
            "visibility": "campus",
            "membership_policy": "open",
            "member_ids": {2, 3, 4},
        },
        {
            "id": 2,
            "name": "Art Club",
            "description": "Sketching",
            "visibility": "campus",
            "membership_policy": "open",
            "member_ids": {5, 6, 7},
        },
        {
            "id": 3,
            "name": "Tiny Club",
            "description": "Too small",
            "visibility": "campus",
            "membership_policy": "open",
            "member_ids": {2, 3},
        },
    ]
    skills = {2: {"Python"}, 3: {"DSA"}, 4: set(), 5: {"Painting"}, 6: set(), 7: set()}

    recs = suggest_groups(
        adj=adj,
        viewer_id=1,
        viewer_skills={"Python"},
        groups=groups,
        member_skills_map=skills,
        blocked_ids=set(),
        inactive_ids=set(),
        limit=10,
    )
    assert [r["id"] for r in recs] == [1, 2]
    assert recs[0]["score"] > recs[1]["score"]
