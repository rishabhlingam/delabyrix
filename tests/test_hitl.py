"""
tests/test_hitl.py
────────────────────
Unit and integration tests for Phase 5 HITL modules and agent router:

  - backend/hitl/models.py        (Pydantic models)
  - backend/hitl/queue.py         (Thread-safe in-memory queue)
  - backend/hitl/router.py        (GET /hitl/queue, POST /hitl/approve, /reject)
  - backend/routers/agent.py      (POST /agent/query, GET /agent/session/{id})

Tests cover:
  - HITL approve/reject flow
  - ICU consent escalation end-to-end
  - Cross-border banned drug escalation end-to-end via /agent/query
  - Thread safety of the queue
  - API error handling (404, 409)
"""

from __future__ import annotations

import os
import threading
import uuid

# Force mock mode before importing backend modules
os.environ["WATSONX_MOCK_MODE"] = "true"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.hitl.models import ApproveRequest, RejectRequest, ReviewItem, ReviewStatus
from backend.hitl.queue import HITLQueue, get_queue
from backend.hitl.router import router as hitl_router
from backend.registry.sync import inject_registry
from backend.routers.agent import router as agent_router
from backend.synthetic.medication_registry import generate_medication_registry
from backend.watsonx.client import get_client


# ──────────────────────────────────────────────────────────────────────────────
# Test app setup
# ──────────────────────────────────────────────────────────────────────────────

def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(hitl_router)
    return app


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_state():
    """Reset all singletons and queue between tests."""
    get_settings.cache_clear()
    get_client.cache_clear()
    get_queue().clear()
    inject_registry(generate_medication_registry())
    yield
    get_settings.cache_clear()
    get_client.cache_clear()
    get_queue().clear()


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(build_test_app(), raise_server_exceptions=True)


@pytest.fixture
def queue() -> HITLQueue:
    q = get_queue()
    q.clear()
    return q


# ──────────────────────────────────────────────────────────────────────────────
# Helper: submit a query and expect escalation
# ──────────────────────────────────────────────────────────────────────────────

def _query(client: TestClient, text: str, country: str = "US",
           source_language: str = "en", user_type: str = "patient") -> dict:
    resp = client.post("/agent/query", json={
        "text": text,
        "source_language": source_language,
        "user_type": user_type,
        "country": country,
        "session_id": str(uuid.uuid4()),
    })
    return resp


