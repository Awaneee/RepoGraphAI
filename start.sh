#!/usr/bin/env bash
# Launch the FastAPI backend on 127.0.0.1:8000 (internal only), then hand off
# to Streamlit on 0.0.0.0:7860 (the port HF Spaces exposes publicly).
#
# `exec` on the Streamlit line makes Streamlit PID 1, so container signals
# (SIGTERM on stop/redeploy) reach it directly and it shuts down cleanly.
# The backend runs in the background; when Streamlit exits, the container
# stops and the backend is killed with it.

set -euo pipefail

cd /app/backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    --log-level "${LOG_LEVEL:-info}" &

export REPOGRAPHAI_BACKEND_URL="http://127.0.0.1:8000"

# Wait briefly for the backend to accept connections so the first page load
# doesn't show "backend unreachable".
for _ in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

exec streamlit run /app/frontend/app.py \
    --server.port 7860 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableXsrfProtection false \
    --server.enableCORS false \
    --browser.gatherUsageStats false
