"""People-you-may-know recommendations using Jaccard similarity, same course, and shared skills.

For candidate v and user u:
  J(u,v) = |N(u) intersection N(v)| / |N(u) union N(v)|
Also considers campus peers with the same programme/course or shared skills.
Rank by: descending combined score, descending mutual count, ascending username, ascending user_id.
"""


def get_recommendations(
    adj: dict[int, set[int]],
    user_id: int,
    pending_pairs: set[tuple[int, int]],
    blocked_ids: set[int],
    inactive_ids: set[int],
    username_map: dict[int, str],
    limit: int = 10,
    programme_map: dict[int, str] | None = None,
    skills_map: dict[int, set[str]] | None = None,
) -> list[dict]:
    """Return ranked people-you-may-know suggestions.
    1. Discover two-hop candidates from user's neighbors' neighbors, plus
       same-programme or shared-skill campus peers.
    2. Exclude: self, existing connections, pending requests (either dir),
       blocked users, inactive users.
    3. Rank by Jaccard similarity + course/skill affinity with stable tie-breaking.
    """
    if user_id not in adj:
        return []
    neighbors = adj[user_id]
    candidates: set[int] = set()
    for neighbor in neighbors:
        for two_hop in adj.get(neighbor, set()):
            candidates.add(two_hop)

    my_prog = (programme_map or {}).get(user_id, "").strip().lower()
    my_skills = {s.strip().lower() for s in (skills_map or {}).get(user_id, set()) if s.strip()}

    # Include same-programme or shared-skill peers as candidates
    for uid in adj:
        if uid == user_id:
            continue
        other_prog = (programme_map or {}).get(uid, "").strip().lower()
        other_skills = {s.strip().lower() for s in (skills_map or {}).get(uid, set()) if s.strip()}
        if (my_prog and other_prog and my_prog == other_prog) or (my_skills & other_skills):
            candidates.add(uid)

    candidates.discard(user_id)
    candidates -= neighbors
    candidates -= blocked_ids
    candidates -= inactive_ids
    candidates = {
        c for c in candidates
        if (user_id, c) not in pending_pairs and (c, user_id) not in pending_pairs
    }

    scored = []
    user_neighbors = adj[user_id]
    for candidate in candidates:
        candidate_neighbors = adj.get(candidate, set())
        intersection = user_neighbors & candidate_neighbors
        union = user_neighbors | candidate_neighbors
        mutual_count = len(intersection)
        jaccard = len(intersection) / len(union) if union else 0.0

        other_prog_raw = (programme_map or {}).get(candidate, "").strip()
        same_course = bool(my_prog and other_prog_raw and my_prog == other_prog_raw.lower())
        other_skills = {s.strip().lower() for s in (skills_map or {}).get(candidate, set()) if s.strip()}
        shared_skills = len(my_skills & other_skills)

        # Combined affinity score: Jaccard primary, course & skills secondary
        combined_score = jaccard + (0.15 if same_course else 0.0) + (0.05 * min(shared_skills, 3))

        reasons: list[str] = []
        if mutual_count > 0:
            reasons.append(f"{mutual_count} mutual connection{'s' if mutual_count != 1 else ''}")
        if same_course:
            reasons.append(f"Same course ({other_prog_raw})")
        if shared_skills > 0:
            reasons.append(f"{shared_skills} shared skill{'s' if shared_skills != 1 else ''}")
        if not reasons:
            reasons.append("Campus peer")

        username = username_map.get(candidate, "")
        scored.append((
            -combined_score,
            -mutual_count,
            username.lower(),
            candidate,
            {
                "user_id": candidate,
                "score": round(combined_score, 4),
                "mutual_count": mutual_count,
                "reason": " · ".join(reasons),
            },
        ))
    scored.sort()
    return [item[4] for item in scored[:limit]]
