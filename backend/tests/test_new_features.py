"""
tests/test_new_features.py
===========================
Tests for features added in the second engineering pass:
  - PersistentJobStore (SQLite)
  - TypeScriptParser (tree-sitter)
  - Token counting / context trimming
  - Health endpoint fields
  - Structured logging (middleware)
"""
from __future__ import annotations

import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


# ===========================================================================
# PersistentJobStore
# ===========================================================================

class TestPersistentJobStore:

    def _make_store(self, tmp_path):
        from app.cache.job_store import PersistentJobStore
        db = os.path.join(tmp_path, "jobs.db")
        return PersistentJobStore(db_path=db, ttl_days=1)

    def _dummy_request(self):
        """Return a plain dict as a fake QARequest."""
        class R:
            def model_dump(self):
                return {"repo_url": "https://github.com/psf/requests", "question": "What?", "top_k": 5, "max_hops": 1}
        return R()

    def test_create_returns_job(self, tmp_path):
        store = self._make_store(tmp_path)
        job   = store.create(self._dummy_request())
        assert job.id
        assert job.status == "queued"

    def test_get_returns_same_job(self, tmp_path):
        store = self._make_store(tmp_path)
        job   = store.create(self._dummy_request())
        fetched = store.get(job.id)
        assert fetched is not None
        assert fetched.id == job.id

    def test_get_unknown_returns_none(self, tmp_path):
        store = self._make_store(tmp_path)
        assert store.get("nonexistent-id") is None

    def test_update_status(self, tmp_path):
        store = self._make_store(tmp_path)
        job   = store.create(self._dummy_request())
        store.update(job.id, status="running")
        updated = store.get(job.id)
        assert updated.status == "running"

    def test_update_error(self, tmp_path):
        store = self._make_store(tmp_path)
        job   = store.create(self._dummy_request())
        store.update(job.id, status="error", error="something went wrong")
        updated = store.get(job.id)
        assert updated.status == "error"
        assert "something" in (updated.error or "")

    def test_persists_across_instances(self, tmp_path):
        """A job created by one store instance is visible to another."""
        from app.cache.job_store import PersistentJobStore
        db = os.path.join(tmp_path, "persist.db")
        store1 = PersistentJobStore(db_path=db)
        job    = store1.create(self._dummy_request())
        store2 = PersistentJobStore(db_path=db)
        fetched = store2.get(job.id)
        assert fetched is not None
        assert fetched.id == job.id

    def test_cleanup_expired(self, tmp_path):
        """Jobs older than TTL are deleted."""
        from app.cache.job_store import PersistentJobStore
        import sqlite3
        from datetime import datetime, timezone, timedelta

        db = os.path.join(tmp_path, "ttl.db")
        store = PersistentJobStore(db_path=db, ttl_days=1)
        job = store.create(self._dummy_request())

        # Manually backdate the job's created_at to 10 days ago
        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        conn = sqlite3.connect(db)
        conn.execute("UPDATE jobs SET created_at = ? WHERE id = ?", (old_date, job.id))
        conn.commit()
        conn.close()

        deleted = store.cleanup_expired()
        assert deleted >= 1
        assert store.get(job.id) is None


# ===========================================================================
# TypeScript Parser
# ===========================================================================

class TestTypeScriptParser:

    def test_is_available(self):
        from app.parsers.typescript_parser import is_available
        # Just check it returns a bool — actual availability depends on install
        assert isinstance(is_available(), bool)

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("tree_sitter_typescript"),
        reason="tree-sitter-typescript not installed"
    )
    def test_parse_simple_ts_file(self):
        from app.parsers.typescript_parser import TypeScriptParser
        src = b"""
import { readFile } from "fs";
import axios from "axios";

class UserService {
  getUser(id: string): string {
    return fetchData(id);
  }
}

function fetchData(id: string): string {
  return axios.get(id);
}
"""
        with tempfile.NamedTemporaryFile(suffix=".ts", delete=False, mode="wb") as f:
            f.write(src)
            fname = f.name
        try:
            parser = TypeScriptParser()
            result = parser.parse_file(fname)
            assert result.file_path == fname
            assert "fs" in result.imports or "axios" in result.imports
            assert any(c.name == "UserService" for c in result.classes)
            assert any(f.name == "fetchData" for f in result.functions)
        finally:
            os.unlink(fname)

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("tree_sitter_typescript"),
        reason="tree-sitter-typescript not installed"
    )
    def test_parse_repository_returns_parsed_repo(self):
        from app.parsers.typescript_parser import TypeScriptParser
        with tempfile.TemporaryDirectory() as tmpdir:
            ts_file = os.path.join(tmpdir, "app.ts")
            with open(ts_file, "w") as f:
                f.write("export class Foo { bar(): void {} }\n")
            parser = TypeScriptParser()
            repo   = parser.parse_repository(tmpdir)
            assert repo.repository_name == os.path.basename(tmpdir)
            assert repo.total_python_files >= 1
            assert any(
                any(c.name == "Foo" for c in pf.classes)
                for pf in repo.files
            )


# ===========================================================================
# Token counting and trimming
# ===========================================================================

class TestTokenUtils:

    def test_count_tokens_empty(self):
        from app.core.token_utils import count_tokens
        assert count_tokens("") == 0

    def test_count_tokens_positive(self):
        from app.core.token_utils import count_tokens
        assert count_tokens("Hello world") > 0

    def test_count_tokens_longer_text_is_more(self):
        from app.core.token_utils import count_tokens
        short = count_tokens("Hi")
        long  = count_tokens("Hello world this is a longer sentence with many tokens")
        assert long > short

    def test_trim_short_text_unchanged(self):
        from app.core.token_utils import trim_to_token_limit
        text = "Hello world"
        result = trim_to_token_limit(text, max_tokens=1000)
        assert result == text

    def test_trim_long_text_within_limit(self):
        from app.core.token_utils import trim_to_token_limit, count_tokens
        text   = "word " * 5000  # ~5000 tokens
        result = trim_to_token_limit(text, max_tokens=100)
        assert count_tokens(result) <= 100

    def test_trim_adds_marker(self):
        from app.core.token_utils import trim_to_token_limit
        text   = "word " * 5000
        result = trim_to_token_limit(text, max_tokens=50)
        assert "trimmed" in result.lower()

    def test_trim_preserves_beginning(self):
        from app.core.token_utils import trim_to_token_limit
        text   = "START " + "filler " * 5000
        result = trim_to_token_limit(text, max_tokens=20)
        assert result.startswith("START")


# ===========================================================================
# Health endpoint
# ===========================================================================

class TestHealthEndpoint:

    def test_health_returns_200(self):
        from app.main import app
        with TestClient(app) as c:
            r = c.get("/health")
        assert r.status_code == 200

    def test_health_has_expected_fields(self):
        from app.main import app
        with TestClient(app) as c:
            data = c.get("/health").json()
        assert "status" in data
        assert "cache_dir_writable" in data
        assert "repos_dir_writable" in data
        assert "llm_configured" in data
        assert "embedding_available" in data

    def test_health_status_is_string(self):
        from app.main import app
        with TestClient(app) as c:
            data = c.get("/health").json()
        assert data["status"] in ("ok", "degraded")

    def test_health_booleans_are_bool(self):
        from app.main import app
        with TestClient(app) as c:
            data = c.get("/health").json()
        for key in ("cache_dir_writable", "repos_dir_writable", "llm_configured", "embedding_available"):
            assert isinstance(data[key], bool), f"{key} should be bool"