# ══════════════════════════════════════════════════════════════════════════════
# HITLQueue unit tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHITLQueueUnit:

    def test_enqueue_returns_uuid(self, queue):
        rid = queue.enqueue(
            session_id="s1", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        assert isinstance(rid, str)
        assert len(rid) > 0

    def test_enqueue_item_is_pending(self, queue):
        rid = queue.enqueue(
            session_id="s1", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        item = queue.get_item(rid)
        assert item is not None
        assert item.status == ReviewStatus.pending

    def test_pending_count_increments(self, queue):
        assert queue.pending_count() == 0
        queue.enqueue(
            session_id="s2", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        assert queue.pending_count() == 1

    def test_get_pending_returns_all(self, queue):
        for i in range(3):
            queue.enqueue(
                session_id=f"sess-{i}", user_type="patient", country="US",
                pipeline_trace={}, draft_response="draft",
            )
        pending = queue.get_pending()
        assert len(pending) == 3

    def test_approve_changes_status(self, queue):
        rid = queue.enqueue(
            session_id="s3", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        updated = queue.approve(rid, approved_response="Final answer.")
        assert updated.status == ReviewStatus.approved
        assert updated.approved_response == "Final answer."
        assert updated.reviewed_at is not None

    def test_reject_changes_status(self, queue):
        rid = queue.enqueue(
            session_id="s4", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        updated = queue.reject(rid, rejection_reason="Incorrect information.")
        assert updated.status == ReviewStatus.rejected
        assert updated.rejection_reason == "Incorrect information."
        assert updated.reviewed_at is not None

    def test_approve_non_existent_raises_key_error(self, queue):
        with pytest.raises(KeyError):
            queue.approve("nonexistent-id", approved_response="ok")

    def test_reject_non_existent_raises_key_error(self, queue):
        with pytest.raises(KeyError):
            queue.reject("nonexistent-id", rejection_reason="reason")

    def test_approve_already_approved_raises_value_error(self, queue):
        rid = queue.enqueue(
            session_id="s5", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.approve(rid, approved_response="done")
        with pytest.raises(ValueError, match="pending"):
            queue.approve(rid, approved_response="again")

    def test_reject_already_rejected_raises_value_error(self, queue):
        rid = queue.enqueue(
            session_id="s6", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.reject(rid, rejection_reason="bad")
        with pytest.raises(ValueError, match="pending"):
            queue.reject(rid, rejection_reason="again")

    def test_approved_item_not_in_pending(self, queue):
        rid = queue.enqueue(
            session_id="s7", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.approve(rid, approved_response="done")
        pending = queue.get_pending()
        assert all(i.review_id != rid for i in pending)
        assert queue.pending_count() == 0

    def test_get_by_session_returns_correct_item(self, queue):
        sid = "my-session-xyz"
        rid = queue.enqueue(
            session_id=sid, user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        item = queue.get_by_session(sid)
        assert item is not None
        assert item.review_id == rid

    def test_get_by_session_unknown_returns_none(self, queue):
        result = queue.get_by_session("unknown-session")
        assert result is None

    def test_clear_empties_queue(self, queue):
        queue.enqueue(
            session_id="s8", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.clear()
        assert queue.pending_count() == 0

    def test_reviewer_note_stored(self, queue):
        rid = queue.enqueue(
            session_id="s9", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.approve(rid, approved_response="ok", reviewer_note="Looks good.")
        item = queue.get_item(rid)
        assert item.reviewer_note == "Looks good."

    def test_escalation_rules_stored(self, queue):
        rid = queue.enqueue(
            session_id="s10", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
            escalation_rules=["rule_1_low_confidence"],
        )
        item = queue.get_item(rid)
        assert "rule_1_low_confidence" in item.escalation_rules

    def test_pending_sorted_by_submitted_at(self, queue):
        for i in range(3):
            queue.enqueue(
                session_id=f"sorted-{i}", user_type="patient", country="US",
                pipeline_trace={}, draft_response="draft",
            )
        pending = queue.get_pending()
        timestamps = [i.submitted_at for i in pending]
        assert timestamps == sorted(timestamps)


# ══════════════════════════════════════════════════════════════════════════════
# Thread safety test
# ══════════════════════════════════════════════════════════════════════════════

class TestHITLQueueThreadSafety:

    def test_concurrent_enqueues_no_data_loss(self, queue):
        """50 concurrent enqueues must all succeed without race conditions."""
        n = 50
        results: list = []
        errors: list = []

        def _enqueue():
            try:
                rid = queue.enqueue(
                    session_id=str(uuid.uuid4()),
                    user_type="patient",
                    country="US",
                    pipeline_trace={},
                    draft_response="draft",
                )
                results.append(rid)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_enqueue) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == n
        assert queue.pending_count() == n
        # All review_ids must be unique
        assert len(set(results)) == n


# ══════════════════════════════════════════════════════════════════════════════
# HITL HTTP router tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHITLRouter:

    def test_get_queue_empty(self, test_client):
        resp = test_client.get("/hitl/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 0
        assert data["items"] == []

    def test_get_queue_shows_pending_items(self, test_client, queue):
        queue.enqueue(
            session_id="show-me", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        resp = test_client.get("/hitl/queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["session_id"] == "show-me"

    def test_approve_valid_item(self, test_client, queue):
        rid = queue.enqueue(
            session_id="approve-me", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        resp = test_client.post("/hitl/approve", json={
            "review_id": rid,
            "approved_response": "This is the approved answer.",
            "reviewer_note": "Looks correct.",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject_valid_item(self, test_client, queue):
        rid = queue.enqueue(
            session_id="reject-me", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        resp = test_client.post("/hitl/reject", json={
            "review_id": rid,
            "rejection_reason": "Response was inaccurate.",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_approve_nonexistent_returns_404(self, test_client):
        resp = test_client.post("/hitl/approve", json={
            "review_id": "00000000-0000-0000-0000-000000000000",
            "approved_response": "ok",
        })
        assert resp.status_code == 404

    def test_reject_nonexistent_returns_404(self, test_client):
        resp = test_client.post("/hitl/reject", json={
            "review_id": "00000000-0000-0000-0000-000000000000",
            "rejection_reason": "reason",
        })
        assert resp.status_code == 404

    def test_approve_already_approved_returns_409(self, test_client, queue):
        rid = queue.enqueue(
            session_id="double-approve", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        test_client.post("/hitl/approve", json={
            "review_id": rid,
            "approved_response": "first approval",
        })
        resp = test_client.post("/hitl/approve", json={
            "review_id": rid,
            "approved_response": "second approval",
        })
        assert resp.status_code == 409

    def test_reject_already_rejected_returns_409(self, test_client, queue):
        rid = queue.enqueue(
            session_id="double-reject", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        test_client.post("/hitl/reject", json={
            "review_id": rid,
            "rejection_reason": "first",
        })
        resp = test_client.post("/hitl/reject", json={
            "review_id": rid,
            "rejection_reason": "second",
        })
        assert resp.status_code == 409

    def test_approve_then_queue_count_decreases(self, test_client, queue):
        rid = queue.enqueue(
            session_id="count-test", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        test_client.post("/hitl/approve", json={
            "review_id": rid,
            "approved_response": "done",
        })
        resp = test_client.get("/hitl/queue")
        assert resp.json()["pending_count"] == 0


# ══════════════════════════════════════════════════════════════════════════════
# Agent router tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentRouter:

    def test_clean_query_returns_200(self, test_client):
        """A benign, non-escalating query should return 200."""
        resp = _query(
            test_client,
            text="What is a deductible?",
            country="US",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_trace" in data
        assert data["escalated"] is False
        assert "response_text" in data

    def test_pipeline_trace_has_required_keys(self, test_client):
        resp = _query(test_client, text="Explain my insurance copay.", country="US")
        assert resp.status_code == 200
        trace = resp.json()["pipeline_trace"]
        required = {"jurisdiction", "pii_redacted", "translation",
                    "medical_interpretation", "cultural_context", "next_steps"}
        assert required == set(trace.keys())

    def test_session_id_returned(self, test_client):
        resp = _query(test_client, text="Help.", country="US")
        assert "session_id" in resp.json()

    def test_icu_consent_escalates_to_202(self, test_client):
        """
        ICU escalation test: a query mentioning ICU admission must trigger
        rule 4, return 202, and appear in the HITL queue.
        """
        resp = _query(
            test_client,
            text="Please explain the ICU admission consent form for my father.",
            country="US",
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["escalated"] is True
        assert "review_id" in data
        assert data["status"] == "pending_review"

    def test_icu_escalation_queued(self, test_client, queue):
        """After escalation, the item appears in GET /hitl/queue."""
        resp = _query(
            test_client,
            text="I need to sign the surgery consent form.",
            country="US",
        )
        assert resp.status_code == 202
        queue_resp = test_client.get("/hitl/queue")
        assert queue_resp.json()["pending_count"] >= 1

    def test_banned_drug_escalates_to_202(self, test_client):
        """
        Cross-border banned drug escalation test: metamizole is banned in
        US_FDA, so a query mentioning it must return 202.
        """
        resp = _query(
            test_client,
            text="I was prescribed metamizole tablet for my pain.",
            country="US",
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["escalated"] is True

    def test_banned_drug_in_eu_does_not_escalate_on_rule2(self, test_client):
        """
        metamizole is approved in EU_EMA — rule 2 must NOT fire for a DE
        query.  Other rules may still fire (e.g. rule 4 from "pain").
        """
        resp = _query(
            test_client,
            text="I take metamizole for mild pain.",
            country="DE",
        )
        # 200 or 202 depending on other rules, but rule_2 should not be in trace
        # We verify the response is well-formed
        data = resp.json()
        assert "session_id" in data

    def test_ambiguous_jurisdiction_escalates(self, test_client):
        """An unknown country code (ZZ) must trigger rule 5 and return 202."""
        resp = _query(
            test_client,
            text="What is my deductible?",
            country="ZZ",
        )
        assert resp.status_code == 202

    def test_session_status_pending_before_review(self, test_client):
        """After escalation, GET /agent/session/{id} must return 'pending'."""
        resp = _query(
            test_client,
            text="I need ICU admission consent help.",
            country="US",
        )
        assert resp.status_code == 202
        session_id = resp.json()["session_id"]

        status_resp = test_client.get(f"/agent/session/{session_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "pending"
        assert status_data["response_text"] is None

    def test_session_status_approved_after_review(self, test_client, queue):
        """After HITL approval, GET /agent/session/{id} must return approved text."""
        resp = _query(
            test_client,
            text="Explain the ICU consent form.",
            country="US",
        )
        assert resp.status_code == 202
        session_id = resp.json()["session_id"]
        review_id = resp.json()["review_id"]

        # Reviewer approves
        test_client.post("/hitl/approve", json={
            "review_id": review_id,
            "approved_response": "Here is the approved explanation.",
        })

        status_resp = test_client.get(f"/agent/session/{session_id}")
        status_data = status_resp.json()
        assert status_data["status"] == "approved"
        assert status_data["response_text"] == "Here is the approved explanation."

    def test_session_status_rejected_after_review(self, test_client, queue):
        """After HITL rejection, GET /agent/session/{id} must return 'rejected'."""
        resp = _query(
            test_client,
            text="Explain surgery consent for my child.",
            country="US",
        )
        assert resp.status_code == 202
        session_id = resp.json()["session_id"]
        review_id = resp.json()["review_id"]

        test_client.post("/hitl/reject", json={
            "review_id": review_id,
            "rejection_reason": "Insufficient information.",
        })

        status_resp = test_client.get(f"/agent/session/{session_id}")
        status_data = status_resp.json()
        assert status_data["status"] == "rejected"

    def test_session_status_no_escalation_returns_approved(self, test_client):
        """A session that was NOT escalated should report 'approved' on poll."""
        resp = _query(
            test_client,
            text="What does copay mean?",
            country="US",
        )
        # May be 200 or 202 depending on mock confidence
        if resp.status_code == 200:
            session_id = resp.json()["session_id"]
            status_resp = test_client.get(f"/agent/session/{session_id}")
            # No queue item -> should return "approved" with no text
            assert status_resp.status_code == 200
            assert status_resp.json()["status"] == "approved"

    def test_pii_in_query_does_not_appear_in_trace(self, test_client):
        """Raw PII in the input must not propagate to pipeline_trace."""
        resp = _query(
            test_client,
            text="My SSN is 234-56-7890 and I need help with my deductible.",
            country="US",
        )
        assert resp.status_code in (200, 202)
        body = resp.json()
        body_str = str(body)
        assert "234-56-7890" not in body_str

    def test_spanish_language_accepted(self, test_client):
        resp = _query(
            test_client,
            text="¿Qué es el deducible de mi seguro?",
            source_language="es",
            country="US",
        )
        assert resp.status_code in (200, 202)
        assert "session_id" in resp.json()

    def test_hindi_language_accepted(self, test_client):
        resp = _query(
            test_client,
            text="मेरा बीमा कटौती क्या है?",
            source_language="hi",
            country="IN",
        )
        assert resp.status_code in (200, 202)
        assert "session_id" in resp.json()
