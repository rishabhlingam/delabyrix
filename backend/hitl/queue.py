"""
backend/hitl/queue.py
──────────────────────
Thread-safe in-memory HITL review queue.

Architecture note (architecture.md §12):
  "In-memory list (MVP) — Simplest viable; documented upgrade path to Redis
  for production."

The queue is a module-level singleton protected by a threading.Lock so it is
safe to use from FastAPI's default threadpool workers.

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

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.hitl.models import ReviewItem, ReviewStatus


class HITLQueue:
    """
    Thread-safe in-memory HITL review queue.

    All public methods acquire the internal lock so they are safe to call
    from concurrent FastAPI request handlers.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, ReviewItem] = {}  # review_id -> ReviewItem

    # ── Write operations ──────────────────────────────────────────────────────

    def enqueue(
        self,
        session_id: str,
        user_type: str,
        country: str,
        pipeline_trace: Dict[str, Any],
        draft_response: str,
        escalation_rules: Optional[List[str]] = None,
    ) -> str:
        """
        Add a new item to the queue.

        Parameters
        ──────────
        session_id       : Session UUID from the agent request.
        user_type        : "patient" | "provider" | "coordinator".
        country          : ISO 3166-1 alpha-2 country code.
        pipeline_trace   : Stage outputs dict (no raw PII).
        draft_response   : Draft response text for the reviewer.
        escalation_rules : List of triggered rule labels.

        Returns
        ───────
        review_id (UUID string) for the new queue item.
        """
        review_id = str(uuid.uuid4())
        item = ReviewItem(
            review_id=review_id,
            session_id=session_id,
            submitted_at=datetime.now(tz=timezone.utc),
            user_type=user_type,
            country=country,
            pipeline_trace=pipeline_trace,
            draft_response=draft_response,
            escalation_rules=escalation_rules or [],
            status=ReviewStatus.pending,
        )
        with self._lock:
            self._items[review_id] = item
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
        with self._lock:
            item = self._items.get(review_id)
            if item is None:
                raise KeyError(f"review_id not found: {review_id!r}")
            if item.status != ReviewStatus.pending:
                raise ValueError(
                    f"Cannot approve item with status={item.status!r}. "
                    "Only 'pending' items can be approved."
                )
            updated = item.model_copy(update={
                "status": ReviewStatus.approved,
                "approved_response": approved_response,
                "reviewer_note": reviewer_note,
                "reviewed_at": datetime.now(tz=timezone.utc),
            })
            self._items[review_id] = updated
        return updated

    def reject(self, review_id: str, rejection_reason: str) -> ReviewItem:
        """
        Mark a pending item as rejected.

        Raises
        ──────
        KeyError  — when *review_id* does not exist.
        ValueError — when item is not in 'pending' status.
        """
        with self._lock:
            item = self._items.get(review_id)
            if item is None:
                raise KeyError(f"review_id not found: {review_id!r}")
            if item.status != ReviewStatus.pending:
                raise ValueError(
                    f"Cannot reject item with status={item.status!r}. "
                    "Only 'pending' items can be rejected."
                )
            updated = item.model_copy(update={
                "status": ReviewStatus.rejected,
                "rejection_reason": rejection_reason,
                "reviewed_at": datetime.now(tz=timezone.utc),
            })
            self._items[review_id] = updated
        return updated

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
            if review_id is not None:
                item = self._items.get(review_id)
                if item and item.status == ReviewStatus.pending:
                    return [item]
                return []
            return sorted(
                (i for i in self._items.values() if i.status == ReviewStatus.pending),
                key=lambda i: i.submitted_at,
            )

    def get_item(self, review_id: str) -> Optional[ReviewItem]:
        """Return any item by review_id regardless of status."""
        with self._lock:
            return self._items.get(review_id)

    def get_by_session(self, session_id: str) -> Optional[ReviewItem]:
        """Return the most recent review item for a given session_id."""
        with self._lock:
            matches = [
                i for i in self._items.values() if i.session_id == session_id
            ]
        if not matches:
            return None
        return max(matches, key=lambda i: i.submitted_at)

    def pending_count(self) -> int:
        """Return the number of items currently in 'pending' status."""
        with self._lock:
            return sum(
                1 for i in self._items.values() if i.status == ReviewStatus.pending
            )

    def clear(self) -> None:
        """Remove all items. Intended for testing only."""
        with self._lock:
            self._items.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────────────────────────────────────

_queue: Optional[HITLQueue] = None
_queue_lock = threading.Lock()


def get_queue() -> HITLQueue:
    """
    Return the application-wide HITLQueue singleton.

    Thread-safe double-checked initialisation.
    """
    global _queue
    if _queue is None:
        with _queue_lock:
            if _queue is None:
                _queue = HITLQueue()
    return _queue
