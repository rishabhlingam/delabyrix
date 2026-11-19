"""
backend/pipeline/next_steps_guide.py
──────────────────────────────────────
Stage 4 — Next Steps Guide.

Generates actionable, role-specific next steps for the user and, when a
medication is banned or restricted, proposes therapeutic alternatives.

Responsibilities
────────────────
* Prompt Granite to produce concrete, role-appropriate next steps.
* When medication_flags contains banned/restricted items, include the
  registry-sourced therapeutic alternatives in the prompt context.
* Never recommend specific treatments — guide users to appropriate resources
  and professionals.

Usage
─────
    from backend.pipeline.next_steps_guide import generate_next_steps

    result = generate_next_steps(
        framed_text=cultural_context_text,
        user_type="patient",
        medication_flags=flags,
        jurisdiction=jctx,
        client=client,
    )
    print(result.next_steps_text)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from backend.jurisdiction.resolver import JurisdictionContext
from backend.pipeline.medical_interpreter import MedicationFlag
from backend.watsonx.client import WatsonxClient, WatsonxResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class NextStepsResult:
    """
    Output of Stage 4.

    Attributes
    ──────────
    next_steps_text        : Actionable next steps in plain language.
    therapeutic_alternatives: Aggregated list of alternatives for banned/restricted
                               medications (empty when no flags).
    confidence             : Model confidence from the LLM call.
    mock                   : True when response came from a mock stub.
    """

    next_steps_text: str
    therapeutic_alternatives: List[str] = field(default_factory=list)
    confidence: float = 1.0
    mock: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Role-specific guidance fragments
# ──────────────────────────────────────────────────────────────────────────────

_ROLE_NEXT_STEPS: dict[str, str] = {
    "patient": (
        "Provide 3-5 clear, numbered next steps the patient can take immediately. "
        "Include: who to contact, what questions to ask, any rights they should know. "
        "Avoid medical jargon. Be empathetic and actionable."
    ),
    "provider": (
        "Provide clinical next steps for the provider. "
        "Include: documentation requirements, referral pathways, relevant policy "
        "or regulatory considerations, and patient communication guidance."
    ),
    "coordinator": (
        "Provide process-focused next steps for the care coordinator. "
        "Include: escalation procedures, documentation requirements, "
        "follow-up timeline, and interdepartmental handoff points."
    ),
}

# ──────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ──────────────────────────────────────────────────────────────────────────────

_NEXT_STEPS_PROMPT = """\
You are a clinical navigator. Based on the following explanation, provide
specific, actionable next steps for the recipient.

Role: {user_type}
Jurisdiction: {registry} ({privacy_law})
{medication_section}
Guidance: {role_guidance}

Explanation:
{framed_text}

Next steps:"""

_MEDICATION_SECTION_TEMPLATE = """\
IMPORTANT — Medication Alert:
The following medication(s) are {status} in this jurisdiction:
{med_list}

Therapeutic alternatives available: {alternatives}

Include appropriate guidance about these medications and their alternatives
in the next steps. Do NOT recommend specific alternative medications — direct
the patient/provider to consult a healthcare professional."""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_next_steps(
    framed_text: str,
    user_type: str,
    medication_flags: List[MedicationFlag],
    jurisdiction: JurisdictionContext,
    client: WatsonxClient,
) -> NextStepsResult:
    """
    Generate actionable next steps from the culturally-framed text.

    Parameters
    ──────────
    framed_text       : Output from Stage 3 (cultural context).
    user_type         : "patient" | "provider" | "coordinator".
    medication_flags  : List of MedicationFlag from Stage 2 (may be empty).
    jurisdiction      : Resolved JurisdictionContext.
    client            : WatsonxClient instance.

    Returns
    ───────
    NextStepsResult.
    """
    role_guidance = _ROLE_NEXT_STEPS.get(
        user_type.lower(), _ROLE_NEXT_STEPS["patient"]
    )

    # Build medication section if any flags exist
    all_alternatives: List[str] = []
    medication_section = ""
    flagged = [f for f in medication_flags if f.status in ("banned", "restricted")]

    if flagged:
        med_lines = "\n".join(
            f"  - {f.name} ({f.status}): {f.restriction_reason or 'restriction in force'}"
            for f in flagged
        )
        for f in flagged:
            all_alternatives.extend(f.therapeutic_alternatives)

        alt_text = (
            ", ".join(dict.fromkeys(all_alternatives)) if all_alternatives
            else "consult a healthcare professional for alternatives"
        )

        status_label = "banned or restricted"
        medication_section = _MEDICATION_SECTION_TEMPLATE.format(
            status=status_label,
            med_list=med_lines,
            alternatives=alt_text,
        )

    prompt = _NEXT_STEPS_PROMPT.format(
        user_type=user_type,
        registry=jurisdiction.registry,
        privacy_law=jurisdiction.privacy_law,
        medication_section=medication_section,
        role_guidance=role_guidance,
        framed_text=framed_text,
    )

    wx_resp: WatsonxResponse = client.generate(prompt, max_new_tokens=512)

    logger.debug(
        "Next steps: user_type=%s flagged_meds=%d confidence=%.4f",
        user_type, len(flagged), wx_resp.confidence,
    )

    return NextStepsResult(
        next_steps_text=wx_resp.text.strip(),
        therapeutic_alternatives=list(dict.fromkeys(all_alternatives)),
        confidence=wx_resp.confidence,
        mock=wx_resp.mock,
    )
