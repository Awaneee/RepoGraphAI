"""
app/core/security.py
=====================
Lightweight API key authentication and in-process rate limiting.

No external packages (Redis, slowapi, etc.) are required. Both mechanisms
are implemented using Python stdlib only and wired into FastAPI via Depends().

Authentication
--------------
When the ``API_KEY`` setting is non-empty, the ``require_api_key`` dependency
checks the ``X-API-Key`` request header. Requests without a matching key
receive HTTP 401.

When ``API_KEY`` is unset (default), the dependency is a no-op — all requests
are allowed. This is the recommended configuration for local/internal use.

Rate limiting
-------------
``rate_limit_qa`` implements a sliding-window rate limiter keyed by client IP.
Each IP is allowed ``settings.RATE_LIMIT_REQUESTS`` requests in a rolling
``settings.RATE_LIMIT_WINDOW_SECONDS`` window. Requests beyond the limit
receive HTTP 429 with a ``Retry-After`` header.

The limiter state is in-process (a plain dict). In a multi-worker deployment,
each worker maintains an independent state — requests may exceed the nominal
limit by up to N×limit across N workers. For strict multi-worker rate limiting,
replace with a Redis-backed store. For single-worker deployments (the default
here), the in-process store is accurate.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

from fastapi import Header, HTTPException, Request

from app.core.config import settings

# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------

async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    FastAPI dependency that enforces API key authentication.

    When ``settings.API_KEY`` is set, the ``X-API-Key`` header must match.
    When ``settings.API_KEY`` is not set, this dependency is a no-op.

    Usage::

        @router.post("/qa", dependencies=[Depends(require_api_key)])
        def qa_endpoint(...): ...

    Raises
    ------
    HTTPException 401
        If the key is required but absent or incorrect.
    """
    configured_key = settings.API_KEY
    if not configured_key:
        return   # Auth disabled — allow all requests

    if x_api_key != configured_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )


# ---------------------------------------------------------------------------
# Sliding-window rate limiter
# ---------------------------------------------------------------------------

class _SlidingWindowLimiter:
    """
    Thread-safe sliding-window rate limiter.

    Maintains a deque of timestamps per client key.  On each request:
      1. Expire entries older than ``window_seconds``.
      2. If fewer than ``max_requests`` remain, admit the request.
      3. Otherwise, reject with 429.

    Space: O(max_requests) per client.
    Time:  O(expired_entries) per request (amortised O(1) for steady traffic).
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max       = max_requests
        self._window    = window_seconds
        self._store: dict[str, deque] = {}
        self._lock      = threading.Lock()

    def check(self, client_key: str) -> tuple[bool, int]:
        """
        Check whether ``client_key`` is within rate limit.

        Returns
        -------
        (allowed: bool, retry_after: int)
            ``retry_after`` is only meaningful when ``allowed`` is False.
        """
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            if client_key not in self._store:
                self._store[client_key] = deque()

            dq = self._store[client_key]

            # Expire old entries
            while dq and dq[0] < cutoff:
                dq.popleft()

            if len(dq) < self._max:
                dq.append(now)
                return True, 0
            else:
                # Earliest entry will expire at: dq[0] + window
                retry_after = max(1, int(dq[0] + self._window - now) + 1)
                return False, retry_after


# Module-level limiter — shared across all requests in this process.
_qa_limiter = _SlidingWindowLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)


async def rate_limit_qa(request: Request) -> None:
    """
    FastAPI dependency that enforces per-IP rate limiting on /qa* endpoints.

    Limits: ``settings.RATE_LIMIT_REQUESTS`` requests per
    ``settings.RATE_LIMIT_WINDOW_SECONDS`` seconds per client IP.

    The client IP is taken from ``request.client.host`` (the direct connection
    peer). Behind a reverse proxy, you should use the ``X-Forwarded-For``
    header instead — update ``_client_ip`` accordingly.

    Usage::

        @router.post("/qa", dependencies=[Depends(rate_limit_qa)])
        def qa_endpoint(...): ...

    Raises
    ------
    HTTPException 429
        When the limit is exceeded. Includes a ``Retry-After`` header.
    """
    client_ip = _client_ip(request)
    allowed, retry_after = _qa_limiter.check(client_ip)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Rate limit exceeded: {settings.RATE_LIMIT_REQUESTS} requests "
                f"per {settings.RATE_LIMIT_WINDOW_SECONDS}s. "
                f"Retry after {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )


def _client_ip(request: Request) -> str:
    """
    Extract the client IP from the request.

    Uses ``X-Forwarded-For`` if present (common behind Nginx/Traefik);
    falls back to the direct connection address.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
