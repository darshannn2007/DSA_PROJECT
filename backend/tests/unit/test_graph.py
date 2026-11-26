"""Unit tests for social graph and BFS algorithms."""
from backend.app.dsa.graph import (
    build_adjacency_list,
    build_ordered_adjacency,
    degree_label,
    hop_count,
    mutual_connections,
    shortest_path,
    vertex_degree,
)


def test_build_adjacency_list_includes_isolated_users():
    adj = build_adjacency_list([1, 2, 3], [(1, 2)])
    assert adj == {1: {2}, 2: {1}, 3: set()}


def test_shortest_path_and_degrees():
    adj = build_adjacency_list([1, 2, 3, 4, 5], [(1, 2), (2, 3), (3, 4)])
    ordered = build_ordered_adjacency(adj)

    assert shortest_path(ordered, 1, 1) == [1]
    assert hop_count([1]) == 0
    assert degree_label(0) == "Self"

    p14 = shortest_path(ordered, 1, 4)
    assert p14 == [1, 2, 3, 4]
    assert hop_count(p14) == 3
    assert degree_label(3) == "3rd degree"

    assert shortest_path(ordered, 1, 5) is None
    assert degree_label(None) == "Not connected"


def test_mutual_connections_and_vertex_degree():
    adj = build_adjacency_list([1, 2, 3, 4], [(1, 2), (1, 3), (2, 4), (3, 4)])
    assert mutual_connections(adj, 1, 4) == {2, 3}
    assert vertex_degree(adj, 1) == 2
    assert vertex_degree(adj, 99) == 0
