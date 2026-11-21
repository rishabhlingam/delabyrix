"""
backend/hitl/queue.py
──────────────────────
Thread-safe HITL review queue backed by SQLite.

Each HITLQueue instance owns a single SQLite database (file-backed or
in-memory).  The module-level singleton (get_queue()) is initialised from
``settings.hitl_db_path``; tests can bypass this by constructing
``HITLQueue(db_path=":memory:")`` directly so they never touch the file system.

Design notes
────────────
* sqlite3 connections are NOT thread-safe when shared.  We open a new
  connection per operation (check_same_thread=False is NOT used).  This is the
  safest pattern for FastAPI's threadpool workers.
* All rows are stored as JSON blobs for complex fields (pipeline_trace,
  escalation_rules) to avoid a schema migration every time the model grows.
* The table is created with CREATE TABLE IF NOT EXISTS so restarts are safe.

Usage
─────
    from backend.hitl.queue import get_queue

    q = get_queue()
    review_id = q.enqueue(session_id=..., user_type=..., ...)
    item = q.get_pending(review_id)
    q.approve(review_id, approved_response="...", reviewer_note=None)
    q.reject(review_id, rejection_reason="...")
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.hitl.models import ReviewItem, ReviewStatus


# ──────────────────────────────────────────────────────────────────────────────
# SQL helpers
# ──────────────────────────────────────────────────────────────────────────────

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS hitl_queue (
    review_id              TEXT PRIMARY KEY,
    session_id             TEXT NOT NULL,
    submitted_at           TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'pending',
    user_type              TEXT NOT NULL,
    country                TEXT NOT NULL,
    pipeline_trace         TEXT NOT NULL DEFAULT '{}',
    draft_response         TEXT NOT NULL DEFAULT '',
    draft_response_english TEXT,
    source_language        TEXT NOT NULL DEFAULT 'en',
    redacted_original_text TEXT,
    english_inquiry        TEXT,
    escalation_rules       TEXT NOT NULL DEFAULT '[]',
    reviewed_at            TEXT,
    approved_response      TEXT,
    reviewer_note          TEXT,
    rejection_reason       TEXT,
    rejection_reason_english TEXT
)
"""

_INSERT = """
INSERT INTO hitl_queue (
    review_id, session_id, submitted_at, status,
    user_type, country, pipeline_trace, draft_response,
    draft_response_english, source_language,
    redacted_original_text, english_inquiry, escalation_rules
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_BY_ID = "SELECT * FROM hitl_queue WHERE review_id = ?;"

_SELECT_PENDING = (
    "SELECT * FROM hitl_queue WHERE status = 'pending' ORDER BY submitted_at ASC;"
)

_SELECT_BY_SESSION = (
    "SELECT * FROM hitl_queue WHERE session_id = ? ORDER BY submitted_at DESC LIMIT 1;"
)

_UPDATE_APPROVE = """
UPDATE hitl_queue
   SET status = 'approved',
       approved_response = ?,
       reviewer_note = ?,
       reviewed_at = ?
 WHERE review_id = ?;
"""

_UPDATE_REJECT = """
UPDATE hitl_queue
   SET status = 'rejected',
       rejection_reason = ?,
       rejection_reason_english = ?,
       reviewed_at = ?
 WHERE review_id = ?;
