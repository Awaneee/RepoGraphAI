# syntax=docker/dockerfile:1
# RepoGraphAI — combined backend + Streamlit frontend container.
#
# Build:   docker build -t repographai .
# Run:     docker run -p 7860:7860 -e GOOGLE_API_KEY=... repographai
# Compose: docker compose up
#
# The Streamlit UI listens on $PORT (Render sets this to 10000; local `docker
# run` uses the 7860 default). The FastAPI backend runs on 127.0.0.1:8000
# inside the container and is not exposed publicly.

FROM python:3.12-slim AS base

# System deps: git (for GitPython clone), gcc/g++ (for sentence-transformers wheel build),
# curl (for start.sh backend-readiness probe).
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dependency layer (cached separately from app code) ---
FROM base AS deps

COPY backend/requirements.txt ./backend-requirements.txt
COPY frontend/requirements.txt ./frontend-requirements.txt

# Lean install for free-tier hosts (Render 512 MB, HF free, etc.).
# sentence-transformers + torch are intentionally omitted here: the
# "Semantic search" toggle is off by default and the extra ~1.2 GB
# blows past the free-tier image/memory budget. Add them back if you
# upgrade the plan.
RUN pip install --no-cache-dir -r backend-requirements.txt \
    && pip install --no-cache-dir -r frontend-requirements.txt \
    && pip install --no-cache-dir \
        google-genai \
        anthropic \
        tree-sitter \
        tree-sitter-typescript

# --- Application layer ---
FROM deps AS app

# Create the non-root user BEFORE the big COPY so we can use --chown and
# avoid a duplicate 1+ GB layer from a post-copy `chown -R`.
RUN useradd -m appuser

COPY --chown=appuser:appuser backend/  /app/backend/
COPY --chown=appuser:appuser frontend/ /app/frontend/
COPY --chown=appuser:appuser start.sh  /app/start.sh
RUN chmod +x /app/start.sh \
    && mkdir -p /app/backend/repos /app/backend/.cache \
    && chown appuser:appuser /app/backend/repos /app/backend/.cache

USER appuser

# Streamlit binds to $PORT (set by the platform: 10000 on Render, 7860 on HF,
# etc.). Falls back to 7860 for local `docker run` invocations.
ENV PORT=7860
EXPOSE 7860

CMD ["/app/start.sh"]
