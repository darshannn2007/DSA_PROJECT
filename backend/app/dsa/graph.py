"""Social network graph using adjacency lists.

Representation: adj: dict[int, set[int]]
For every accepted edge (u, v): v in adj[u] and u in adj[v].
Space: O(V + E). Neighbor lookup: O(1) average.
"""
from collections import deque
from typing import Optional


def build_adjacency_list(user_ids: list[int], edges: list[tuple[int, int]]) -> dict[int, set[int]]:
    """Build adjacency list from user IDs and accepted edges.
    Every registered user has an entry (including isolated users).
    Each undirected edge (u,v) stored in both directions.
    Time: O(V + E). Space: O(V + E).
    """
    adj: dict[int, set[int]] = {uid: set() for uid in user_ids}
    for u, v in edges:
        if u in adj and v in adj and u != v:
            adj[u].add(v)
            adj[v].add(u)
    return adj


def build_ordered_adjacency(adj: dict[int, set[int]]) -> dict[int, tuple[int, ...]]:
    """Build deterministic sorted-neighbor adjacency for BFS.
    One-time sort cost: O(V * max_degree * log(max_degree)).
    """
    return {uid: tuple(sorted(neighbors)) for uid, neighbors in adj.items()}


def shortest_path(ordered_adj: dict[int, tuple[int, ...]], start: int, target: int) -> Optional[list[int]]:
    """BFS shortest path in unweighted graph.
    Returns list of user IDs from start to target, or None if unreachable.
    Same user returns [start]. Invalid IDs return None.
    Time: O(V + E). Space: O(V).
    """
    if start not in ordered_adj or target not in ordered_adj:
        return None
    if start == target:
        return [start]
    queue = deque([start])
    parent: dict[int, Optional[int]] = {start: None}
    while queue:
        current = queue.popleft()
        for neighbor in ordered_adj.get(current, ()):
            if neighbor in parent:
                continue
            parent[neighbor] = current
            if neighbor == target:
                path: list[int] = []
                node: Optional[int] = target
                while node is not None:
                    path.append(node)
                    node = parent[node]
                return list(reversed(path))
            queue.append(neighbor)
    return None


def hop_count(path: Optional[list[int]]) -> Optional[int]:
    """Number of edges in path. None if no path."""
    if path is None:
        return None
    return len(path) - 1


def degree_label(hops: Optional[int]) -> str:
    """Human label for connection degree."""
    if hops is None:
        return "Not connected"
    if hops == 0:
        return "Self"
    if hops == 1:
        return "1st degree"
    if hops == 2:
        return "2nd degree"
    if hops == 3:
        return "3rd degree"
    return f"{hops}th degree"


def mutual_connections(adj: dict[int, set[int]], u: int, v: int) -> set[int]:
    """Set intersection of neighbors. O(min(deg(u), deg(v))) expected."""
    if u not in adj or v not in adj:
        return set()
    return adj[u] & adj[v]


def vertex_degree(adj: dict[int, set[int]], user_id: int) -> int:
    """Number of direct connections (graph-theoretic degree)."""
    return len(adj.get(user_id, set()))
