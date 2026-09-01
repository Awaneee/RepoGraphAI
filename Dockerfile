# syntax=docker/dockerfile:1
# RepoGraphAI — combined backend + Streamlit frontend container.
#
# Build:   docker build -t repographai .
# Run:     docker run -p 7860:7860 -e GOOGLE_API_KEY=... repographai
# Compose: docker compose up
#
# Port 7860 serves the Streamlit UI (public). Backend runs on 127.0.0.1:8000
# inside the container and is not exposed. This layout is what Hugging Face
# Spaces expects for a Docker Space.

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

# sentence-transformers and torch are heavy — install CPU-only torch first
RUN pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir \
        sentence-transformers \
    && pip install --no-cache-dir -r backend-requirements.txt \
    && pip install --no-cache-dir -r frontend-requirements.txt \
    && pip install --no-cache-dir google-genai anthropic

# --- Application layer ---
FROM deps AS app

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Cache the ML model in a location owned by /app so it survives the chown
# below and is reused (not re-downloaded) at container start.
ENV HF_HOME=/app/.hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/app/.hf_cache/sentence-transformers

RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2', device='cpu'); \
print('Model cached.')"

# Non-root user for security. On HF Spaces the writable location is /home/user
# (or /data for persistent storage); we use /app/backend/{repos,.cache} which
# are ephemeral but writable by appuser.
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

RUN mkdir -p /app/backend/repos /app/backend/.cache

# HF Spaces exposes exactly one port; 7860 is the default. Streamlit binds
# to 7860 in start.sh; the FastAPI backend runs on 127.0.0.1:8000 internally.
EXPOSE 7860

CMD ["/app/start.sh"]
