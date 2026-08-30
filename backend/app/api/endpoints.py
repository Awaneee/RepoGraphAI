"""
app/api/endpoints.py
=====================
FastAPI router for RepoGraphAI.

Endpoints
---------
GET  /health            — Liveness/readiness check; reports subsystem status.
POST /analyze           — Clone a repository and return a filesystem-level summary.
POST /graph             — Clone/cache a repository and return its typed knowledge graph.
POST /qa                — Synchronous GraphRAG Q&A (blocks until complete).
POST /qa/async          — Async GraphRAG Q&A; returns a job_id immediately (HTTP 202).
GET  /qa/jobs/{job_id}  — Poll a previously submitted async job for status / result.
POST /qa/stream         — GraphRAG Q&A with Server-Sent Events token streaming.
POST /sessions          — Create a pinned repo session for multi-turn Q&A.
POST /sessions/{id}/qa  — Ask a follow-up question within an existing session.

Service injection
-----------------
Services are injected via FastAPI's Depends() mechanism rather than being
module-level singletons. This makes each service independently replaceable
in tests (TestClient with dependency_overrides) and prevents shared state
between requests.

LLM provider selection (for /qa and /qa/async)
-----------------------------------------------
Controlled by environment variables:
  ANTHROPIC_API_KEY  — use the Anthropic Messages API
  GOOGLE_API_KEY     — use the Gemini API
  DEFAULT_LLM_PROVIDER = "anthropic" | "gemini"  (default: "anthropic")

If neither key is set, the /qa endpoint returns the ContextPackage without
an LLM answer (useful for offline testing and retrieval benchmarking).

Async job execution
-------------------
/qa/async uses asyncio.to_thread() to run the full pipeline (clone + parse +
graph build + retrieval + LLM call) in a thread-pool worker without blocking
the event loop. Jobs are tracked in an in-memory JobStore; results survive for
the lifetime of the server process.

Limitation: the JobStore is in-process only. In a multi-worker deployment
(Gunicorn with multiple Uvicorn workers), a job submitted to worker A is not
visible on worker B. For production multi-worker setups, replace JobStore with
a Redis-backed store. For a single-worker deployment (the default here), the
in-process store is sufficient.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import rate_limit_qa, require_api_key
from app.models.pydantic_models import (
    RepositoryGraph,
    RepositoryRequest,
    RepositorySummary,
)
from app.services.graph_services import GraphService
from app.services.repository_service import RepositoryService

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency factories (FastAPI Depends)
# ---------------------------------------------------------------------------

def get_repository_service() -> RepositoryService:
    """Dependency: return a fresh RepositoryService for this request."""
    return RepositoryService()


def get_graph_service() -> GraphService:
    """Dependency: return a fresh GraphService for this request."""
    return GraphService()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QARequest(BaseModel):
    repo_url: str
    question: str
    top_k: int = 10
    max_hops: int = 1
    use_embeddings: bool = False
    """
    If True, use hybrid (keyword + semantic) retrieval via weighted RRF.
    Falls back to TF-IDF when sentence-transformers/torch is not installed.
    Default False — pure keyword retrieval is fast and achieves 82.6% Top-1.
    """


class SourceNodeResponse(BaseModel):
    node_id: str
    node_type: str
    label: str
    score: float
    file_path: Optional[str] = None
    line_number: Optional[int] = None


class RetrievalMetadataResponse(BaseModel):
    intent_categories: list[str]
    keywords: list[str]
    resolved_node_count: int
    subgraph_node_count: int
    subgraph_edge_count: int
    traversal_strategy: str


class QAResponse(BaseModel):
    question: str
    answer: Optional[str] = None
    source_nodes: list[SourceNodeResponse]
    retrieval_metadata: RetrievalMetadataResponse
    intent_categories: list[str]
    llm_context: Optional[str] = None
    """
    Populated only when no LLM key is configured (offline mode).
    Contains the full ContextPackage.llm_context text — useful for debugging.
    """


class JobStatus(str, Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"


class JobSubmittedResponse(BaseModel):
    """Returned immediately from POST /qa/async (HTTP 202)."""
    job_id: str
    status: JobStatus
    poll_url: str


class JobStatusResponse(BaseModel):
    """Returned from GET /qa/jobs/{job_id}."""
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[QAResponse] = None
    error: Optional[str] = None


class SessionCreateRequest(BaseModel):
    repo_url: str
    top_k: int = 10
    max_hops: int = 1
    use_embeddings: bool = False


class SessionCreatedResponse(BaseModel):
    session_id: str
    repo_url: str
    node_count: int
    edge_count: int


class SessionQARequest(BaseModel):
    question: str


# ---------------------------------------------------------------------------
# In-process job store
# ---------------------------------------------------------------------------

@dataclass
class _QAJob:
    id: str
    request: QARequest
    status: JobStatus = JobStatus.QUEUED
    result: Optional[QAResponse] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class _JobStore:
    """
    Thread-safe in-memory job store.

    Limitation: in-process only. Replace with a SQLite or Redis-backed store
    for persistence across server restarts or multi-worker deployments.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, _QAJob] = {}
        self._lock = threading.Lock()

    def create(self, request: QARequest) -> _QAJob:
        job = _QAJob(id=str(uuid.uuid4()), request=request)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[_QAJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                for k, v in kwargs.items():
                    setattr(job, k, v)


# Module-level stores
_job_store = _JobStore()


# ---------------------------------------------------------------------------
# In-process session store (for multi-turn Q&A)
# ---------------------------------------------------------------------------

@dataclass
class _Session:
    id: str
    repo_url: str
    graph: object               # RepositoryGraph
    context_builder: object     # ContextBuilder
    history: list[dict]         # list of {question, answer}
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class _SessionStore:
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def create(self, session: _Session) -> None:
        with self._lock:
            self._sessions[session.id] = session

    def get(self, session_id: str) -> Optional[_Session]:
        with self._lock:
            return self._sessions.get(session_id)

    def append_history(self, session_id: str, question: str, answer: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.history.append({"question": question, "answer": answer})


_session_store = _SessionStore()


# ---------------------------------------------------------------------------
# LLM provider factory
# ---------------------------------------------------------------------------

def _build_llm_provider():
    """
    Build the configured LLM provider from environment variables.
    Returns None if no key is configured (offline mode).
    """
    from app.rag.graphrag_engine import (
        AnthropicLLMProvider,
        GeminiLLMProvider,
    )

    provider_name = os.getenv("DEFAULT_LLM_PROVIDER", "anthropic").lower()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    google_key    = os.getenv("GOOGLE_API_KEY", "")

    if provider_name == "gemini" and google_key:
        return GeminiLLMProvider(api_key=google_key)
    if anthropic_key:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        return AnthropicLLMProvider(model=model, api_key=anthropic_key)
    if google_key:
        return GeminiLLMProvider(api_key=google_key)
    return None


# ---------------------------------------------------------------------------
# Shared pipeline helpers
# ---------------------------------------------------------------------------

def _validate_qa_request(request: QARequest) -> None:
    """Raise ValueError for invalid QARequest fields (including URL)."""
    from app.services.repository_service import validate_clone_url
    validate_clone_url(request.repo_url)
    if not request.question or not request.question.strip():
        raise ValueError("question must be a non-empty string.")
    if request.top_k < 1 or request.top_k > 50:
        raise ValueError("top_k must be between 1 and 50.")
    if request.max_hops < 0 or request.max_hops > 3:
        raise ValueError("max_hops must be between 0 and 3.")


def _build_context_builder_for_request(graph, request: QARequest, repo_path: str = ""):
    """Build the appropriate ContextBuilder based on request parameters."""
    from app.rag.context_builder import build_context_builder
    if getattr(request, "use_embeddings", False):
        from app.cache.repository_cache import RepositoryCache
        from app.retrievers.hybrid_retriever import build_hybrid_context_builder
        cache = RepositoryCache(repo_path) if repo_path else None
        return build_hybrid_context_builder(
            graph,
            top_k=request.top_k,
            max_hops=request.max_hops,
            cache=cache,
        )
    return build_context_builder(graph, top_k=request.top_k, max_hops=request.max_hops)


def _package_to_qa_response(question: str, context_package, llm_provider) -> QAResponse:
    """Run LLM (or offline) and return a QAResponse."""

    source_nodes = [
        SourceNodeResponse(
            node_id    = rn.node_id,
            node_type  = rn.node_type,
            label      = rn.label,
            score      = rn.score,
            file_path  = rn.file_path,
            line_number = rn.line_number,
        )
        for rn in context_package.resolved_nodes
    ]
    retrieval_metadata = RetrievalMetadataResponse(
        intent_categories   = context_package.intent_categories,
        keywords            = context_package.keywords,
        resolved_node_count = len(context_package.resolved_nodes),
        subgraph_node_count = context_package.subgraph_node_count,
        subgraph_edge_count = context_package.subgraph_edge_count,
        traversal_strategy  = context_package.traversal_strategy,
    )

    if llm_provider is None:
        return QAResponse(
            question           = question,
            answer             = None,
            source_nodes       = source_nodes,
            retrieval_metadata = retrieval_metadata,
            intent_categories  = context_package.intent_categories,
            llm_context        = context_package.llm_context,
        )

    # Rebuild context_builder from context_package is not possible here;
    # we use the pre-built one from the caller.
    # (The LLM call is handled by the caller, this function is for offline mode)
    # For the LLM path, the caller uses GraphRAGEngine directly.
    # This function returns offline-mode response only.
    return QAResponse(
        question           = question,
        answer             = None,
        source_nodes       = source_nodes,
        retrieval_metadata = retrieval_metadata,
        intent_categories  = context_package.intent_categories,
        llm_context        = context_package.llm_context,
    )


def _run_qa_pipeline(
    request: QARequest,
    repo_service: Optional[RepositoryService] = None,
    graph_service: Optional[GraphService] = None,
) -> QAResponse:
    """
    Execute the full GraphRAG pipeline synchronously.

    Safe to call from any thread (including thread-pool workers spawned by
    asyncio.to_thread). ``repo_service`` and ``graph_service`` are optional:
    the sync /qa endpoint passes Depends()-injected fakes for testability;
    the async background task passes None to get real instances.
    """
    from app.rag.graphrag_engine import GraphRAGEngine, LLMProviderError

    if repo_service is None:
        repo_service = RepositoryService()
    if graph_service is None:
        graph_service = GraphService()

    repo_path = repo_service.clone_repository(request.repo_url)
    graph     = graph_service.generate_graph(repo_path)

    context_builder = _build_context_builder_for_request(graph, request, repo_path)
    context_package = context_builder.build(request.question)

    source_nodes = [
        SourceNodeResponse(
            node_id    = rn.node_id,
            node_type  = rn.node_type,
            label      = rn.label,
            score      = rn.score,
            file_path  = rn.file_path,
            line_number = rn.line_number,
        )
        for rn in context_package.resolved_nodes
    ]
    retrieval_metadata = RetrievalMetadataResponse(
        intent_categories   = context_package.intent_categories,
        keywords            = context_package.keywords,
        resolved_node_count = len(context_package.resolved_nodes),
        subgraph_node_count = context_package.subgraph_node_count,
        subgraph_edge_count = context_package.subgraph_edge_count,
        traversal_strategy  = context_package.traversal_strategy,
    )

    llm_provider = _build_llm_provider()

    if llm_provider is None:
        return QAResponse(
            question           = request.question,
            answer             = None,
            source_nodes       = source_nodes,
            retrieval_metadata = retrieval_metadata,
            intent_categories  = context_package.intent_categories,
            llm_context        = context_package.llm_context,
        )

    try:
        engine   = GraphRAGEngine(context_builder, llm_provider)
        response = engine.answer(
            request.question,
            top_k=request.top_k,
            max_hops=request.max_hops,
        )
    except LLMProviderError as exc:
        raise RuntimeError(f"LLM provider error: {exc}") from exc

    return QAResponse(
        question           = request.question,
        answer             = response.answer,
        source_nodes       = source_nodes,
        retrieval_metadata = retrieval_metadata,
        intent_categories  = context_package.intent_categories,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health_check():
    """
    Liveness and readiness probe.

    Returns HTTP 200 with a JSON body describing each subsystem's status.
    Suitable for Docker/Kubernetes health checks and monitoring dashboards.
    """
    from app.embeddings.embedding_model import EmbeddingModel

    cache_ok = os.access(settings.CACHE_DIR, os.W_OK) if os.path.isdir(settings.CACHE_DIR) else os.access(".", os.W_OK)
    repos_ok = os.access(settings.REPOS_DIR, os.W_OK) if os.path.isdir(settings.REPOS_DIR) else os.access(".", os.W_OK)
    llm_ok   = bool(settings.ANTHROPIC_API_KEY or settings.GOOGLE_API_KEY)
    emb_ok   = EmbeddingModel.is_available()
    status   = "ok" if (cache_ok and repos_ok) else "degraded"

    return {
        "status":              status,
        "cache_dir_writable":  cache_ok,
        "repos_dir_writable":  repos_ok,
        "llm_configured":      llm_ok,
        "embedding_available": emb_ok,
    }


@router.post("/analyze", response_model=RepositorySummary)
def analyze_repository(
    request: RepositoryRequest,
    repository_service: RepositoryService = Depends(get_repository_service),
):
    """
    Clone a repository and return a filesystem-level summary.

    Includes language distribution, file category breakdown, framework
    detection, and largest files — a quick overview without graph building.
    """
    try:
        repo_path = repository_service.clone_repository(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return repository_service.generate_summary(repo_path)


@router.post("/graph", response_model=RepositoryGraph)
def generate_graph(
    request: RepositoryRequest,
    repository_service: RepositoryService = Depends(get_repository_service),
    graph_service: GraphService = Depends(get_graph_service),
):
    """
    Clone (or update) a repository and return its typed knowledge graph.

    The graph is cached on disk. Subsequent requests for the same unchanged
    repository skip the parse/build step entirely.
    """
    try:
        repo_path = repository_service.clone_repository(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return graph_service.generate_graph(repo_path)


@router.post(
    "/qa",
    response_model=QAResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit_qa)],
)
def qa_repository(
    request: QARequest,
    repository_service: RepositoryService = Depends(get_repository_service),
    graph_service: GraphService = Depends(get_graph_service),
):
    """
    Answer a natural-language question about a repository (synchronous).

    Blocks until complete. For large repos or long LLM calls, use
    POST /qa/async which returns a job_id immediately.

    Pipeline: clone → graph (cached) → retrieval → LLM → structured response.

    Error codes:
      422  Bad repo_url / question / parameter.
      404  Repository not found.
      500  Graph build or LLM failure.
    """
    try:
        _validate_qa_request(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        result = _run_qa_pipeline(
            request,
            repo_service=repository_service,
            graph_service=graph_service,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "404" in msg or "repository not found" in msg:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found: {request.repo_url}",
            ) from e
        raise HTTPException(status_code=500, detail=str(e)) from e

    return result


@router.post(
    "/qa/async",
    response_model=JobSubmittedResponse,
    status_code=202,
    dependencies=[Depends(require_api_key), Depends(rate_limit_qa)],
)
async def qa_repository_async(request: QARequest):
    """
    Submit a GraphRAG Q&A job and return immediately (HTTP 202 Accepted).

    The pipeline runs in a thread-pool worker via asyncio.to_thread() so the
    event loop is never blocked. Use GET /qa/jobs/{job_id} to poll for results.

    Typical flow:
        POST /qa/async  →  {job_id, status: "queued", poll_url}
        GET  /qa/jobs/{id}  →  {status: "running"}
        GET  /qa/jobs/{id}  →  {status: "done", result: {...}}
    """
    try:
        _validate_qa_request(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    job = _job_store.create(request)

    async def _execute() -> None:
        _job_store.update(job.id, status=JobStatus.RUNNING)
        try:
            result = await asyncio.to_thread(_run_qa_pipeline, request)
            _job_store.update(
                job.id,
                status       = JobStatus.DONE,
                result       = result,
                completed_at = datetime.now(timezone.utc),
            )
        except Exception as exc:
            _job_store.update(
                job.id,
                status       = JobStatus.ERROR,
                error        = str(exc),
                completed_at = datetime.now(timezone.utc),
            )

    asyncio.create_task(_execute())

    return JobSubmittedResponse(
        job_id   = job.id,
        status   = JobStatus.QUEUED,
        poll_url = f"/qa/jobs/{job.id}",
    )


@router.post(
    "/qa/stream",
    dependencies=[Depends(require_api_key), Depends(rate_limit_qa)],
)
def qa_repository_stream(
    request: QARequest,
    repository_service: RepositoryService = Depends(get_repository_service),
    graph_service: GraphService = Depends(get_graph_service),
):
    """
    Stream a GraphRAG answer using Server-Sent Events (SSE).

    Returns Content-Type: text/event-stream. Each event is a JSON object
    on a data: line followed by two newlines.

    Event sequence:
      1. {"type": "metadata", ...}   — retrieval info before first token
      2. {"type": "token", "text": "..."} — one or more LLM text chunks
      3. {"type": "done", "full_answer": "..."}

    In offline mode (no LLM key), emits metadata → context-as-token → done.

    Example (curl):
        curl -N -X POST http://localhost:8000/qa/stream \\
             -H "Content-Type: application/json" \\
             -d '{"repo_url":"https://github.com/psf/requests","question":"How does Session.send work?"}'
    """
    from app.rag.graphrag_engine import GraphRAGEngine, LLMProviderError

    try:
        _validate_qa_request(request)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        repo_path = repository_service.clone_repository(request.repo_url)
        graph     = graph_service.generate_graph(repo_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    context_builder = _build_context_builder_for_request(graph, request, repo_path)
    llm_provider    = _build_llm_provider()

    def _event_generator():
        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload)}\n\n"

        if llm_provider is None:
            try:
                package = context_builder.build(request.question)
            except Exception as exc:
                yield _sse({"type": "error", "detail": str(exc)})
                return

            source_nodes = [
                {"node_id": rn.node_id, "node_type": rn.node_type,
                 "label": rn.label, "score": rn.score}
                for rn in package.resolved_nodes
            ]
            yield _sse({
                "type":             "metadata",
                "intent_categories": package.intent_categories,
                "keywords":          package.keywords,
                "source_nodes":      source_nodes,
                "offline":           True,
            })
            yield _sse({"type": "token", "text": package.llm_context})
            yield _sse({"type": "done", "full_answer": package.llm_context, "no_context": False})
            return

        engine = GraphRAGEngine(context_builder, llm_provider)
        try:
            for event in engine.stream_answer(
                request.question,
                top_k=request.top_k,
                max_hops=request.max_hops,
            ):
                yield _sse(event)
        except LLMProviderError as exc:
            yield _sse({"type": "error", "detail": str(exc)})
        except Exception as exc:
            yield _sse({"type": "error", "detail": f"Unexpected error: {exc}"})

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/qa/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Poll the status of a job submitted via POST /qa/async.

    Statuses: queued → running → done | error
    Returns 404 if the job_id is unknown (e.g., server restart).
    """
    job = _job_store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id!r} not found. It may have been lost on server restart.",
        )
    return JobStatusResponse(
        job_id       = job.id,
        status       = job.status,
        created_at   = job.created_at,
        completed_at = job.completed_at,
        result       = job.result,
        error        = job.error,
    )


# ---------------------------------------------------------------------------
# Multi-turn session endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=SessionCreatedResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit_qa)],
    status_code=201,
)
def create_session(
    request: SessionCreateRequest,
    repository_service: RepositoryService = Depends(get_repository_service),
    graph_service: GraphService = Depends(get_graph_service),
):
    """
    Create a pinned session for multi-turn Q&A over a single repository.

    The repository is cloned and its graph is built once; subsequent questions
    via POST /sessions/{id}/qa reuse the cached graph and context builder
    without any re-cloning or re-parsing.

    Sessions are in-memory: they are lost when the server restarts.

    Returns:
      session_id  — use this in subsequent /sessions/{id}/qa requests
      node_count  — number of nodes in the knowledge graph
      edge_count  — number of edges in the knowledge graph
    """
    from app.services.repository_service import validate_clone_url

    try:
        validate_clone_url(request.repo_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        repo_path = repository_service.clone_repository(request.repo_url)
        graph     = graph_service.generate_graph(repo_path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    context_builder = _build_context_builder_for_request(
        graph,
        QARequest(
            repo_url=request.repo_url,
            question="",
            top_k=request.top_k,
            max_hops=request.max_hops,
            use_embeddings=request.use_embeddings,
        ),
    )

    session = _Session(
        id              = str(uuid.uuid4()),
        repo_url        = request.repo_url,
        graph           = graph,
        context_builder = context_builder,
        history         = [],
    )
    _session_store.create(session)

    return SessionCreatedResponse(
        session_id = session.id,
        repo_url   = request.repo_url,
        node_count = len(graph.nodes),
        edge_count = len(graph.edges),
    )


@router.post(
    "/sessions/{session_id}/qa",
    response_model=QAResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit_qa)],
)
def session_qa(session_id: str, request: SessionQARequest):
    """
    Ask a question within an existing session (multi-turn Q&A).

    Unlike POST /qa, this endpoint:
      - Reuses the already-built graph and context builder (fast).
      - Injects conversation history into the LLM prompt so follow-up
        questions like "What calls it?" resolve correctly.
      - Does NOT re-clone the repository.

    Error codes:
      404  Session not found (expired or server restarted).
      422  Empty question.
      500  LLM error.
    """
    from app.rag.graphrag_engine import GraphRAGEngine, GraphRAGPromptBuilder, LLMProviderError

    session = _session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id!r} not found. Create one via POST /sessions.",
        )

    if not request.question or not request.question.strip():
        raise HTTPException(status_code=422, detail="question must be a non-empty string.")

    llm_provider = _build_llm_provider()

    try:
        context_package = session.context_builder.build(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context build failed: {e}") from e

    # Inject conversation history into the LLM context when history exists
    history_prefix = ""
    if session.history:
        turns = "\n".join(
            f"Q: {h['question']}\nA: {h['answer']}"
            for h in session.history[-5:]  # keep last 5 turns
        )
        history_prefix = f"CONVERSATION HISTORY (most recent):\n{turns}\n\n"

    source_nodes = [
        SourceNodeResponse(
            node_id    = rn.node_id,
            node_type  = rn.node_type,
            label      = rn.label,
            score      = rn.score,
            file_path  = rn.file_path,
            line_number = rn.line_number,
        )
        for rn in context_package.resolved_nodes
    ]
    retrieval_metadata = RetrievalMetadataResponse(
        intent_categories   = context_package.intent_categories,
        keywords            = context_package.keywords,
        resolved_node_count = len(context_package.resolved_nodes),
        subgraph_node_count = context_package.subgraph_node_count,
        subgraph_edge_count = context_package.subgraph_edge_count,
        traversal_strategy  = context_package.traversal_strategy,
    )

    if llm_provider is None:
        return QAResponse(
            question           = request.question,
            answer             = None,
            source_nodes       = source_nodes,
            retrieval_metadata = retrieval_metadata,
            intent_categories  = context_package.intent_categories,
            llm_context        = history_prefix + context_package.llm_context,
        )

    # Inject history into prompt via a custom PromptBuilder
    class _HistoryPromptBuilder(GraphRAGPromptBuilder):
        def build(self, package):
            bundle = super().build(package)
            if history_prefix:
                return bundle.__class__(
                    system_prompt = bundle.system_prompt,
                    user_prompt   = history_prefix + bundle.user_prompt,
                )
            return bundle

    try:
        engine   = GraphRAGEngine(session.context_builder, llm_provider, _HistoryPromptBuilder())
        response = engine.answer(request.question)
        answer   = response.answer
    except LLMProviderError as exc:
        raise HTTPException(status_code=500, detail=f"LLM provider error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GraphRAG error: {exc}") from exc

    _session_store.append_history(session_id, request.question, answer or "")

    return QAResponse(
        question           = request.question,
        answer             = answer,
        source_nodes       = source_nodes,
        retrieval_metadata = retrieval_metadata,
        intent_categories  = context_package.intent_categories,
    )
