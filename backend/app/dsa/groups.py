"""Closely-connected group discovery using graph density + skill Jaccard + heapq.

Formula (Plan Section 21.5):
  D = 2 * E(C) / (|C| * (|C| - 1))  where E(C) = edges inside member set C
  skill_jaccard = |S_u & S_C| / |S_u | S_C| (0.0 if union empty)
  community_score = 0.7 * D + 0.3 * skill_jaccard
Rank with heapq; break ties by group name ASC then group ID ASC.
"""
import heapq


def suggest_groups(
    adj: dict[int, set[int]],
    viewer_id: int,
    viewer_skills: set[str],
    groups: list[dict],
    member_skills_map: dict[int, set[str]],
    blocked_ids: set[int],
    inactive_ids: set[int],
    limit: int = 10,
) -> list[dict]:
    """Rank eligible campus-visible groups for viewer using heapq."""
    norm_viewer_skills = {s.strip().lower() for s in viewer_skills if s.strip()}
    heap: list[tuple] = []

    for g in groups:
        if g.get("visibility") != "campus":
            continue
        if g.get("membership_policy") == "invite":
            continue

        raw_members: set[int] = set(g.get("member_ids", set()))
        if viewer_id in raw_members:
            continue

        members = raw_members - blocked_ids - inactive_ids
        n = len(members)
        if n < 3:
            continue

        # Count undirected edges within C using adjacency list
        internal_edges_twice = 0
        for u in members:
            neighbors = adj.get(u, set())
            internal_edges_twice += len(neighbors & members)
        # Each edge counted twice (u->v and v->u); divide by n*(n-1) directly
        density = internal_edges_twice / (n * (n - 1))

        # Union of member skills
        group_skills: set[str] = set()
        for uid in members:
            for sk in member_skills_map.get(uid, set()):
                clean = sk.strip().lower()
                if clean:
                    group_skills.add(clean)

        union_skills = norm_viewer_skills | group_skills
        skill_jaccard = (
            len(norm_viewer_skills & group_skills) / len(union_skills)
            if union_skills
            else 0.0
        )

        score = 0.7 * density + 0.3 * skill_jaccard
        heapq.heappush(
            heap,
            (
                -score,
                g["name"].lower(),
                g["id"],
                {
                    "id": g["id"],
                    "name": g["name"],
                    "description": g["description"],
                    "visibility": g["visibility"],
                    "membership_policy": g["membership_policy"],
                    "member_count": n,
                    "score": round(score, 4),
                    "reason": "Shared skills and strong campus connections",
                },
            ),
        )

    results: list[dict] = []
    while heap and len(results) < limit:
        results.append(heapq.heappop(heap)[3])
    return results