"""

_DELETE_ALL = "DELETE FROM hitl_queue;"

# Migration statements: add new columns to pre-existing databases.
_MIGRATE_STMTS: list[str] = [
    "ALTER TABLE hitl_queue ADD COLUMN draft_response_english TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN source_language TEXT NOT NULL DEFAULT 'en';",
    "ALTER TABLE hitl_queue ADD COLUMN redacted_original_text TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN english_inquiry TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN rejection_reason_english TEXT;",
]


# ──────────────────────────────────────────────────────────────────────────────
# Row → ReviewItem conversion
# ──────────────────────────────────────────────────────────────────────────────

def _row_to_item(row: sqlite3.Row) -> ReviewItem:
    """Convert a sqlite3.Row (dict-like) to a ReviewItem instance."""
    d = dict(row)
    return ReviewItem(
        review_id=d["review_id"],
        session_id=d["session_id"],
        submitted_at=datetime.fromisoformat(d["submitted_at"]),
        status=ReviewStatus(d["status"]),
        user_type=d["user_type"],
        country=d["country"],
        pipeline_trace=json.loads(d["pipeline_trace"]),
        draft_response=d["draft_response"],
        draft_response_english=d.get("draft_response_english"),
        source_language=d.get("source_language", "en") or "en",
        redacted_original_text=d.get("redacted_original_text"),
        english_inquiry=d.get("english_inquiry"),
        escalation_rules=json.loads(d["escalation_rules"]),
        reviewed_at=(
            datetime.fromisoformat(d["reviewed_at"]) if d["reviewed_at"] else None
        ),
        approved_response=d.get("approved_response"),
        reviewer_note=d.get("reviewer_note"),
        rejection_reason=d.get("rejection_reason"),
        rejection_reason_english=d.get("rejection_reason_english"),
    )


# ──────────────────────────────────────────────────────────────────────────────
# HITLQueue
# ──────────────────────────────────────────────────────────────────────────────

class HITLQueue:
    """
    Thread-safe HITL review queue backed by SQLite.

    Parameters
    ──────────
    db_path : Path to the SQLite database file, or ``":memory:"`` for an
              ephemeral in-memory database (useful in tests).
              Defaults to the value of ``settings.hitl_db_path``.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            from backend.config import get_settings
            db_path = get_settings().hitl_db_path

        self._db_path = db_path
        self._lock = threading.Lock()

        # In-memory databases are connection-scoped in sqlite3: a new
        # connection always starts with a blank database.  We therefore
        # keep a single persistent connection for the ":memory:" case.
        self._mem_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            # Create parent directories for file-backed DBs
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialise the schema (safe to call on every start).
        # Use execute() instead of executescript() so it participates in the
        # normal transaction flow and works identically for file and in-memory DBs.
        conn = self._connect()
        conn.execute(_CREATE_TABLE)
        # Migrate: add bilingual columns to existing databases.
        # ALTER TABLE … ADD COLUMN is a no-op if the column already exists
        # (SQLite ≥3.37 supports IF NOT EXISTS; for older versions we silently
        # ignore OperationalError("duplicate column name")).
        for _stmt in _MIGRATE_STMTS:
            try:
                conn.execute(_stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()

    # ── Internal connection helper ────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        """
        Return a SQLite connection.

        For in-memory DBs: returns the single persistent shared connection
        (the same connection that created the schema).
        For file-backed DBs: opens a fresh connection per call (safe for
        multi-threaded use because the lock guards all operations).
        """
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Write operations ──────────────────────────────────────────────────────

    def enqueue(
        self,
        session_id: str,
        user_type: str,
        country: str,
        pipeline_trace: Dict[str, Any],
        draft_response: str,
        escalation_rules: Optional[List[str]] = None,
        source_language: str = "en",
        draft_response_english: Optional[str] = None,
        redacted_original_text: Optional[str] = None,
        english_inquiry: Optional[str] = None,
    ) -> str:
        """
        Add a new item to the queue and persist it to SQLite.

        Parameters
        ──────────
        session_id             : Session UUID from the agent request.
        user_type              : "patient" | "provider" | "coordinator".
        country                : ISO 3166-1 alpha-2 country code.
        pipeline_trace         : Stage outputs dict (no raw PII).
        draft_response         : Draft response text in original source language.
        escalation_rules       : List of triggered rule labels.
        source_language        : BCP-47 source language code ("en", "es", "hi").
        draft_response_english : English version of draft_response (when source != en).
        redacted_original_text : Redacted patient inquiry in original language.
        english_inquiry        : English translation of the patient inquiry.

        Returns
        ───────
        review_id (UUID string) for the new queue item.
        """
        review_id = str(uuid.uuid4())
        submitted_at = datetime.now(tz=timezone.utc).isoformat()

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    _INSERT,
                    (
                        review_id,
                        session_id,
                        submitted_at,
                        ReviewStatus.pending.value,
                        user_type,
                        country,
                        json.dumps(pipeline_trace),
                        draft_response,
                        draft_response_english,
                        source_language,
                        redacted_original_text,
                        english_inquiry,
                        json.dumps(escalation_rules or []),
                    ),
                )
        return review_id

    def approve(
        self,
        review_id: str,
        approved_response: str,
        reviewer_note: Optional[str] = None,
    ) -> ReviewItem:
        """
        Mark a pending item as approved with the reviewer's final response.

        Raises
        ──────
        KeyError  — when *review_id* does not exist.
        ValueError — when item is not in 'pending' status.
        """
        reviewed_at = datetime.now(tz=timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
                if row is None:
                    raise KeyError(f"review_id not found: {review_id!r}")
                if row["status"] != ReviewStatus.pending.value:
                    raise ValueError(
                        f"Cannot approve item with status={row['status']!r}. "
                        "Only 'pending' items can be approved."
                    )
                conn.execute(
                    _UPDATE_APPROVE,
                    (approved_response, reviewer_note, reviewed_at, review_id),
                )
                updated_row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
        return _row_to_item(updated_row)

    def reject(
        self,
        review_id: str,
        rejection_reason: str,
        rejection_reason_english: Optional[str] = None,
    ) -> ReviewItem:
        """
        Mark a pending item as rejected.

        Raises
        ──────
        KeyError  — when *review_id* does not exist.
        ValueError — when item is not in 'pending' status.
        """
        reviewed_at = datetime.now(tz=timezone.utc).isoformat()
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
                if row is None:
                    raise KeyError(f"review_id not found: {review_id!r}")
                if row["status"] != ReviewStatus.pending.value:
                    raise ValueError(
                        f"Cannot reject item with status={row['status']!r}. "
                        "Only 'pending' items can be rejected."
                    )
                conn.execute(
                    _UPDATE_REJECT,
                    (rejection_reason, rejection_reason_english, reviewed_at, review_id),
                )
                updated_row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
        return _row_to_item(updated_row)

    # ── Read operations ───────────────────────────────────────────────────────

    def get_pending(self, review_id: Optional[str] = None) -> List[ReviewItem]:
        """
        Return pending items.

        When *review_id* is provided, return a list containing that specific
        item (empty list if not found or not pending).
        When *review_id* is None, return all pending items ordered by
        submitted_at ascending.
        """
        with self._lock:
            with self._connect() as conn:
                if review_id is not None:
                    row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
                    if row and row["status"] == ReviewStatus.pending.value:
                        return [_row_to_item(row)]
                    return []
                rows = conn.execute(_SELECT_PENDING).fetchall()
        return [_row_to_item(r) for r in rows]

    def get_item(self, review_id: str) -> Optional[ReviewItem]:
        """Return any item by review_id regardless of status."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(_SELECT_BY_ID, (review_id,)).fetchone()
        return _row_to_item(row) if row else None

    def get_by_session(self, session_id: str) -> Optional[ReviewItem]:
        """Return the most recent review item for a given session_id."""
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(_SELECT_BY_SESSION, (session_id,)).fetchone()
        return _row_to_item(row) if row else None

    def pending_count(self) -> int:
        """Return the number of items currently in 'pending' status."""
        with self._lock:
            with self._connect() as conn:
                result = conn.execute(
                    "SELECT COUNT(*) FROM hitl_queue WHERE status = 'pending';"
                ).fetchone()
        return result[0] if result else 0

    def clear(self) -> None:
        """Remove all items. Intended for testing only."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(_DELETE_ALL)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────────────────────────────────────

_queue: Optional[HITLQueue] = None
_queue_lock = threading.Lock()


def get_queue() -> HITLQueue:
    """
    Return the application-wide HITLQueue singleton.

    Uses ``settings.hitl_db_path`` for the backing store; this means the queue
    survives FastAPI server restarts when HITL_DB_PATH points to a file.

    Thread-safe double-checked initialisation.
    """
    global _queue
    if _queue is None:
        with _queue_lock:
            if _queue is None:
                _queue = HITLQueue()
    return _queue
