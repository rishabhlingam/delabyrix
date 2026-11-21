"""
backend/pipeline/hitl_escalator.py
─────────────────────────────────────
HITL Escalation Evaluator.

Evaluates all five escalation rules defined in architecture.md §8 and
enqueues flagged pipeline results for human review.

Escalation rules (architecture.md §8)
───────────────────────────────────────
  Rule 1 — Confidence below threshold (default 0.70).
  Rule 2 — Medication status is 'banned' or 'restricted' in user's jurisdiction.
  Rule 3 — Input text contains PII patterns that could not be fully redacted.
  Rule 4 — Query involves ICU admission, surgery consent, or end-of-life topics.
  Rule 5 — Jurisdiction resolution is ambiguous (no clear match).

Usage
─────
    from backend.pipeline.hitl_escalator import evaluate_escalation, EscalationInput

    result = evaluate_escalation(inp)
    if result.should_escalate:
        enqueue(result)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from backend.config import get_settings
from backend.pipeline.medical_interpreter import MedicationFlag
from backend.pipeline.pii_redactor import RedactionResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# High-stakes topic detector (Rule 4)
# ──────────────────────────────────────────────────────────────────────────────

_HIGH_STAKES_PATTERN = re.compile(
    r"\b("
    r"icu|intensive\s+care|critical\s+care"
    r"|surgery|surgical|operation|operative"
    r"|consent\s+form|informed\s+consent"
    r"|end[- ]of[- ]life|palliative|hospice|dnr|do\s+not\s+resuscitate"
    r"|ventilator|life\s+support|intubat"
    r"|organ\s+(transplant|donation)"
    r")\b",
    re.IGNORECASE,
)


def _has_high_stakes_topic(text: str) -> bool:
    """Return True when *text* contains ICU/surgery/end-of-life language."""
    return bool(_HIGH_STAKES_PATTERN.search(text))


# ──────────────────────────────────────────────────────────────────────────────
# Input / output dataclasses
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class EscalationInput:
    """
    All the information the escalator needs from the pipeline run.

    Attributes
    ──────────
    session_id               : Session UUID from the original request.
    original_text            : Redacted text (NOT raw — raw PII must not be passed).
    user_type                : "patient" | "provider" | "coordinator".
    country                  : ISO 3166-1 alpha-2 country code.
    is_ambiguous_jurisdiction: True when jurisdiction resolver was ambiguous.
    redaction_result         : Output from Stage 0 (pii_redactor).
    min_confidence           : Lowest confidence score across all pipeline LLM calls.
    medication_flags         : List of MedicationFlag from Stage 2.
    pipeline_trace           : Dict with stage outputs for HITL reviewer.
    draft_response           : Assembled draft response text in source language.
    source_language          : BCP-47 source language code.
    draft_response_english   : English version of draft_response.
    redacted_original_text   : Redacted patient inquiry in original language.
    english_inquiry          : English translation of the patient inquiry.
    """

    session_id: str
    original_text: str
    user_type: str
    country: str
    is_ambiguous_jurisdiction: bool
    redaction_result: RedactionResult
    min_confidence: float
    medication_flags: List[MedicationFlag]
    pipeline_trace: dict
    draft_response: str
    source_language: str = "en"
    draft_response_english: Optional[str] = None
    redacted_original_text: Optional[str] = None
    english_inquiry: Optional[str] = None


@dataclass
class EscalationResult:
    """
    Output of the escalation evaluator.

    Attributes
    ──────────
    should_escalate  : True when any rule fired.
    rules_triggered  : Human-readable labels for each rule that fired.
    escalation_input : The original EscalationInput (passed through for enqueueing).
    """

    should_escalate: bool
    rules_triggered: List[str] = field(default_factory=list)
    escalation_input: Optional[EscalationInput] = None


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def evaluate_escalation(inp: EscalationInput) -> EscalationResult:
    """
    Evaluate all five HITL escalation rules against *inp*.

    Parameters
    ──────────
    inp : EscalationInput with all pipeline stage outputs.

    Returns
    ───────
    EscalationResult.  Call ``enqueue_if_escalated()`` to actually push
    to the HITL queue.
    """
    settings = get_settings()
    threshold = settings.hitl_confidence_threshold
    rules_triggered: List[str] = []

    # Rule 1 — Low confidence
    if inp.min_confidence < threshold:
        rules_triggered.append(
            f"rule_1_low_confidence (score={inp.min_confidence:.4f} < {threshold})"
        )

    # Rule 2 — Banned or restricted medication
    for flag in inp.medication_flags:
        if flag.status in ("banned", "restricted"):
            rules_triggered.append(
                f"rule_2_banned_medication ({flag.name} is {flag.status} "
                f"in {flag.jurisdiction})"
            )
            break  # one trigger is enough per category

    # Rule 3 — Residual PII
    if inp.redaction_result.has_residual_pii:
        rules_triggered.append("rule_3_residual_pii")

    # Rule 4 — High-stakes clinical topic
    if _has_high_stakes_topic(inp.original_text):
        rules_triggered.append("rule_4_high_stakes_topic")

    # Rule 5 — Ambiguous jurisdiction
    if inp.is_ambiguous_jurisdiction:
        rules_triggered.append(
            f"rule_5_ambiguous_jurisdiction (country={inp.country!r})"
        )

    should_escalate = bool(rules_triggered)

    if should_escalate:
        logger.info(
            "HITL escalation triggered for session=%s rules=%s",
            inp.session_id,
            rules_triggered,
        )
    else:
        logger.debug("No HITL escalation for session=%s", inp.session_id)

    return EscalationResult(
        should_escalate=should_escalate,
        rules_triggered=rules_triggered,
        escalation_input=inp if should_escalate else None,
    )


def enqueue_if_escalated(result: EscalationResult) -> Optional[str]:
    """
    If *result* requires escalation, push it to the HITL queue and return
    the review_id.  Returns None when no escalation is needed.

    Import is deferred to avoid a circular dependency between pipeline and hitl.
    """
    if not result.should_escalate or result.escalation_input is None:
        return None

    from backend.hitl.queue import get_queue  # deferred import

    inp = result.escalation_input
    review_id = get_queue().enqueue(
        session_id=inp.session_id,
        user_type=inp.user_type,
        country=inp.country,
        pipeline_trace=inp.pipeline_trace,
        draft_response=inp.draft_response,
        escalation_rules=result.rules_triggered,
        source_language=inp.source_language,
        draft_response_english=inp.draft_response_english,
        redacted_original_text=inp.redacted_original_text,
        english_inquiry=inp.english_inquiry,
    )
    return review_id
