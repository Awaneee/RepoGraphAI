"""
app/main.py
============
RepoGraphAI FastAPI application entry point.

Logging is configured here once so every module that uses
``logging.getLogger(__name__)`` inherits the same format and level.

Log level is controlled by the LOG_LEVEL environment variable (default INFO).
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.endpoints import router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

# Suppress overly verbose third-party loggers at INFO level
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("torch").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.info("Starting RepoGraphAI (log level: %s)", _LOG_LEVEL)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RepoGraphAI",
    description=(
        "Graph-native RAG pipeline for Python codebase intelligence.\n\n"
        "Parses Python repositories into typed knowledge graphs and answers "
        "natural-language questions via graph traversal + LLM generation."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(router)

# ---------------------------------------------------------------------------
# Observability middleware — structured per-request logging
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log each HTTP request with timing and status code.

    Produces one structured log line per request, e.g.:
        2026-08-30T12:00:00 INFO app.main POST /qa 200 1234ms ip=127.0.0.1

    Retrieval metadata (intent, node count, etc.) is logged separately inside
    the endpoint handlers via the graphrag_engine module.
    """
    start = time.perf_counter()
    method = request.method
    path = request.url.path
    client = request.client.host if request.client else "unknown"

    response = await call_next(request)

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    logger.info(
        "%s %s %d %dms ip=%s",
        method,
        path,
        response.status_code,
        elapsed_ms,
        client,
    )
    return response


# ---------------------------------------------------------------------------
# Serve the frontend (single HTML file)
# ---------------------------------------------------------------------------

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
_FRONTEND_DIR = os.path.normpath(_FRONTEND_DIR)

if os.path.isdir(_FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend():
        """Serve the RepoGraphAI single-page frontend."""
        index = os.path.join(_FRONTEND_DIR, "index.html")
        return FileResponse(index)
else:
    logger.warning("Frontend directory not found at %s — UI not served.", _FRONTEND_DIR)
