"""
app/cache/job_store.py
========================
SQLite-backed persistent job store for /qa/async jobs.

Replaces the in-memory ``_JobStore`` in endpoints.py with a SQLite database
so jobs survive server restarts. The database lives in the ``.cache/``
directory alongside the graph cache.

Design decisions
----------------
- SQLite: zero infrastructure — no Redis, no Postgres, no Celery. A single
  .db file that survives process restarts. Appropriate for single-worker
  deployments. For multi-worker Gunicorn, SQLite with WAL mode handles
  concurrent reads from multiple processes safely.
- WAL mode: enables concurrent reads from multiple Gunicorn workers without
  locking. Writers still serialize, but at <1 job/sec write throughput that
  is not a bottleneck.
- JSON serialization: job results are stored as JSON so the store is portable
  and inspectable with standard tools (sqlite3, DB Browser for SQLite).
- TTL: jobs older than ``ttl_days`` (default: 7) are pruned on startup to
  prevent unbounded growth.

Usage
-----
::

    store = PersistentJobStore()            # creates/opens .cache/jobs.db
    job = store.create(request)             # returns Job dataclass
    store.update(job.id, status="running")
    job = store.get(job.id)
    store.cleanup_expired()                 # prune old jobs
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DB_PATH = os.path.join(".cache", "jobs.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'queued',
    request_json TEXT NOT NULL,
    result_json TEXT,
    error       TEXT,
    created_at  TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
"""


@dataclass
class Job:
    id: str
    status: str  # "queued" | "running" | "done" | "error"
    request: dict  # serialised QARequest
    result: Optional[dict] = None  # serialised QAResponse (when done)
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class PersistentJobStore:
    """
    Thread-safe SQLite-backed job store.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file.  Created (with its parent
        directories) if it does not exist.
    ttl_days : int
        Jobs older than this are deleted on startup.
    """

    def __init__(self, db_path: str = _DB_PATH, ttl_days: int = 7) -> None:
        self._db_path = db_path
        self._ttl_days = ttl_days
        self._local = threading.local()  # per-thread connection
        self._init_lock = threading.Lock()
        self._initialized = False
        self._ensure_db()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        """Return a per-thread SQLite connection (created lazily)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _ensure_db(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
            conn = self._conn()
            conn.executescript(_SCHEMA)
            conn.commit()
            self._initialized = True
            self.cleanup_expired()
            logger.debug("PersistentJobStore initialised at %s", self._db_path)

    @staticmethod
    def _dt_str(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        return dt.isoformat()

    @staticmethod
    def _dt_parse(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        return datetime.fromisoformat(s)

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            status=row["status"],
            request=json.loads(row["request_json"]),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
            created_at=self._dt_parse(row["created_at"]) or datetime.now(timezone.utc),
            completed_at=self._dt_parse(row["completed_at"]),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, request: Any) -> Job:
        """Create a new job and persist it. Returns the Job dataclass."""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        req_json = json.dumps(
            request.model_dump() if hasattr(request, "model_dump") else dict(request)
        )
        conn = self._conn()
        conn.execute(
            "INSERT INTO jobs (id, status, request_json, created_at) VALUES (?, ?, ?, ?)",
            (job_id, "queued", req_json, self._dt_str(now)),
        )
        conn.commit()
        return Job(id=job_id, status="queued", request=json.loads(req_json), created_at=now)

    def get(self, job_id: str) -> Optional[Job]:
        """Return the Job for ``job_id``, or None if not found."""
        row = self._conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def update(self, job_id: str, **kwargs: Any) -> None:
        """Update one or more fields on a job."""
        conn = self._conn()
        for key, value in kwargs.items():
            if key == "result" and value is not None:
                val = json.dumps(
                    value.model_dump() if hasattr(value, "model_dump") else dict(value)
                )
                conn.execute("UPDATE jobs SET result_json = ? WHERE id = ?", (val, job_id))
            elif key == "completed_at":
                conn.execute(
                    "UPDATE jobs SET completed_at = ? WHERE id = ?",
                    (self._dt_str(value), job_id),
                )
            elif key in ("status", "error"):
                conn.execute(
                    f"UPDATE jobs SET {key} = ? WHERE id = ?",  # noqa: S608
                    (value, job_id),
                )
        conn.commit()

    def cleanup_expired(self) -> int:
        """Delete jobs older than ``ttl_days``. Returns number deleted."""
        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        cutoff -= timedelta(days=self._ttl_days)
        conn = self._conn()
        cur = conn.execute("DELETE FROM jobs WHERE created_at < ?", (self._dt_str(cutoff),))
        conn.commit()
        if cur.rowcount:
            logger.info(
                "Pruned %d expired jobs (older than %d days).", cur.rowcount, self._ttl_days
            )
        return cur.rowcount
