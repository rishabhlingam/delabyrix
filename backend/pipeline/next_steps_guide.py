"""
backend/pipeline/next_steps_guide.py
──────────────────────────────────────
Stage 4 — Next Steps Guide.

Generates actionable, role-specific next steps for the user and, when a
medication is banned or restricted, proposes therapeutic alternatives.

Responsibilities
────────────────
* Prompt Granite to produce a clear 1–2 sentence clinical/regulatory answer
  synthesised from Stage 2 (medical_interpretation) and Stage 3
  (cultural_context), followed immediately by numbered next-step
  recommendations.
* When medication_flags contains banned/restricted items, include the
  registry-sourced therapeutic alternatives in the prompt context.
* Never recommend specific treatments — guide users to appropriate resources
  and professionals.

Usage
─────
    from backend.pipeline.next_steps_guide import generate_next_steps

    result = generate_next_steps(
        framed_text=cultural_context_text,
        medical_interpretation=medical_interpretation_text,
        cultural_context=cultural_context_text,
        user_type="patient",
        medication_flags=flags,
        jurisdiction=jctx,
        client=client,
    )
    print(result.next_steps_text)
"""

from __future__ import annotations

import logging
import re
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

_NEXT_STEPS_SYSTEM = (
    "You are a clinical navigator. "
    "Write a user-facing response with exactly this structure — no section headers, "
    "no labels, no preamble:\n\n"
    "  • Begin with 1–2 sentences that directly answer whether the medication or "
    "treatment is FDA/EMA approved, restricted, or banned in the relevant jurisdiction. "
    "Synthesise this from the medical interpretation and cultural context provided. "
    "Write in plain language; do not use bullet points or numbering for this opening.\n\n"
    "  • Follow immediately with a blank line, then a numbered list of next steps "
    "the {user_type} should take.\n\n"
    "Rules you MUST follow:\n"
    "1. Do NOT output any section labels, headings, or markers such as "
    "'Part 1', 'Part 2', 'Clinical Answer', 'Next Steps:', or similar.\n"
    "2. Do NOT recommend specific medications or treatments; direct the recipient to a "
    "healthcare professional.\n"
    "3. Do NOT add unrelated legal disclaimers, privacy notices, or genetic-privacy text "
    "   not already present in the explanation.\n"
    "4. Apply this guidance:\n"
    "   Role: {user_type}\n"
    "   Jurisdiction: {registry} ({privacy_law})\n"
    "   {medication_section}"
    "   Guidance: {role_guidance}\n\n"
    "Background context (do NOT copy verbatim — synthesise into the opening sentence):\n"
    "  Medical Interpretation: {medical_interpretation}\n"
    "  Cultural Context: {cultural_context}"
)

_NEXT_STEPS_PROMPT = (
    "Write the clinical/regulatory answer and numbered next steps "
    "for the following explanation:\n\n{framed_text}"
)

_MEDICATION_SECTION_TEMPLATE = """\
IMPORTANT — Medication Alert:
The following medication(s) are {status} in this jurisdiction:
{med_list}

Therapeutic alternatives available: {alternatives}

Include appropriate guidance about these medications and their alternatives
in the next steps. Do NOT recommend specific alternative medications — direct
the patient/provider to consult a healthcare professional."""


# ──────────────────────────────────────────────────────────────────────────────
# Output sanitizer
# ──────────────────────────────────────────────────────────────────────────────

# Matches lines that are purely structural prompt-echo labels, e.g.:
#   "Part 1:", "PART 2 —", "Part 1 - Clinical Answer", "PART2:", etc.
# The pattern is applied line-by-line so it only removes the label line, not the
# content that follows it.
_PART_LABEL_RE = re.compile(
    r"^\s*part\s*\d+\s*[-–—:].*$",
    re.IGNORECASE,
)


def _strip_part_labels(text: str) -> str:
    """
    Remove any structural 'PART N' label lines the LLM may have echoed from
    the system prompt.  Operates line-by-line and collapses runs of blank lines
    left behind, so the returned text is clean prose followed by numbered steps.
    """
    cleaned_lines = [
        line for line in text.splitlines()
        if not _PART_LABEL_RE.match(line)
    ]
    # Collapse 3+ consecutive blank lines down to two (paragraph break)
    result: list[str] = []
    blank_run = 0
    for line in cleaned_lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                result.append(line)
        else:
            blank_run = 0
            result.append(line)
    return "\n".join(result).strip()


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate_next_steps(
    framed_text: str,
    user_type: str,
    medication_flags: List[MedicationFlag],
    jurisdiction: JurisdictionContext,
    client: WatsonxClient,
    *,
    medical_interpretation: str = "",
    cultural_context: str = "",
) -> NextStepsResult:
    """
    Generate a clinical/regulatory answer and actionable next steps.

    The returned ``next_steps_text`` leads with a clear 1–2 sentence
    clinical/regulatory answer synthesised from Stage 2
    (``medical_interpretation``) and Stage 3 (``cultural_context``),
    followed immediately by the numbered next-step recommendations.

    Parameters
    ──────────
    framed_text            : Output from Stage 3 (cultural context framed text).
    user_type              : "patient" | "provider" | "coordinator".
    medication_flags       : List of MedicationFlag from Stage 2 (may be empty).
    jurisdiction           : Resolved JurisdictionContext.
    client                 : WatsonxClient instance.
    medical_interpretation : Plain-language output from Stage 2.
    cultural_context       : Framed output from Stage 3.

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

    system = _NEXT_STEPS_SYSTEM.format(
        user_type=user_type,
        registry=jurisdiction.registry,
        privacy_law=jurisdiction.privacy_law,
        medication_section=medication_section,
        role_guidance=role_guidance,
        medical_interpretation=medical_interpretation or framed_text,
        cultural_context=cultural_context or framed_text,
    )
    prompt = _NEXT_STEPS_PROMPT.format(framed_text=framed_text)

    wx_resp: WatsonxResponse = client.generate(
        prompt,
        system_prompt=system,
        max_new_tokens=512,
    )

    logger.debug(
        "Next steps: user_type=%s flagged_meds=%d confidence=%.4f",
        user_type, len(flagged), wx_resp.confidence,
    )

    return NextStepsResult(
        next_steps_text=_strip_part_labels(wx_resp.text.strip()),
        therapeutic_alternatives=list(dict.fromkeys(all_alternatives)),
        confidence=wx_resp.confidence,
        mock=wx_resp.mock,
    )
