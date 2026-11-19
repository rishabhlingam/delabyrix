"""
backend/watsonx/orchestrate_adapter.py
────────────────────────────────────────
Thin adapter that formats WatsonxClient requests/responses to match the
watsonx Orchestrate skill invocation contract (architecture.md §7).

Responsibilities
────────────────
* Wraps ``WatsonxClient.generate()`` with Orchestrate-compatible input/output.
* Provides structured skill payloads for the four exported endpoints:
    - clinical_query        (POST /agent/query)
    - medication_check      (GET /registry/check)
    - get_consent_document  (GET /documents/{doc_type}/{language})
    - get_dashboard_metrics (GET /analytics/dashboard)
* Never touches credentials directly — delegates to WatsonxClient.

This module is intentionally light: heavy pipeline logic lives in
backend/pipeline/; this adapter handles only the Orchestrate wire format.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.watsonx.client import WatsonxClient, WatsonxResponse, get_client

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrate skill request / response containers
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class OrchestrateSkillRequest:
    """
    Normalised inbound skill request from watsonx Orchestrate.

    Attributes
    ──────────
    skill_name  : One of the four exported skill names (e.g. 'clinical_query').
    parameters  : Raw parameter dict as received from Orchestrate.
    session_id  : Optional session continuity token.
    """

    skill_name: str
    parameters: Dict[str, Any]
    session_id: Optional[str] = None


@dataclass
class OrchestrateSkillResponse:
    """
    Normalised outbound skill response for watsonx Orchestrate.

    Attributes
    ──────────
    skill_name  : Echoed from the request.
    result      : Skill-specific result dict (passed through to Orchestrate).
    confidence  : Model confidence score (0.0–1.0) from the LLM stage.
    escalated   : True when HITL review is required.
    mock        : True when the response came from a mock/stub backend.
    """

    skill_name: str
    result: Dict[str, Any]
    confidence: float = 1.0
    escalated: bool = False
    mock: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Prompt templates for Orchestrate-routed LLM calls
# ──────────────────────────────────────────────────────────────────────────────

_CLINICAL_QUERY_TEMPLATE = """\
You are a clinical language specialist. Answer the following patient question
in plain, culturally sensitive language. Do not give medical advice.

Question: {text}
Language: {source_language}
User type: {user_type}
Jurisdiction: {jurisdiction}

Provide a clear, empathetic response:"""

_MEDICATION_CHECK_TEMPLATE = """\
Summarise the regulatory status of the medication "{medication_name}"
in jurisdiction "{jurisdiction}" for a healthcare professional.
Focus on approved uses, restrictions, and alternatives if banned."""


# ──────────────────────────────────────────────────────────────────────────────
# Adapter
# ──────────────────────────────────────────────────────────────────────────────

class OrchestrateAdapter:
    """
    Formats requests and responses between watsonx Orchestrate and the
    internal WatsonxClient / pipeline infrastructure.

    Usage
    ─────
        adapter = OrchestrateAdapter()
        response = adapter.dispatch(request)
    """

    def __init__(self, client: Optional[WatsonxClient] = None) -> None:
        self._client: WatsonxClient = client or get_client()

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def dispatch(self, request: OrchestrateSkillRequest) -> OrchestrateSkillResponse:
        """
        Route an Orchestrate skill request to the appropriate handler.

        Parameters
        ──────────
        request : OrchestrateSkillRequest with skill_name and parameters.

        Returns
        ───────
        OrchestrateSkillResponse.

        Raises
        ──────
        ValueError — for unknown skill names.
        """
        handlers = {
            "clinical_query": self._handle_clinical_query,
            "medication_check": self._handle_medication_check,
            "get_consent_document": self._handle_get_consent_document,
            "get_dashboard_metrics": self._handle_get_dashboard_metrics,
        }
        handler = handlers.get(request.skill_name)
        if handler is None:
            raise ValueError(
                f"Unknown Orchestrate skill: '{request.skill_name}'. "
                f"Valid skills: {list(handlers.keys())}"
            )
        logger.debug("Dispatching Orchestrate skill: %s", request.skill_name)
        return handler(request)

    # ── Skill handlers ────────────────────────────────────────────────────────

    def _handle_clinical_query(
        self, request: OrchestrateSkillRequest
    ) -> OrchestrateSkillResponse:
        """Generate a clinical response via Granite for Orchestrate."""
        p = request.parameters
        prompt = _CLINICAL_QUERY_TEMPLATE.format(
            text=p.get("text", ""),
            source_language=p.get("source_language", "en"),
            user_type=p.get("user_type", "patient"),
            jurisdiction=p.get("jurisdiction", "unknown"),
        )
        wx_resp: WatsonxResponse = self._client.generate(prompt)
        return OrchestrateSkillResponse(
            skill_name=request.skill_name,
            result={
                "session_id": request.session_id,
                "response_text": wx_resp.text,
                "model_id": wx_resp.model_id,
            },
            confidence=wx_resp.confidence,
            escalated=False,
            mock=wx_resp.mock,
        )

    def _handle_medication_check(
        self, request: OrchestrateSkillRequest
    ) -> OrchestrateSkillResponse:
        """Summarise medication regulatory status for Orchestrate."""
        p = request.parameters
        prompt = _MEDICATION_CHECK_TEMPLATE.format(
            medication_name=p.get("medication_name", ""),
            jurisdiction=p.get("jurisdiction", "unknown"),
        )
        wx_resp = self._client.generate(prompt, max_new_tokens=256)
        return OrchestrateSkillResponse(
            skill_name=request.skill_name,
            result={
                "summary": wx_resp.text,
                "medication_name": p.get("medication_name"),
                "jurisdiction": p.get("jurisdiction"),
            },
            confidence=wx_resp.confidence,
            mock=wx_resp.mock,
        )

    def _handle_get_consent_document(
        self, request: OrchestrateSkillRequest
    ) -> OrchestrateSkillResponse:
        """
        Return a consent/billing document reference for Orchestrate.

        The actual document content is served by GET /documents/{doc_type}/{lang};
        this skill returns the metadata stub that Orchestrate can follow up on.
        """
        p = request.parameters
        doc_type = p.get("doc_type", "consent_icu_admission")
        language = p.get("language", "en")
        return OrchestrateSkillResponse(
            skill_name=request.skill_name,
            result={
                "doc_type": doc_type,
                "language": language,
                "endpoint": f"/documents/{doc_type}/{language}",
            },
            confidence=1.0,
            mock=self._client.is_mock,
        )

    def _handle_get_dashboard_metrics(
        self, request: OrchestrateSkillRequest
    ) -> OrchestrateSkillResponse:
        """
        Return a pointer to the analytics endpoint for Orchestrate.

        Full metric aggregation is handled by backend/analytics/; this skill
        returns the endpoint reference so Orchestrate can retrieve live data.
        """
        p = request.parameters
        params: Dict[str, str] = {}
        if p.get("date_from"):
            params["date_from"] = p["date_from"]
        if p.get("date_to"):
            params["date_to"] = p["date_to"]
        if p.get("jurisdiction"):
            params["jurisdiction"] = p["jurisdiction"]

        return OrchestrateSkillResponse(
            skill_name=request.skill_name,
            result={
                "endpoint": "/analytics/dashboard",
                "params": params,
            },
            confidence=1.0,
            mock=self._client.is_mock,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────────────────────────────────────────────

def get_adapter() -> OrchestrateAdapter:
    """Return an OrchestrateAdapter backed by the application-wide client."""
    return OrchestrateAdapter(client=get_client())
