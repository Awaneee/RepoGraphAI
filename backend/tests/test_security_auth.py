"""
tests/test_security_auth.py
=============================
Tests for API key authentication and rate limiting.
"""
from __future__ import annotations

import os
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.api.endpoints import get_repository_service, get_graph_service
from app.models.pydantic_models import (
    GraphEdge, GraphNode, NodeType, RelationshipType,
    RepositoryGraph, RepositorySummary,
)


# ---------------------------------------------------------------------------
# Fakes (same as test_api.py)
# ---------------------------------------------------------------------------

class FakeRepositoryService:
    def clone_repository(self, url: str) -> str:
        from app.services.repository_service import validate_clone_url
        validate_clone_url(url)
        return "/fake/repos/requests"

    def generate_summary(self, repo_path: str) -> RepositorySummary:
        return RepositorySummary(
            repository_name="requests", repository_path=repo_path,
            repository_type="General Software Project", framework=None,
            total_files=10, total_directories=2, repository_size_bytes=50_000,
            language_distribution={"Python": 10},
            file_extension_distribution={".py": 10},
            file_category_distribution={"source_code": 10},
            top_level_directories=["src"], largest_files=[],
        )


def _minimal_graph() -> RepositoryGraph:
    n = GraphNode(id="A", type=NodeType.CLASS, label="A")
    e = GraphEdge(source="A", target="A", relationship=RelationshipType.CONTAINS)
    return RepositoryGraph(nodes=[n], edges=[e])


class FakeGraphService:
    def generate_graph(self, repo_path: str) -> RepositoryGraph:
        return _minimal_graph()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client_no_auth():
    """TestClient with no API key configured — open access."""
    app.dependency_overrides[get_repository_service] = lambda: FakeRepositoryService()
    app.dependency_overrides[get_graph_service] = lambda: FakeGraphService()
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "", "GOOGLE_API_KEY": "", "API_KEY": ""
    }):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_auth():
    """TestClient with API_KEY=test-secret-key configured."""
    app.dependency_overrides[get_repository_service] = lambda: FakeRepositoryService()
    app.dependency_overrides[get_graph_service] = lambda: FakeGraphService()
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "", "GOOGLE_API_KEY": "", "API_KEY": "test-secret-key"
    }):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# API key auth tests
# ---------------------------------------------------------------------------

class TestApiKeyAuthentication:

    def test_no_key_configured_allows_all_requests(self, client_no_auth):
        """When API_KEY is not set, all requests are accepted."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", None):
            resp = client_no_auth.post("/qa", json={
                "repo_url": "https://github.com/psf/requests",
                "question": "What is A?",
            })
            assert resp.status_code == 200

    def test_correct_key_allows_request(self, client_with_auth):
        """Correct X-API-Key header is accepted."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/qa",
                json={"repo_url": "https://github.com/psf/requests", "question": "What is A?"},
                headers={"X-API-Key": "test-secret-key"},
            )
            assert resp.status_code == 200

    def test_missing_key_returns_401(self, client_with_auth):
        """Missing X-API-Key header returns 401 when key is required."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/qa",
                json={"repo_url": "https://github.com/psf/requests", "question": "What is A?"},
            )
            assert resp.status_code == 401

    def test_wrong_key_returns_401(self, client_with_auth):
        """Wrong X-API-Key returns 401."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/qa",
                json={"repo_url": "https://github.com/psf/requests", "question": "What is A?"},
                headers={"X-API-Key": "wrong-key"},
            )
            assert resp.status_code == 401

    def test_auth_not_required_for_analyze(self, client_with_auth):
        """/analyze does not require API key."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/analyze",
                json={"repo_url": "https://github.com/psf/requests"},
            )
            assert resp.status_code == 200

    def test_auth_not_required_for_graph(self, client_with_auth):
        """/graph does not require API key."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/graph",
                json={"repo_url": "https://github.com/psf/requests"},
            )
            assert resp.status_code == 200

    def test_qa_async_requires_key(self, client_with_auth):
        """/qa/async also enforces API key."""
        from app.core import security
        with patch.object(security.settings, "API_KEY", "test-secret-key"):
            resp = client_with_auth.post(
                "/qa/async",
                json={"repo_url": "https://github.com/psf/requests", "question": "What?"},
            )
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiter unit tests (no HTTP)
# ---------------------------------------------------------------------------

class TestSlidingWindowLimiter:

    def _make_limiter(self, max_req=3, window=60):
        from app.core.security import _SlidingWindowLimiter
        return _SlidingWindowLimiter(max_requests=max_req, window_seconds=window)

    def test_allows_requests_within_limit(self):
        limiter = self._make_limiter(max_req=3)
        for _ in range(3):
            allowed, _ = limiter.check("client1")
            assert allowed

    def test_rejects_request_over_limit(self):
        limiter = self._make_limiter(max_req=3)
        for _ in range(3):
            limiter.check("client1")
        allowed, retry = limiter.check("client1")
        assert not allowed
        assert retry > 0

    def test_different_clients_are_independent(self):
        limiter = self._make_limiter(max_req=2)
        for _ in range(2):
            limiter.check("client1")
        # client1 is at limit; client2 should still be allowed
        allowed, _ = limiter.check("client2")
        assert allowed

    def test_window_expiry_allows_new_requests(self):
        """After the window expires, a previously-limited client can request again."""
        limiter = self._make_limiter(max_req=2, window=1)  # 1-second window
        for _ in range(2):
            limiter.check("client-expiry")
        allowed_before, _ = limiter.check("client-expiry")
        assert not allowed_before

        time.sleep(1.1)  # wait for window to expire

        allowed_after, _ = limiter.check("client-expiry")
        assert allowed_after

    def test_returns_retry_after_when_limited(self):
        limiter = self._make_limiter(max_req=1, window=10)
        limiter.check("c")
        allowed, retry = limiter.check("c")
        assert not allowed
        assert 1 <= retry <= 11

    def test_thread_safety(self):
        """Concurrent requests from the same IP must not corrupt internal state."""
        import threading
        limiter = self._make_limiter(max_req=50, window=60)
        results = []
        lock = threading.Lock()

        def make_request():
            allowed, _ = limiter.check("shared-client")
            with lock:
                results.append(allowed)

        threads = [threading.Thread(target=make_request) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 50 should be allowed
        assert sum(results) == 50


# ---------------------------------------------------------------------------
# Rate limit HTTP integration test
# ---------------------------------------------------------------------------

class TestRateLimitingEndpoint:

    def test_rate_limit_returns_429_after_limit(self, client_no_auth):
        """Sending many requests quickly should eventually return 429."""
        from app.core import security

        # Use a very tight limit so the test is fast
        with patch.object(security._qa_limiter, "_max", 2):
            # Reset the client's entry first
            with security._qa_limiter._lock:
                security._qa_limiter._store.pop("testclient", None)

            responses = []
            for _ in range(4):
                resp = client_no_auth.post("/qa", json={
                    "repo_url": "https://github.com/psf/requests",
                    "question": "What is A?",
                })
                responses.append(resp.status_code)

            # At least one 429 should appear
            assert 429 in responses
