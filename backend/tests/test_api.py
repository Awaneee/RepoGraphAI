"""
tests/test_api.py
==================
TestClient integration tests for /analyze, /graph, and /qa endpoints.

These tests use FastAPI dependency injection overrides to replace
RepositoryService and GraphService with controlled doubles — no real
git clones are performed.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.api.endpoints import get_repository_service, get_graph_service
from app.models.pydantic_models import (
    GraphEdge,
    GraphNode,
    NodeType,
    RelationshipType,
    RepositoryGraph,
    RepositorySummary,
)


# ===========================================================================
# Service fakes
# ===========================================================================

class FakeRepositoryService:
    """
    Stub RepositoryService that never touches the filesystem or network.
    """

    def clone_repository(self, repo_url: str) -> str:
        # Reject bad URLs so /analyze and /graph error tests work
        from app.services.repository_service import validate_clone_url
        validate_clone_url(repo_url)
        return f"/fake/repos/{repo_url.split('/')[-1]}"

    def generate_summary(self, repo_path: str) -> RepositorySummary:
        return RepositorySummary(
            repository_name="fake-repo",
            repository_path=repo_path,
            repository_type="Backend API",
            framework="FastAPI",
            total_files=42,
            total_directories=7,
            repository_size_bytes=1_234_567,
            language_distribution={"Python": 40, "Markdown": 2},
            file_extension_distribution={".py": 40, ".md": 2},
            file_category_distribution={"source_code": 40, "documentation": 2},
            top_level_directories=["app", "tests"],
            largest_files=[],
        )


def _make_minimal_graph() -> RepositoryGraph:
    node_a = GraphNode(id="MyClass", type=NodeType.CLASS, label="MyClass")
    node_b = GraphNode(
        id="MyClass.process",
        type=NodeType.METHOD,
        label="process",
        docstring="Process something.",
    )
    node_f = GraphNode(
        id="fake_file.py",
        type=NodeType.FILE,
        label="fake_file.py",
    )
    edge1 = GraphEdge(source="fake_file.py", target="MyClass",
                      relationship=RelationshipType.CONTAINS)
    edge2 = GraphEdge(source="MyClass", target="MyClass.process",
                      relationship=RelationshipType.CONTAINS)
    return RepositoryGraph(nodes=[node_a, node_b, node_f], edges=[edge1, edge2])


class FakeGraphService:
    """
    Stub GraphService that returns a pre-built minimal graph without
    parsing or disk access.
    """

    def generate_graph(self, repository_path: str) -> RepositoryGraph:
        return _make_minimal_graph()


# ===========================================================================
# Pytest fixtures
# ===========================================================================

@pytest.fixture
def client():
    """
    TestClient with dependency overrides injecting the fake services.

    Environment variables ANTHROPIC_API_KEY and GOOGLE_API_KEY are cleared
    to ensure /qa tests run in offline mode (no real LLM calls).

    The rate limiter store is cleared before each test to prevent state
    leaking across test runs (the module-level _qa_limiter accumulates
    timestamps per IP, which can trigger 429s in long test suites).
    """
    app.dependency_overrides[get_repository_service] = lambda: FakeRepositoryService()
    app.dependency_overrides[get_graph_service] = lambda: FakeGraphService()
    # Clear LLM keys so /qa runs in offline mode
    env_patch = patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "",
        "GOOGLE_API_KEY": "",
    })
    env_patch.start()

    # Reset rate limiter state so tests don't fail due to accumulated counts
    from app.core.security import _qa_limiter
    with _qa_limiter._lock:
        _qa_limiter._store.clear()

    with TestClient(app) as c:
        yield c
    env_patch.stop()
    app.dependency_overrides.clear()


# ===========================================================================
# /analyze endpoint tests
# ===========================================================================

class TestAnalyzeEndpoint:

    def test_analyze_returns_200(self, client):
        resp = client.post("/analyze", json={"repo_url": "https://github.com/psf/requests"})
        assert resp.status_code == 200

    def test_analyze_response_structure(self, client):
        resp = client.post("/analyze", json={"repo_url": "https://github.com/psf/requests"})
        data = resp.json()
        assert "repository_name" in data
        assert "total_files" in data
        assert "language_distribution" in data

    def test_analyze_returns_summary_data(self, client):
        resp = client.post("/analyze", json={"repo_url": "https://github.com/psf/requests"})
        data = resp.json()
        assert data["total_files"] == 42
        assert data["framework"] == "FastAPI"

    def test_analyze_rejects_http_url(self, client):
        resp = client.post("/analyze", json={"repo_url": "http://github.com/psf/requests"})
        assert resp.status_code == 422

    def test_analyze_rejects_file_url(self, client):
        resp = client.post("/analyze", json={"repo_url": "file:///etc/passwd"})
        assert resp.status_code == 422

    def test_analyze_rejects_arbitrary_host(self, client):
        resp = client.post("/analyze", json={"repo_url": "https://evil.com/bad/repo"})
        assert resp.status_code == 422

    def test_analyze_rejects_missing_body(self, client):
        resp = client.post("/analyze", json={})
        assert resp.status_code == 422

    def test_analyze_rejects_empty_url(self, client):
        resp = client.post("/analyze", json={"repo_url": ""})
        assert resp.status_code == 422


# ===========================================================================
# /graph endpoint tests
# ===========================================================================

class TestGraphEndpoint:

    def test_graph_returns_200(self, client):
        resp = client.post("/graph", json={"repo_url": "https://github.com/psf/requests"})
        assert resp.status_code == 200

    def test_graph_response_has_nodes_and_edges(self, client):
        resp = client.post("/graph", json={"repo_url": "https://github.com/psf/requests"})
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_graph_nodes_have_required_fields(self, client):
        resp = client.post("/graph", json={"repo_url": "https://github.com/psf/requests"})
        data = resp.json()
        for node in data["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "label" in node

    def test_graph_edges_have_required_fields(self, client):
        resp = client.post("/graph", json={"repo_url": "https://github.com/psf/requests"})
        data = resp.json()
        for edge in data["edges"]:
            assert "source" in edge
            assert "target" in edge
            assert "relationship" in edge

    def test_graph_rejects_invalid_url(self, client):
        resp = client.post("/graph", json={"repo_url": "https://notallowed.com/x/y"})
        assert resp.status_code == 422


# ===========================================================================
# /qa endpoint tests
# ===========================================================================

class TestQAEndpoint:

    def test_qa_returns_200_offline_mode(self, client):
        """Without LLM key, /qa returns 200 with answer=null."""
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        assert resp.status_code == 200

    def test_qa_response_structure(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        data = resp.json()
        assert "question" in data
        assert "source_nodes" in data
        assert "retrieval_metadata" in data
        assert "intent_categories" in data

    def test_qa_question_preserved(self, client):
        question = "What does MyClass do?"
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": question,
        })
        data = resp.json()
        assert data["question"] == question

    def test_qa_offline_returns_llm_context(self, client):
        """In offline mode (no LLM key), llm_context field should be populated."""
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "How does process work?",
        })
        data = resp.json()
        # answer should be null in offline mode
        assert data.get("answer") is None
        # llm_context should be populated
        assert data.get("llm_context") is not None
        assert len(data["llm_context"]) > 0

    def test_qa_retrieval_metadata_fields(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "How does process work?",
        })
        meta = resp.json()["retrieval_metadata"]
        assert "intent_categories" in meta
        assert "keywords" in meta
        assert "resolved_node_count" in meta
        assert "subgraph_node_count" in meta
        assert "traversal_strategy" in meta

    def test_qa_source_nodes_structure(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "How does process work?",
        })
        for node in resp.json()["source_nodes"]:
            assert "node_id" in node
            assert "node_type" in node
            assert "label" in node
            assert "score" in node

    def test_qa_rejects_empty_question(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "",
        })
        assert resp.status_code == 422

    def test_qa_rejects_whitespace_only_question(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "   ",
        })
        assert resp.status_code == 422

    def test_qa_rejects_invalid_repo_url(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://evil.com/bad/repo",
            "question": "What does this do?",
        })
        assert resp.status_code == 422

    def test_qa_rejects_top_k_too_large(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
            "top_k": 100,
        })
        assert resp.status_code == 422

    def test_qa_rejects_top_k_zero(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
            "top_k": 0,
        })
        assert resp.status_code == 422

    def test_qa_rejects_max_hops_too_large(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
            "max_hops": 10,
        })
        assert resp.status_code == 422

    def test_qa_accepts_valid_top_k_and_max_hops(self, client):
        resp = client.post("/qa", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
            "top_k": 5,
            "max_hops": 2,
        })
        assert resp.status_code == 200

    def test_qa_http_url_rejected(self, client):
        resp = client.post("/qa", json={
            "repo_url": "http://github.com/psf/requests",
            "question": "What is this?",
        })
        assert resp.status_code == 422


# ===========================================================================
# /qa/async and /qa/jobs/{job_id} endpoint tests
# ===========================================================================

class TestQAAsyncEndpoint:

    def test_async_returns_202(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        assert resp.status_code == 202

    def test_async_response_has_job_id(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        data = resp.json()
        assert "job_id" in data
        assert "status" in data
        assert "poll_url" in data

    def test_async_status_is_queued_or_running(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        data = resp.json()
        assert data["status"] in ("queued", "running", "done")

    def test_async_poll_url_references_job_id(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        data = resp.json()
        assert data["job_id"] in data["poll_url"]

    def test_async_rejects_empty_question(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "",
        })
        assert resp.status_code == 422

    def test_async_rejects_invalid_url(self, client):
        resp = client.post("/qa/async", json={
            "repo_url": "https://evil.com/bad/repo",
            "question": "What is this?",
        })
        assert resp.status_code == 422

    def test_job_poll_returns_404_for_unknown_id(self, client):
        resp = client.get("/qa/jobs/nonexistent-job-id-123")
        assert resp.status_code == 404

    def test_job_poll_returns_job_status(self, client):
        # Submit a job first
        submit = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does process do?",
        })
        job_id = submit.json()["job_id"]

        # Poll the job
        poll = client.get(f"/qa/jobs/{job_id}")
        assert poll.status_code == 200
        data = poll.json()
        assert data["job_id"] == job_id
        assert data["status"] in ("queued", "running", "done", "error")
        assert "created_at" in data

    def test_job_poll_returns_valid_status_field(self, client):
        """
        Polling a submitted job always returns one of the known statuses.

        Note on TestClient + asyncio.create_task:
        FastAPI's synchronous TestClient (backed by HTTPX) does not advance
        the event loop between requests, so background tasks created with
        asyncio.create_task() are not guaranteed to complete during test
        execution. This test therefore only asserts that the status field
        is a valid member of the JobStatus enum — not that the job has
        progressed to 'done'. End-to-end completion is verified in
        integration tests that use an async HTTP client.
        """
        submit = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        job_id = submit.json()["job_id"]
        poll = client.get(f"/qa/jobs/{job_id}")
        assert poll.status_code == 200
        status = poll.json()["status"]
        assert status in ("queued", "running", "done", "error")

    def test_job_response_schema_is_complete(self, client):
        """A polled job always returns all required fields."""
        submit = client.post("/qa/async", json={
            "repo_url": "https://github.com/psf/requests",
            "question": "What does MyClass do?",
        })
        job_id = submit.json()["job_id"]
        data = client.get(f"/qa/jobs/{job_id}").json()
        assert "job_id" in data
        assert "status" in data
        assert "created_at" in data
        # completed_at and result may be None while still running
        assert "completed_at" in data
        assert "result" in data
        assert "error" in data
