"""Unit tests for Trie prefix search."""
from backend.app.dsa.trie import Trie


def test_trie_insert_search_and_normalize():
    trie = Trie()
    trie.insert("Alice", 1)
    trie.insert("alicia", 2)
    trie.insert("Bob", 3)

    res = set(trie.search_prefix("AL", limit=10))
    assert res == {1, 2}
    assert trie.search_prefix("bo", limit=10) == [3]
    assert trie.search_prefix("zz", limit=10) == []


def test_trie_remove_and_rebuild():
    trie = Trie()
    trie.rebuild([("charlie", 10), ("charlotte", 11)])
    assert set(trie.search_prefix("char")) == {10, 11}

    trie.remove("charlie", 10)
    assert trie.search_prefix("char") == [11]
