"""
backend/pipeline/cultural_context.py
──────────────────────────────────────
Stage 3 — Cultural Context Injection.

Injects jurisdiction-aware regulatory framing and culturally sensitive
communication style into the pipeline response.

Responsibilities
────────────────
* Map jurisdiction context (US_FDA/HIPAA vs EU_EMA/GDPR) to the appropriate
  regulatory messaging framing.
* Tailor tone and information emphasis to the user_type:
    - patient      → empathetic, plain language, avoid jargon
    - provider     → clinical precision, include policy references
    - coordinator  → process-oriented, escalation pathways
* Prompt Granite to produce a culturally framed version of the interpreted text.

Usage
─────
    from backend.pipeline.cultural_context import add_cultural_context
    from backend.jurisdiction.resolver import resolve

    jctx = resolve("DE")
    result = add_cultural_context(
        text=plain_english_text,
        jurisdiction=jctx,
        user_type="patient",
        client=client,
    )
    print(result.framed_text)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.jurisdiction.resolver import JurisdictionContext
from backend.watsonx.client import WatsonxClient, WatsonxResponse

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class CulturalContextResult:
    """
    Output of Stage 3.

    Attributes
    ──────────
    framed_text       : Text with cultural and regulatory context applied.
    jurisdiction_note : Short human-readable note about the regulatory regime.
    user_type         : The user type this response was tailored for.
    confidence        : Model confidence from the LLM call.
    mock              : True when response came from a mock stub.
    """

    framed_text: str
    jurisdiction_note: str
    user_type: str
    confidence: float
    mock: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Regulatory regime descriptions
# ──────────────────────────────────────────────────────────────────────────────

_REGIME_NOTES: dict[str, str] = {
    "US_FDA": (
        "US regulations apply (FDA Orange Book, HIPAA privacy protections). "
        "Patients have HIPAA rights to access and control their health information."
    ),
    "EU_EMA": (
        "EU regulations apply (EMA Union Register, GDPR data protection). "
        "Patients have GDPR rights including data access and the right to be forgotten."
    ),
    "OTHER": (
        "Jurisdiction-specific regulations apply. "
        "Please verify local medication and privacy requirements."
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Cultural norms communication guidance
# ──────────────────────────────────────────────────────────────────────────────

_CULTURAL_GUIDANCE: dict[str, str] = {
    "western": (
        "Use direct, fact-based communication. Respect patient autonomy. "
        "Be clear about rights and options."
    ),
    "south_asian": (
        "Be respectful and considerate of family involvement in healthcare decisions. "
        "Use formal but warm language. Acknowledge the importance of family support."
    ),
    "latin_american": (
        "Use warm, personalised language (personalismo). "
        "Acknowledge the importance of family in care decisions. "
        "Be respectful of personal dignity."
    ),
    "east_asian": (
        "Be respectful and avoid direct confrontation. "
        "Acknowledge the role of family in decisions. "
        "Use formal language and show deference."
    ),
    "middle_eastern": (
        "Be respectful of cultural and religious considerations. "
        "Acknowledge family involvement. Use formal language."
    ),
    "default": (
        "Use clear, respectful, culturally neutral language. "
        "Acknowledge individual rights and needs."
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# User-type communication guidance
# ──────────────────────────────────────────────────────────────────────────────

_USER_TYPE_GUIDANCE: dict[str, str] = {
    "patient": (
        "Write in plain, accessible language. Avoid clinical jargon. "
        "Be empathetic and reassuring. Focus on what the patient needs to know "
        "and do next. Use short sentences."
    ),
    "provider": (
        "Use clinical precision. Include relevant regulatory references. "
        "Provide evidence-based context. Acknowledge professional expertise. "
        "Be concise and factual."
    ),
    "coordinator": (
        "Focus on process, escalation pathways, and documentation requirements. "
        "Include relevant policy references. Be action-oriented and specific "
        "about next steps and responsible parties."
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────────────

_CULTURAL_SYSTEM = (
    "You are a multilingual clinical communication specialist. "
    "Your ONLY task is to revise the provided medical explanation so it is "
    "culturally appropriate and tailored to the recipient's role. "
    "Rules you MUST follow:\n"
    "1. Output ONLY the revised explanation — no preamble, no meta-commentary.\n"
    "2. Do NOT introduce new medical facts, diagnoses, or treatment recommendations.\n"
    "3. Do NOT add unrelated legal disclaimers, privacy notices, or regulatory boilerplate "
    "   not already present in the original explanation.\n"
    "4. Apply the guidance below exactly:\n"
    "   Regulatory regime: {regime_note}\n"
    "   Cultural context: {cultural_guidance}\n"
    "   Recipient role: {user_type_guidance}"
)

_CULTURAL_PROMPT = "Revise the following medical explanation:\n\n{text}"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def add_cultural_context(
    text: str,
    jurisdiction: JurisdictionContext,
    user_type: str,
    client: WatsonxClient,
) -> CulturalContextResult:
    """
    Inject cultural and jurisdictional framing into *text*.

    Parameters
    ──────────
    text         : Plain-language medical interpretation from Stage 2.
    jurisdiction : Resolved JurisdictionContext.
    user_type    : "patient" | "provider" | "coordinator".
    client       : WatsonxClient instance.

    Returns
    ───────
    CulturalContextResult with framed_text and jurisdiction_note.
    """
    regime_note = _REGIME_NOTES.get(jurisdiction.registry, _REGIME_NOTES["OTHER"])
    cultural_guidance = _CULTURAL_GUIDANCE.get(
        jurisdiction.cultural_norms, _CULTURAL_GUIDANCE["default"]
    )
    user_type_guidance = _USER_TYPE_GUIDANCE.get(
        user_type.lower(), _USER_TYPE_GUIDANCE["patient"]
    )

    system = _CULTURAL_SYSTEM.format(
        regime_note=regime_note,
        cultural_guidance=cultural_guidance,
        user_type_guidance=user_type_guidance,
    )
    prompt = _CULTURAL_PROMPT.format(text=text)

    wx_resp: WatsonxResponse = client.generate(
        prompt,
        system_prompt=system,
        max_new_tokens=600,
    )

    logger.debug(
        "Cultural context: jurisdiction=%s user_type=%s confidence=%.4f",
        jurisdiction.registry, user_type, wx_resp.confidence,
    )

    return CulturalContextResult(
        framed_text=wx_resp.text.strip(),
        jurisdiction_note=regime_note,
        user_type=user_type,
        confidence=wx_resp.confidence,
        mock=wx_resp.mock,
    )
