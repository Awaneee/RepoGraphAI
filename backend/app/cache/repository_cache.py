"""
app/cache/repository_cache.py
==============================
Repository graph caching.

Avoids re-parsing a repository and rebuilding its knowledge graph when
the repository has not changed since the last run.

Cache validity is decided by a lightweight repository *fingerprint*
based only on:

  - Python file names (relative path within the repository)
  - modification timestamps
  - file sizes

File contents are never read or hashed for fingerprinting purposes.

Layout
------
.cache/
    <repo_key>/
        repository_hash.json     # fingerprint of the last cached build
        repository_graph.pkl     # pickled RepositoryGraph

``<repo_key>`` namespaces the cache per repository (derived from the
repository's absolute path) so multiple repositories — e.g. the ones
used by ``tests/cross_repo_benchmark.py`` — can each have their own
independent cache underneath a single top-level ``.cache/`` directory.

This module only reads from / writes to disk and never touches
retrieval logic (``QueryResolver``, ``RepositoryRetriever``,
``ContextBuilder``, ``GraphRAGEngine``) or mutates ``RepositoryGraph``.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
from dataclasses import dataclass
from typing import Optional

from app.models.pydantic_models import RepositoryGraph

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CACHE_ROOT_DIRNAME = ".cache"
_HASH_FILENAME = "repository_hash.json"
_GRAPH_FILENAME = "repository_graph.pkl"

# Mirrors CodeParser's directory-skip set and test-file filtering
# (app/parsers/code_parser.py) so the fingerprint tracks exactly the
# files that influence the parsed graph. Duplicated here rather than
# imported to keep this module decoupled from CodeParser's internals.
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", ".venv", "venv", "env",
    "node_modules", "dist", "build",
    "docs", "docs_src",
    "examples", "example",
    "tests", "test",
    ".github", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    _CACHE_ROOT_DIRNAME,  # never fingerprint our own cache directory
})


def _is_tracked_python_file(filename: str) -> bool:
    if not filename.endswith(".py"):
        return False
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return False
    return True


def _sanitize_repo_key(repository_path: str) -> str:
    """
    Build a filesystem-safe, collision-resistant cache key for a
    repository path, e.g. "app_3f9a1c2b" or "fastapi_7b21ee04".
    """
    abs_path = os.path.abspath(repository_path)
    name = os.path.basename(abs_path.rstrip("/\\")) or "repository"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    digest = hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:8]
    return f"{safe_name}_{digest}"


@dataclass(frozen=True)
class CacheValidationResult:
    """Result of checking whether a cached graph can be reused."""

    is_valid: bool
    reason: str


# ---------------------------------------------------------------------------
# RepositoryCache
# ---------------------------------------------------------------------------

class RepositoryCache:
    """
    Computes repository fingerprints and saves/loads a parsed
    ``RepositoryGraph`` to/from disk so unchanged repositories don't
    need to be re-parsed and re-built on every run.

    Usage
    -----
        cache = RepositoryCache(repository_path)
        fingerprint = cache.compute_fingerprint()

        if cache.is_cache_valid(fingerprint).is_valid:
            graph = cache.load()
        else:
            graph = GraphBuilder().build_graph(parsed_repository)
            cache.save(graph, fingerprint)
    """

    def __init__(self, repository_path: str, cache_root: str = _CACHE_ROOT_DIRNAME) -> None:
        self.repository_path = repository_path
        self.cache_root = cache_root
        self._repo_key = _sanitize_repo_key(repository_path)
        self._cache_dir = os.path.join(self.cache_root, self._repo_key)

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    @property
    def cache_dir(self) -> str:
        return self._cache_dir

    @property
    def hash_path(self) -> str:
        return os.path.join(self._cache_dir, _HASH_FILENAME)

    @property
    def graph_path(self) -> str:
        return os.path.join(self._cache_dir, _GRAPH_FILENAME)

    # ------------------------------------------------------------------
    # Fingerprint
    # ------------------------------------------------------------------

    def compute_fingerprint(self) -> dict:
        """
        Build a fingerprint of the repository based solely on Python
        file names, modification timestamps, and sizes.

        File contents are never read or hashed.
        """
        entries: list[dict] = []

        for root, dirs, files in os.walk(self.repository_path, topdown=True):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

            for filename in files:
                if not _is_tracked_python_file(filename):
                    continue

                file_path = os.path.join(root, filename)

                try:
                    stat_result = os.stat(file_path)
                except OSError:
                    continue

                rel_path = os.path.relpath(file_path, self.repository_path)

                entries.append({
                    "path": rel_path.replace(os.sep, "/"),
                    "mtime": stat_result.st_mtime,
                    "size": stat_result.st_size,
                })

        entries.sort(key=lambda entry: entry["path"])

        canonical = json.dumps(entries, sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        return {
            "repository_path": os.path.abspath(self.repository_path),
            "file_count": len(entries),
            "digest": digest,
            "entries": entries,
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def is_cache_valid(self, fingerprint: Optional[dict] = None) -> CacheValidationResult:
        """
        Check whether a previously cached graph is still valid for the
        current state of the repository.
        """
        if fingerprint is None:
            fingerprint = self.compute_fingerprint()

        if not os.path.isfile(self.hash_path):
            return CacheValidationResult(False, "no cached fingerprint found")

        if not os.path.isfile(self.graph_path):
            return CacheValidationResult(False, "no cached graph found")

        try:
            with open(self.hash_path, "r", encoding="utf-8") as fh:
                cached_fingerprint = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return CacheValidationResult(False, "cached fingerprint unreadable")

        if cached_fingerprint.get("digest") != fingerprint.get("digest"):
            return CacheValidationResult(False, "repository fingerprint changed")

        return CacheValidationResult(True, "fingerprint matches cached graph")

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self, graph: RepositoryGraph, fingerprint: Optional[dict] = None) -> None:
        """Persist the parsed graph and its fingerprint to disk."""
        if fingerprint is None:
            fingerprint = self.compute_fingerprint()

        os.makedirs(self._cache_dir, exist_ok=True)

        with open(self.graph_path, "wb") as fh:
            pickle.dump(graph, fh, protocol=pickle.HIGHEST_PROTOCOL)

        with open(self.hash_path, "w", encoding="utf-8") as fh:
            json.dump(fingerprint, fh, indent=2)

    def load(self) -> RepositoryGraph:
        """Load the cached graph from disk. Caller should validate first."""
        with open(self.graph_path, "rb") as fh:
            return pickle.load(fh)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove this repository's cached fingerprint and graph, if any."""
        for path in (self.hash_path, self.graph_path):
            try:
                os.remove(path)
            except OSError:
                pass
