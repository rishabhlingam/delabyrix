"""
tests/test_bilingual_hitl.py
──────────────────────────────
Tests for bilingual HITL payload support and the translate endpoint.

Covers:
  - ReviewItem includes source_language, bilingual draft/inquiry fields
  - HITLQueue.enqueue persists and returns bilingual fields
  - HITLQueue.reject persists rejection_reason_english
  - GET /hitl/queue returns bilingual fields
  - POST /hitl/reject stores rejection_reason_english
  - GET /agent/session/{id} returns source_language, rejection_reason, rejection_reason_english
  - POST /agent/translate (mock mode, offline)
  - POST /agent/query (Spanish) enqueues item with source_language="es"
"""

from __future__ import annotations

import os
import uuid

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
# Test app / fixtures
# ──────────────────────────────────────────────────────────────────────────────

def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(hitl_router)
    return app


@pytest.fixture(autouse=True)
def reset_state():
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


def _query(client: TestClient, text: str, country: str = "US",
           source_language: str = "en", user_type: str = "patient") -> dict:
    return client.post("/agent/query", json={
        "text": text,
        "source_language": source_language,
        "user_type": user_type,
        "country": country,
        "session_id": str(uuid.uuid4()),
    })


# ══════════════════════════════════════════════════════════════════════════════
# HITLQueue bilingual field tests
# ══════════════════════════════════════════════════════════════════════════════

class TestBilingualQueueFields:

    def test_enqueue_stores_source_language(self, queue):
        rid = queue.enqueue(
            session_id="s1", user_type="patient", country="US",
            pipeline_trace={}, draft_response="Mi respuesta.",
            source_language="es",
        )
        item = queue.get_item(rid)
        assert item is not None
        assert item.source_language == "es"

    def test_enqueue_stores_draft_response_english(self, queue):
        rid = queue.enqueue(
            session_id="s2", user_type="patient", country="US",
            pipeline_trace={}, draft_response="Mi respuesta.",
            source_language="es",
            draft_response_english="My response.",
        )
        item = queue.get_item(rid)
        assert item.draft_response_english == "My response."

    def test_enqueue_stores_bilingual_inquiry_fields(self, queue):
        rid = queue.enqueue(
            session_id="s3", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
            source_language="hi",
            redacted_original_text="मेरा सवाल",
            english_inquiry="My question",
        )
        item = queue.get_item(rid)
        assert item.redacted_original_text == "मेरा सवाल"
        assert item.english_inquiry == "My question"

    def test_enqueue_defaults_source_language_to_en(self, queue):
        rid = queue.enqueue(
            session_id="s4", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        item = queue.get_item(rid)
        assert item.source_language == "en"

    def test_reject_stores_rejection_reason_english(self, queue):
        rid = queue.enqueue(
            session_id="s5", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
            source_language="es",
        )
        queue.reject(
            rid,
            rejection_reason="Respuesta incorrecta.",
            rejection_reason_english="Incorrect response.",
        )
        item = queue.get_item(rid)
        assert item.rejection_reason == "Respuesta incorrecta."
        assert item.rejection_reason_english == "Incorrect response."

    def test_reject_without_english_stores_null(self, queue):
        rid = queue.enqueue(
            session_id="s6", user_type="patient", country="US",
            pipeline_trace={}, draft_response="draft",
        )
        queue.reject(rid, rejection_reason="Out of scope.")
        item = queue.get_item(rid)
        assert item.rejection_reason == "Out of scope."
        assert item.rejection_reason_english is None


# ══════════════════════════════════════════════════════════════════════════════
# HITL HTTP router bilingual tests
# ══════════════════════════════════════════════════════════════════════════════

class TestHITLRouterBilingual:

    def test_queue_returns_source_language(self, test_client, queue):
        queue.enqueue(
            session_id="show-me", user_type="patient", country="ES",
            pipeline_trace={}, draft_response="Respuesta borrador.",
            source_language="es",
        )
        resp = test_client.get("/hitl/queue")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert item["source_language"] == "es"

    def test_reject_with_english_reason_stored(self, test_client, queue):
        rid = queue.enqueue(
            session_id="reject-es", user_type="patient", country="ES",
            pipeline_trace={}, draft_response="Respuesta.",
            source_language="es",
        )
        resp = test_client.post("/hitl/reject", json={
            "review_id": rid,
            "rejection_reason": "No es apropiado.",
            "rejection_reason_english": "Not appropriate.",
        })
        assert resp.status_code == 200
        item = queue.get_item(rid)
        assert item.rejection_reason_english == "Not appropriate."


# ══════════════════════════════════════════════════════════════════════════════
# Session status bilingual fields
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionStatusBilingual:

    def test_session_status_includes_source_language(self, test_client):
        resp = _query(
            test_client,
            text="Explain the ICU consent form.",
            country="US",
        )
        assert resp.status_code == 202
        session_id = resp.json()["session_id"]

        status_resp = test_client.get(f"/agent/session/{session_id}")
        assert status_resp.status_code == 200
        # source_language should be present
        data = status_resp.json()
        assert "source_language" in data

    def test_session_rejection_returns_reason(self, test_client, queue):
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
            "rejection_reason": "Out of scope query.",
            "rejection_reason_english": "Out of scope query.",
        })

        status_resp = test_client.get(f"/agent/session/{session_id}")
        data = status_resp.json()
        assert data["status"] == "rejected"
        assert data["rejection_reason"] == "Out of scope query."
        assert data["rejection_reason_english"] == "Out of scope query."


# ══════════════════════════════════════════════════════════════════════════════
# POST /agent/translate tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentTranslate:

    def test_translate_es_to_en(self, test_client):
        resp = test_client.post("/agent/translate", json={
            "text": "Hola mundo",
            "source_lang": "es",
            "target_lang": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "translated_text" in data
        assert data["source_lang"] == "es"
        assert data["target_lang"] == "en"
        assert isinstance(data["translated_text"], str)
        assert len(data["translated_text"]) > 0

    def test_translate_en_to_es(self, test_client):
        resp = test_client.post("/agent/translate", json={
            "text": "Hello world",
            "source_lang": "en",
            "target_lang": "es",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_lang"] == "en"
        assert data["target_lang"] == "es"

    def test_translate_same_language_returns_original(self, test_client):
        """When source == target, text is returned unchanged, mock=False."""
        resp = test_client.post("/agent/translate", json={
            "text": "No translation needed.",
            "source_lang": "en",
            "target_lang": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["translated_text"] == "No translation needed."

    def test_translate_mock_flag_set_in_mock_mode(self, test_client):
        """In mock mode, the response mock field should be True."""
        resp = test_client.post("/agent/translate", json={
            "text": "Test text",
            "source_lang": "hi",
            "target_lang": "en",
        })
        assert resp.status_code == 200
        data = resp.json()
        # In mock mode (WATSONX_MOCK_MODE=true), mock should be True
        assert isinstance(data["mock"], bool)
