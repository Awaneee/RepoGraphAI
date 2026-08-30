"""
tests/test_cache.py
====================
Tests for RepositoryCache — save/load roundtrip, fingerprint validation,
cache hit/miss behaviour.

All tests are self-contained (no real git clone or large parse step).
The graph fixture is minimal — just enough to exercise serialization.
"""

from __future__ import annotations

import json
import os
import pickle
import tempfile

import pytest

from app.cache.repository_cache import RepositoryCache, _sanitize_repo_key
from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_minimal_graph() -> RepositoryGraph:
    """A tiny RepositoryGraph with one node and one edge for roundtrip tests."""
    node_a = GraphNode(id="A", type=NodeType.CLASS, label="A")
    node_b = GraphNode(id="B", type=NodeType.METHOD, label="b")
    edge   = GraphEdge(
        source="A", target="B", relationship=RelationshipType.CONTAINS
    )
    return RepositoryGraph(nodes=[node_a, node_b], edges=[edge])


# ===========================================================================
# _sanitize_repo_key tests
# ===========================================================================

class TestSanitizeRepoKey:

    def test_key_includes_basename(self):
        key = _sanitize_repo_key("/some/path/myrepo")
        assert key.startswith("myrepo_")

    def test_key_includes_8_char_digest(self):
        key = _sanitize_repo_key("/some/path/myrepo")
        parts = key.split("_")
        assert len(parts[-1]) == 8

    def test_different_paths_produce_different_keys(self):
        key1 = _sanitize_repo_key("/path/a/repo")
        key2 = _sanitize_repo_key("/path/b/repo")
        assert key1 != key2

    def test_same_path_produces_same_key(self):
        key1 = _sanitize_repo_key("/some/path/myrepo")
        key2 = _sanitize_repo_key("/some/path/myrepo")
        assert key1 == key2

    def test_special_chars_sanitized(self):
        key = _sanitize_repo_key("/path/my repo!")
        # Key should only contain safe filesystem characters
        import re
        assert re.match(r"^[A-Za-z0-9_.\-]+$", key)


# ===========================================================================
# RepositoryCache — save / load roundtrip
# ===========================================================================

class TestRepositoryCache:

    @pytest.fixture
    def temp_repo_dir(self, tmp_path):
        """Create a temporary directory with one minimal Python file."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        (repo / "module.py").write_text("def hello(): pass\n")
        return str(repo)

    @pytest.fixture
    def cache(self, temp_repo_dir, tmp_path):
        cache_root = str(tmp_path / "cache")
        return RepositoryCache(temp_repo_dir, cache_root=cache_root)

    # --- Fingerprint ---

    def test_compute_fingerprint_returns_dict(self, cache):
        fp = cache.compute_fingerprint()
        assert isinstance(fp, dict)
        assert "digest" in fp
        assert "file_count" in fp

    def test_fingerprint_file_count_matches_py_files(self, cache, temp_repo_dir):
        fp = cache.compute_fingerprint()
        # Only module.py is tracked (test files are excluded by naming convention)
        assert fp["file_count"] == 1

    def test_fingerprint_is_deterministic(self, cache):
        fp1 = cache.compute_fingerprint()
        fp2 = cache.compute_fingerprint()
        assert fp1["digest"] == fp2["digest"]

    def test_fingerprint_changes_after_file_modification(self, cache, temp_repo_dir):
        fp1 = cache.compute_fingerprint()
        # Touch the file to change its mtime
        import time
        time.sleep(0.01)
        module_path = os.path.join(temp_repo_dir, "module.py")
        with open(module_path, "a") as f:
            f.write("# changed\n")
        fp2 = cache.compute_fingerprint()
        assert fp1["digest"] != fp2["digest"]

    # --- is_cache_valid ---

    def test_cache_invalid_when_no_files(self, cache):
        fp = cache.compute_fingerprint()
        result = cache.is_cache_valid(fp)
        assert not result.is_valid
        assert "no cached" in result.reason.lower()

    # --- save / load ---

    def test_save_creates_files(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        assert os.path.isfile(cache.hash_path)
        assert os.path.isfile(cache.graph_path)

    def test_load_after_save_roundtrip(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        loaded = cache.load()
        assert isinstance(loaded, RepositoryGraph)
        assert len(loaded.nodes) == len(graph.nodes)
        assert len(loaded.edges) == len(graph.edges)
        assert loaded.nodes[0].id == graph.nodes[0].id

    def test_cache_valid_after_save(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        result = cache.is_cache_valid(fp)
        assert result.is_valid

    def test_cache_invalid_after_file_change(self, cache, temp_repo_dir):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)

        # Modify a file
        import time
        time.sleep(0.01)
        module_path = os.path.join(temp_repo_dir, "module.py")
        with open(module_path, "a") as f:
            f.write("# invalidate\n")

        new_fp = cache.compute_fingerprint()
        result = cache.is_cache_valid(new_fp)
        assert not result.is_valid
        assert "fingerprint changed" in result.reason.lower()

    def test_cache_invalid_when_hash_file_deleted(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        os.remove(cache.hash_path)
        result = cache.is_cache_valid(fp)
        assert not result.is_valid

    def test_cache_invalid_when_graph_file_deleted(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        os.remove(cache.graph_path)
        result = cache.is_cache_valid(fp)
        assert not result.is_valid

    def test_clear_removes_files(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        cache.clear()
        assert not os.path.isfile(cache.hash_path)
        assert not os.path.isfile(cache.graph_path)

    def test_clear_is_idempotent(self, cache):
        """clear() should not raise if files don't exist."""
        cache.clear()  # No files exist yet
        cache.clear()  # Should not raise

    # --- Graph content preservation ---

    def test_node_types_preserved(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        loaded = cache.load()
        original_types = {n.id: n.type for n in graph.nodes}
        loaded_types = {n.id: n.type for n in loaded.nodes}
        assert original_types == loaded_types

    def test_edge_relationships_preserved(self, cache):
        graph = _make_minimal_graph()
        fp = cache.compute_fingerprint()
        cache.save(graph, fp)
        loaded = cache.load()
        original_rels = [(e.source, e.target, e.relationship) for e in graph.edges]
        loaded_rels = [(e.source, e.target, e.relationship) for e in loaded.edges]
        assert original_rels == loaded_rels

    # --- Cache miss behaviour ---

    def test_cache_miss_returns_false(self, tmp_path):
        """A cache with no saved data reports a miss."""
        repo = tmp_path / "emptyrepo"
        repo.mkdir()
        (repo / "a.py").write_text("x = 1\n")
        cache_root = str(tmp_path / "cache")
        cache = RepositoryCache(str(repo), cache_root=cache_root)
        fp = cache.compute_fingerprint()
        result = cache.is_cache_valid(fp)
        assert not result.is_valid

    def test_multiple_repos_independent_caches(self, tmp_path):
        """Two different repos have independent cache entries."""
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir(); repo_b.mkdir()
        (repo_a / "a.py").write_text("a = 1\n")
        (repo_b / "b.py").write_text("b = 2\n")

        cache_root = str(tmp_path / "cache")
        cache_a = RepositoryCache(str(repo_a), cache_root=cache_root)
        cache_b = RepositoryCache(str(repo_b), cache_root=cache_root)

        graph = _make_minimal_graph()
        cache_a.save(graph, cache_a.compute_fingerprint())

        # cache_b should still be a miss
        result_b = cache_b.is_cache_valid(cache_b.compute_fingerprint())
        assert not result_b.is_valid

        # cache_a should be a hit
        result_a = cache_a.is_cache_valid(cache_a.compute_fingerprint())
        assert result_a.is_valid
