# syntax=docker/dockerfile:1
# RepoGraphAI — backend container
#
# Build:   docker build -t repographai .
# Run:     docker run -p 8000:8000 -e ANTHROPIC_API_KEY=sk-... repographai
# Compose: docker compose up

FROM python:3.12-slim AS base

# System deps: git (for GitPython clone), gcc/g++ (for sentence-transformers wheel build)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Dependency layer (cached separately from app code) ---
FROM base AS deps

COPY backend/requirements.txt ./
# sentence-transformers and torch are heavy — install CPU-only torch first
RUN pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
        sentence-transformers \
    && pip install --no-cache-dir -r requirements.txt

# --- Application layer ---
FROM deps AS app

COPY backend/ ./

# Pre-download the all-MiniLM-L6-v2 model so the container can run offline.
# Remove this RUN block if you want a smaller image and don't need offline embeddings.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2', device='cpu'); \
print('Model cached.')"

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Default directories (writable by appuser inside the container)
RUN mkdir -p repos .cache

EXPOSE 8000

# Single worker for this project — no shared state between workers.
# For multi-worker: replace with gunicorn + uvicorn workers and use a
# Redis-backed job store for /qa/async.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
