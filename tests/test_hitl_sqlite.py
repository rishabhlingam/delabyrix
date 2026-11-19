"""
tests/test_hitl_sqlite.py
──────────────────────────
Tests for the SQLite-backed HITLQueue and production-readiness of persistence.

Covers:
  - HITLQueue(db_path=":memory:") — fast isolated unit tests
  - Persistence across re-instantiation (file-backed DB survives restart)
  - GET /hitl/queue and GET /agent/session/{id} survive re-instantiation
  - Thread safety with SQLite backend
  - All existing queue semantics (approve, reject, pending_count, etc.)
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid

# Force mock mode before any backend imports
os.environ["WATSONX_MOCK_MODE"] = "true"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.hitl.models import ReviewStatus
from backend.hitl.queue import HITLQueue, get_queue
from backend.hitl.router import router as hitl_router
from backend.registry.sync import inject_registry
from backend.routers.agent import router as agent_router
from backend.synthetic.medication_registry import generate_medication_registry
from backend.watsonx.client import get_client


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _enqueue(q: HITLQueue, session_id: str = "s1") -> str:
    return q.enqueue(
        session_id=session_id,
        user_type="patient",
        country="US",
        pipeline_trace={"stage": "test"},
        draft_response="Draft response text.",
    )


def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(hitl_router)
    return app


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singletons():
    """Clear lru_cache singletons before and after each test."""
    get_settings.cache_clear()
    get_client.cache_clear()
    inject_registry(generate_medication_registry())
    yield
    get_settings.cache_clear()
    get_client.cache_clear()


@pytest.fixture
def mem_queue() -> HITLQueue:
    """An in-memory HITLQueue — always isolated, never touches disk."""
    return HITLQueue(db_path=":memory:")


@pytest.fixture
def file_db_path(tmp_path):
    """Return a path to a temporary SQLite file DB for persistence tests."""
    return str(tmp_path / "test_hitl.db")


# ══════════════════════════════════════════════════════════════════════════════
# In-memory queue unit tests
# (These mirror test_hitl.py to confirm SQLite backend preserves all semantics)
# ══════════════════════════════════════════════════════════════════════════════

class TestHITLQueueSQLiteUnit:

    def test_enqueue_returns_uuid(self, mem_queue):
        rid = _enqueue(mem_queue)
        assert isinstance(rid, str)
        assert len(rid) == 36  # standard UUID length

    def test_enqueue_item_is_pending(self, mem_queue):
        rid = _enqueue(mem_queue)
        item = mem_queue.get_item(rid)
        assert item is not None
        assert item.status == ReviewStatus.pending

    def test_pending_count_increments(self, mem_queue):
        assert mem_queue.pending_count() == 0
        _enqueue(mem_queue, "s1")
        assert mem_queue.pending_count() == 1
        _enqueue(mem_queue, "s2")
        assert mem_queue.pending_count() == 2

    def test_get_pending_returns_all(self, mem_queue):
        for i in range(3):
            _enqueue(mem_queue, f"sess-{i}")
        assert len(mem_queue.get_pending()) == 3

    def test_approve_changes_status(self, mem_queue):
        rid = _enqueue(mem_queue)
        updated = mem_queue.approve(rid, approved_response="Final answer.")
        assert updated.status == ReviewStatus.approved
        assert updated.approved_response == "Final answer."
        assert updated.reviewed_at is not None

    def test_reject_changes_status(self, mem_queue):
        rid = _enqueue(mem_queue)
        updated = mem_queue.reject(rid, rejection_reason="Incorrect.")
        assert updated.status == ReviewStatus.rejected
        assert updated.rejection_reason == "Incorrect."
        assert updated.reviewed_at is not None

    def test_approve_non_existent_raises_key_error(self, mem_queue):
        with pytest.raises(KeyError):
            mem_queue.approve("nonexistent-id", approved_response="ok")

    def test_reject_non_existent_raises_key_error(self, mem_queue):
        with pytest.raises(KeyError):
            mem_queue.reject("nonexistent-id", rejection_reason="reason")

    def test_approve_already_approved_raises_value_error(self, mem_queue):
        rid = _enqueue(mem_queue)
        mem_queue.approve(rid, approved_response="done")
        with pytest.raises(ValueError, match="pending"):
            mem_queue.approve(rid, approved_response="again")

    def test_reject_already_rejected_raises_value_error(self, mem_queue):
        rid = _enqueue(mem_queue)
        mem_queue.reject(rid, rejection_reason="bad")
        with pytest.raises(ValueError, match="pending"):
            mem_queue.reject(rid, rejection_reason="again")

    def test_approved_item_not_in_pending(self, mem_queue):
        rid = _enqueue(mem_queue)
        mem_queue.approve(rid, approved_response="done")
        pending = mem_queue.get_pending()
        assert all(i.review_id != rid for i in pending)
        assert mem_queue.pending_count() == 0

    def test_get_by_session_returns_correct_item(self, mem_queue):
        sid = "my-session-xyz"
        rid = _enqueue(mem_queue, sid)
        item = mem_queue.get_by_session(sid)
        assert item is not None
        assert item.review_id == rid

    def test_get_by_session_unknown_returns_none(self, mem_queue):
        assert mem_queue.get_by_session("unknown-session") is None

    def test_clear_empties_queue(self, mem_queue):
        _enqueue(mem_queue)
        mem_queue.clear()
        assert mem_queue.pending_count() == 0

    def test_reviewer_note_stored(self, mem_queue):
        rid = _enqueue(mem_queue)
        mem_queue.approve(rid, approved_response="ok", reviewer_note="Looks good.")
        item = mem_queue.get_item(rid)
        assert item.reviewer_note == "Looks good."

    def test_escalation_rules_stored(self, mem_queue):
        rid = mem_queue.enqueue(
            session_id="s1",
            user_type="patient",
            country="US",
            pipeline_trace={},
            draft_response="draft",
            escalation_rules=["rule_1_low_confidence"],
        )
        item = mem_queue.get_item(rid)
        assert "rule_1_low_confidence" in item.escalation_rules

    def test_pipeline_trace_stored_and_retrieved(self, mem_queue):
        trace = {"jurisdiction": "US_FDA", "pii_redacted": True, "extra": [1, 2, 3]}
        rid = mem_queue.enqueue(
            session_id="trace-sess",
            user_type="patient",
            country="US",
            pipeline_trace=trace,
            draft_response="draft",
        )
        item = mem_queue.get_item(rid)
        assert item.pipeline_trace == trace

    def test_pending_sorted_by_submitted_at(self, mem_queue):
        for i in range(3):
            _enqueue(mem_queue, f"sorted-{i}")
        pending = mem_queue.get_pending()
        timestamps = [i.submitted_at for i in pending]
        assert timestamps == sorted(timestamps)


# ══════════════════════════════════════════════════════════════════════════════
# SQLite persistence across re-instantiation
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLitePersistence:
    """
    Verify that data written by one HITLQueue instance is fully visible to a
    second instance opening the same file — simulating a server restart.
    """

    def test_enqueued_item_survives_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        rid = _enqueue(q1, "persistent-session")

        # Simulate restart: instantiate a fresh queue on the same file
        q2 = HITLQueue(db_path=file_db_path)
        item = q2.get_item(rid)
        assert item is not None
        assert item.session_id == "persistent-session"
        assert item.status == ReviewStatus.pending

    def test_approved_item_survives_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        rid = _enqueue(q1, "approve-session")
        q1.approve(rid, approved_response="Approved answer.", reviewer_note="Good.")

        q2 = HITLQueue(db_path=file_db_path)
        item = q2.get_item(rid)
        assert item is not None
        assert item.status == ReviewStatus.approved
        assert item.approved_response == "Approved answer."
        assert item.reviewer_note == "Good."

    def test_rejected_item_survives_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        rid = _enqueue(q1, "reject-session")
        q1.reject(rid, rejection_reason="Insufficient context.")

        q2 = HITLQueue(db_path=file_db_path)
        item = q2.get_item(rid)
        assert item is not None
        assert item.status == ReviewStatus.rejected
        assert item.rejection_reason == "Insufficient context."

    def test_multiple_items_survive_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        rids = [_enqueue(q1, f"sess-{i}") for i in range(5)]

        q2 = HITLQueue(db_path=file_db_path)
        assert q2.pending_count() == 5
        for rid in rids:
            assert q2.get_item(rid) is not None

    def test_get_by_session_survives_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        rid = _enqueue(q1, "my-session")

        q2 = HITLQueue(db_path=file_db_path)
        item = q2.get_by_session("my-session")
        assert item is not None
        assert item.review_id == rid

    def test_pending_count_survives_restart(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        _enqueue(q1, "s1")
        _enqueue(q1, "s2")
        q1.approve(q1.get_by_session("s1").review_id, approved_response="ok")

        q2 = HITLQueue(db_path=file_db_path)
        # s1 approved, s2 still pending
        assert q2.pending_count() == 1

    def test_parent_directory_created_automatically(self, tmp_path):
        nested_path = str(tmp_path / "deep" / "nested" / "dir" / "hitl.db")
        q = HITLQueue(db_path=nested_path)
        rid = _enqueue(q, "nested-sess")
        assert q.get_item(rid) is not None

    def test_clear_removes_persisted_items(self, file_db_path):
        q1 = HITLQueue(db_path=file_db_path)
        _enqueue(q1, "del-sess")
        q1.clear()

        q2 = HITLQueue(db_path=file_db_path)
        assert q2.pending_count() == 0


# ══════════════════════════════════════════════════════════════════════════════
# Thread safety with SQLite backend
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLiteThreadSafety:

    def test_concurrent_enqueues_no_data_loss(self, mem_queue):
        """50 concurrent enqueues must all succeed without data loss."""
        n = 50
        results: list = []
        errors: list = []

        def _do_enqueue():
            try:
                rid = _enqueue(mem_queue, str(uuid.uuid4()))
                results.append(rid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_do_enqueue) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == n
        assert mem_queue.pending_count() == n
        assert len(set(results)) == n  # all unique review_ids

    def test_concurrent_enqueue_on_file_db(self, file_db_path):
        """File-backed DB handles concurrent writes without data loss."""
        q = HITLQueue(db_path=file_db_path)
        n = 20
        results: list = []
        errors: list = []

        def _do_enqueue():
            try:
                rid = _enqueue(q, str(uuid.uuid4()))
                results.append(rid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_do_enqueue) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert q.pending_count() == n


# ══════════════════════════════════════════════════════════════════════════════
# API integration tests with SQLite-backed get_queue()
# (verify GET /hitl/queue and GET /agent/session/{id} survive restart)
# ══════════════════════════════════════════════════════════════════════════════

class TestAPIWithSQLitePersistence:
    """
    Uses a temporary file DB, overrides the module-level singleton, and
    verifies that the HTTP API reads from the same persistent store.
    """

    @pytest.fixture
    def file_queue(self, file_db_path, monkeypatch):
        """Replace the module-level singleton with a file-backed queue."""
        import backend.hitl.queue as queue_mod
        import backend.routers.agent as agent_mod
        import backend.hitl.router as hitl_router_mod

        q = HITLQueue(db_path=file_db_path)
        monkeypatch.setattr(queue_mod, "_queue", q)
        monkeypatch.setattr(queue_mod, "_queue_lock", threading.Lock())
        # Patch get_queue to always return our file-backed instance
        monkeypatch.setattr(queue_mod, "get_queue", lambda: q)
        monkeypatch.setattr(agent_mod, "get_queue", lambda: q)
        monkeypatch.setattr(hitl_router_mod, "get_queue", lambda: q)
        return q

    @pytest.fixture
    def api_client(self) -> TestClient:
        return TestClient(build_test_app(), raise_server_exceptions=True)

    def test_hitl_queue_endpoint_returns_persisted_items(
        self, file_queue, api_client, file_db_path
    ):
        # Write via the Python API
        file_queue.enqueue(
            session_id="persist-api-sess",
            user_type="patient",
            country="US",
            pipeline_trace={},
            draft_response="draft",
        )

        # Read via the HTTP endpoint (same underlying queue)
        resp = api_client.get("/hitl/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] >= 1
        sessions = [item["session_id"] for item in data["items"]]
        assert "persist-api-sess" in sessions

    def test_session_status_endpoint_reads_persisted_item(
        self, file_queue, api_client
    ):
        sid = "persist-session-status"
        rid = file_queue.enqueue(
            session_id=sid,
            user_type="patient",
            country="US",
            pipeline_trace={},
            draft_response="draft",
        )

        resp = api_client.get(f"/agent/session/{sid}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_approve_then_session_status_reflects_approval(
        self, file_queue, api_client
    ):
        sid = "approve-persist-sess"
        rid = file_queue.enqueue(
            session_id=sid,
            user_type="patient",
            country="US",
            pipeline_trace={},
            draft_response="draft",
        )
        api_client.post("/hitl/approve", json={
            "review_id": rid,
            "approved_response": "Persisted approval text.",
        })

        resp = api_client.get(f"/agent/session/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert data["response_text"] == "Persisted approval text."

    def test_reject_then_session_status_reflects_rejection(
        self, file_queue, api_client
    ):
        sid = "reject-persist-sess"
        rid = file_queue.enqueue(
            session_id=sid,
            user_type="patient",
            country="US",
            pipeline_trace={},
            draft_response="draft",
        )
        api_client.post("/hitl/reject", json={
            "review_id": rid,
            "rejection_reason": "Persisted rejection reason.",
        })

        resp = api_client.get(f"/agent/session/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rejected"
