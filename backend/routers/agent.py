"""
backend/routers/agent.py
──────────────────────────
FastAPI router for the agentic pipeline endpoints.

Endpoints
─────────
  POST /agent/query              — run the full pipeline (returns 200 or 202)
  GET  /agent/session/{session_id} — poll for escalated result status

Pipeline stages (in order)
──────────────────────────
  Stage 0 — PII redaction         (pii_redactor.py)
  Stage 1 — Translation           (translator.py)
  Stage 2 — Medical interpretation (medical_interpreter.py)
  Stage 3 — Cultural context      (cultural_context.py)
  Stage 4 — Next steps guide      (next_steps_guide.py)
  HITL    — Escalation evaluation  (hitl_escalator.py)

Matches API contracts in architecture.md §6.1.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from backend.hitl.queue import get_queue
from backend.jurisdiction.resolver import resolve
from backend.pipeline.cultural_context import add_cultural_context
from backend.pipeline.hitl_escalator import (
    EscalationInput,
    enqueue_if_escalated,
    evaluate_escalation,
)
from backend.pipeline.medical_interpreter import interpret
from backend.pipeline.next_steps_guide import generate_next_steps
from backend.pipeline.pii_redactor import redact
from backend.pipeline.translator import translate
from backend.watsonx.client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ──────────────────────────────────────────────────────────────────────────────
# Request / response models
# ──────────────────────────────────────────────────────────────────────────────

class AgentQueryRequest(BaseModel):
    text: str = Field(..., description="Raw user input (may contain PII)")
    source_language: str = Field(
        default="en",
        description="BCP-47 language code: 'en', 'es', 'hi'",
    )
    user_type: str = Field(
        default="patient",
        description="patient | provider | coordinator",
    )
    country: str = Field(
        default="US",
        description="ISO 3166-1 alpha-2 country code",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Client-generated UUID for session continuity (auto-generated if absent)",
    )


class PipelineTrace(BaseModel):
    jurisdiction: str
    pii_redacted: bool
    translation: str
    medical_interpretation: str
    cultural_context: str
    next_steps: str


class AgentQueryResponse(BaseModel):
    """200 OK — pipeline completed without escalation."""
    session_id: str
    pipeline_trace: PipelineTrace
    escalated: bool
    review_id: Optional[str]
    response_text: str


class AgentEscalatedResponse(BaseModel):
    """202 Accepted — query escalated for HITL review."""
    session_id: str
    escalated: bool
    review_id: str
    status: str
    message: str


class SessionStatusResponse(BaseModel):
    """Response for GET /agent/session/{session_id}."""
    session_id: str
    status: str                    # approved | pending | rejected
    response_text: Optional[str]
    source_language: Optional[str] = None
    rejection_reason: Optional[str] = None
    rejection_reason_english: Optional[str] = None


class TranslateRequest(BaseModel):
    """Request body for POST /agent/translate."""
    text: str = Field(..., description="Text to translate")
    source_lang: str = Field(..., description="BCP-47 source language code")
    target_lang: str = Field(..., description="BCP-47 target language code")


class TranslateResponse(BaseModel):
    """Response for POST /agent/translate."""
    translated_text: str
    source_lang: str
    target_lang: str
    mock: bool


# ──────────────────────────────────────────────────────────────────────────────
# Localised escalation messages
# ──────────────────────────────────────────────────────────────────────────────

_ESCALATION_MESSAGES: Dict[str, str] = {
    "en": (
        "Your request requires review by a clinical specialist. "
        "We will notify you once the review is complete. "
        "Please use your session ID to check the status."
    ),
    "es": (
        "Su solicitud requiere revisión por un especialista clínico. "
        "Le notificaremos cuando se complete la revisión. "
        "Por favor use su ID de sesión para verificar el estado."
    ),
    "hi": (
        "आपके अनुरोध की समीक्षा एक नैदानिक विशेषज्ञ द्वारा की जानी आवश्यक है। "
        "समीक्षा पूर्ण होने पर हम आपको सूचित करेंगे।"
    ),
}


def _escalation_message(language: str) -> str:
    return _ESCALATION_MESSAGES.get(language.lower(), _ESCALATION_MESSAGES["en"])


# ──────────────────────────────────────────────────────────────────────────────
# POST /agent/query
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/query",
    summary="Run the full agentic clinical pipeline",
)
def agent_query(body: AgentQueryRequest, response: Response):
    """
    Main entry point for the full agentic pipeline.

    Returns **200 OK** with the full pipeline trace when no escalation is
    needed, or **202 Accepted** with a review_id when HITL review is required.
    """
    session_id = body.session_id or str(uuid.uuid4())
    client = get_client()

    # ── Stage 0: PII Redaction ────────────────────────────────────────────────
    redaction = redact(body.text)
    redacted_text = redaction.redacted_text

    # ── Jurisdiction resolution (deterministic, no LLM) ──────────────────────
    jurisdiction = resolve(body.country)

    # ── Stage 1: Translation (redacted text -> English for downstream stages) ─
    translation_result = translate(
        text=redacted_text,
        source_language=body.source_language,
        target_language="en",
        client=client,
    )
    english_text = translation_result.translated_text

    # ── Stage 2: Medical Interpretation ──────────────────────────────────────
    interpretation = interpret(
        text=english_text,
        jurisdiction=jurisdiction,
        client=client,
    )

    # ── Stage 3: Cultural Context ─────────────────────────────────────────────
    cultural = add_cultural_context(
        text=interpretation.plain_language_text,
        jurisdiction=jurisdiction,
        user_type=body.user_type,
        client=client,
    )

    # ── Stage 4: Next Steps ────────────────────────────────────────────────────
    next_steps = generate_next_steps(
        framed_text=cultural.framed_text,
        user_type=body.user_type,
        medication_flags=interpretation.medication_flags,
        jurisdiction=jurisdiction,
        client=client,
        medical_interpretation=interpretation.plain_language_text,
        cultural_context=cultural.framed_text,
    )

    # Assemble draft response (next steps in English, to be translated below)
    draft_english = next_steps.next_steps_text

    # Translate back to source language if needed
    if body.source_language.lower() != "en":
        back_translate = translate(
            text=draft_english,
            source_language="en",
            target_language=body.source_language,
            client=client,
        )
        final_response_text = back_translate.translated_text
        min_confidence = min(
            translation_result.confidence,
            interpretation.confidence,
            cultural.confidence,
            next_steps.confidence,
            back_translate.confidence,
        )
    else:
        final_response_text = draft_english
        min_confidence = min(
            translation_result.confidence,
            interpretation.confidence,
            cultural.confidence,
            next_steps.confidence,
        )

    # Build pipeline trace (never includes raw PII)
    pipeline_trace_dict: Dict[str, Any] = {
        "jurisdiction": jurisdiction.registry,
        "pii_redacted": redaction.redaction_count > 0,
        "translation": translation_result.translated_text,
        "medical_interpretation": interpretation.plain_language_text,
        "cultural_context": cultural.framed_text,
        "next_steps": next_steps.next_steps_text,
    }

    # ── HITL Escalation Evaluation ────────────────────────────────────────────
    escalation_input = EscalationInput(
        session_id=session_id,
        original_text=redacted_text,     # already redacted
        user_type=body.user_type,
        country=body.country,
        is_ambiguous_jurisdiction=jurisdiction.is_ambiguous,
        redaction_result=redaction,
        min_confidence=min_confidence,
        medication_flags=interpretation.medication_flags,
        pipeline_trace=pipeline_trace_dict,
        draft_response=final_response_text,
        source_language=body.source_language,
        draft_response_english=draft_english,
        redacted_original_text=redacted_text,
        english_inquiry=english_text,
    )
    escalation_result = evaluate_escalation(escalation_input)
    review_id = enqueue_if_escalated(escalation_result)

    if escalation_result.should_escalate and review_id:
        response.status_code = status.HTTP_202_ACCEPTED
        return AgentEscalatedResponse(
            session_id=session_id,
            escalated=True,
            review_id=review_id,
            status="pending_review",
            message=_escalation_message(body.source_language),
        )

    response.status_code = status.HTTP_200_OK
    return AgentQueryResponse(
        session_id=session_id,
        pipeline_trace=PipelineTrace(**pipeline_trace_dict),
        escalated=False,
        review_id=None,
        response_text=final_response_text,
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /agent/session/{session_id}
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/session/{session_id}",
    response_model=SessionStatusResponse,
    summary="Poll for the result of an escalated query",
)
def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Poll for the review status of an escalated query.

    Returns the approved response text once a reviewer has acted on it,
    or the current status ('pending', 'approved', 'rejected').
    """
    q = get_queue()
    item = q.get_by_session(session_id)

    if item is None:
        # No HITL item — session was processed without escalation
        return SessionStatusResponse(
            session_id=session_id,
            status="approved",
            response_text=None,
        )

    response_text: Optional[str] = None
    if item.status == "approved":
        response_text = item.approved_response

    rejection_reason: Optional[str] = None
    rejection_reason_english: Optional[str] = None
    if item.status == "rejected":
        rejection_reason = item.rejection_reason
        rejection_reason_english = item.rejection_reason_english

    return SessionStatusResponse(
        session_id=session_id,
        status=item.status,
        source_language=item.source_language,
        response_text=response_text,
        rejection_reason=rejection_reason,
        rejection_reason_english=rejection_reason_english,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /agent/translate
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/translate",
    response_model=TranslateResponse,
    summary="Translate text between supported languages",
)
def translate_text(body: TranslateRequest) -> TranslateResponse:
    """
    Translate arbitrary text between supported language codes.

    Accepts any direction: ``non-English -> English`` or
    ``English -> non-English``.  When ``source_lang == target_lang`` the
    original text is returned unchanged.  Uses the existing pipeline
    translator with the application-wide WatsonxClient (mock-safe).
    """
    client = get_client()
    result = translate(
        text=body.text,
        source_language=body.source_lang,
        target_language=body.target_lang,
        client=client,
    )
    return TranslateResponse(
        translated_text=result.translated_text,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        mock=result.mock,
    )
