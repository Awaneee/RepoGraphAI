"""
Hugging Face Spaces entry point (Streamlit SDK).

HF runs this file with `streamlit run space_app.py`. Streamlit needs to be
the top-level process, so we launch the FastAPI backend as a background
subprocess before handing control to the existing frontend script.

The launch is idempotent: Streamlit re-executes this module on every user
interaction, so we probe port 8000 first and only spawn uvicorn if nothing
is already listening.
"""

from __future__ import annotations

import os
import runpy
import socket
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).parent
_BACKEND_DIR = _HERE / "backend"
_FRONTEND_APP = _HERE / "frontend" / "app.py"
_BACKEND_HOST = "127.0.0.1"
_BACKEND_PORT = 8000


def _backend_is_up() -> bool:
    with socket.socket() as s:
        s.settimeout(0.2)
        try:
            s.connect((_BACKEND_HOST, _BACKEND_PORT))
            return True
        except OSError:
            return False


def _ensure_backend() -> None:
    if _backend_is_up():
        return

    env = {**os.environ, "PYTHONPATH": str(_BACKEND_DIR)}
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            _BACKEND_HOST,
            "--port",
            str(_BACKEND_PORT),
        ],
        cwd=_BACKEND_DIR,
        env=env,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    # Wait up to 30s for the backend to accept connections.
    for _ in range(60):
        if _backend_is_up():
            return
        time.sleep(0.5)


_ensure_backend()
os.environ.setdefault(
    "REPOGRAPHAI_BACKEND_URL", f"http://{_BACKEND_HOST}:{_BACKEND_PORT}"
)

# Hand off to the existing Streamlit UI. runpy executes it in a fresh
# namespace, so its `st.set_page_config(...)` is still the first Streamlit
# call in that module scope.
runpy.run_path(str(_FRONTEND_APP), run_name="__main__")
