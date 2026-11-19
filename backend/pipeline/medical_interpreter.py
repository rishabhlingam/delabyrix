"""
backend/pipeline/medical_interpreter.py
─────────────────────────────────────────
Stage 2 — Medical Interpretation.

Translates complex clinical and billing concepts into plain language and
cross-checks mentioned medications against the registry for the resolved
jurisdiction.

Responsibilities
────────────────
* Prompt Granite to interpret clinical/billing text in plain language.
* Extract medication names from text using a simple keyword scan.
* Call backend/registry/query.check_medication() for each medication found.
* Return interpretation result, medication flags, and therapeutic alternatives.

Clinical concepts explicitly handled
─────────────────────────────────────
  - ICU vs ER admission differences
  - Deductibles, copays, out-of-pocket maximums
  - Informed consent clauses
  - End-of-life / palliative care terminology
  - Surgery vs procedure distinctions

Usage
─────
    from backend.pipeline.medical_interpreter import interpret
    from backend.jurisdiction.resolver import resolve

    jctx = resolve("US")
    result = interpret(text=english_text, jurisdiction=jctx, client=client)
    print(result.plain_language_text)
    print(result.medication_flags)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from backend.jurisdiction.resolver import JurisdictionContext
from backend.registry.query import check_medication
from backend.watsonx.client import WatsonxClient, WatsonxResponse

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Result types
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MedicationFlag:
    """A medication found in the text with its registry status."""
    name: str
    jurisdiction: str
    status: str                            # approved / restricted / banned / delisted
    restriction_reason: Optional[str]
    therapeutic_alternatives: List[str] = field(default_factory=list)
    found_in_registry: bool = True


@dataclass
class MedicalInterpretationResult:
    """
    Output of Stage 2.

    Attributes
    ──────────
    plain_language_text   : Clinical/billing text rewritten in plain language.
    medication_flags      : Registry check results for medications mentioned.
    has_banned_medication : True when any medication is banned/restricted
                            (triggers HITL escalation rule 2).
    confidence            : Model confidence from the LLM call.
    mock                  : True when response came from a mock stub.
    """

    plain_language_text: str
    medication_flags: List[MedicationFlag]
    has_banned_medication: bool
    confidence: float
    mock: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Clinical concept glossary for prompt enrichment
# ──────────────────────────────────────────────────────────────────────────────

_CLINICAL_GLOSSARY = """
Key clinical/billing concepts to explain in plain language:
- ICU (Intensive Care Unit): a hospital ward for critically ill patients needing
  continuous monitoring, different from the ER (Emergency Room) which handles
  acute but not necessarily critical cases.
- Deductible: the amount a patient pays out-of-pocket before insurance starts
  covering costs.
- Copay: a fixed fee paid for a specific service (e.g. $20 per doctor visit).
- Informed consent: a patient's agreement to a procedure after being told the
  risks, benefits, and alternatives.
- Out-of-pocket maximum: the most a patient pays in a plan year before
  insurance covers 100%.
- Palliative / end-of-life care: comfort-focused care not aimed at curing.
"""

# ──────────────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────────────

_INTERPRET_SYSTEM = (
    "You are a clinical language specialist. "
    "Your ONLY task is to rewrite the provided medical or billing text in plain, accessible language. "
    "Rules you MUST follow:\n"
    "1. Output ONLY the plain-language rewrite — no preamble or commentary.\n"
    "2. Do NOT give medical advice. Do NOT diagnose or recommend treatments.\n"
    "3. Do NOT add privacy notices, legal disclaimers, or genetic-privacy boilerplate "
    "   unless that topic is explicitly present in the original text.\n"
    "4. If the text contains placeholder tokens such as [SSN], [EMAIL], or [PHONE], "
    "   treat them as redacted personal data and do NOT expand, explain, or comment on them "
    "   beyond noting that the information has been removed for privacy.\n"
    "5. Use the clinical glossary below to explain any clinical or billing terms present.\n"
    "{glossary}\n"
    "Jurisdiction: {registry} ({privacy_law})"
)

_INTERPRET_PROMPT = "Rewrite the following text in plain language:\n\n{text}"


# ──────────────────────────────────────────────────────────────────────────────
# Medication extraction heuristic
# ──────────────────────────────────────────────────────────────────────────────

# Common medication-related signal words
_MED_CONTEXT_WORDS = re.compile(
    r"\b(medication|drug|medicine|tablet|pill|prescription|dose|dosage|"
    r"mg|mcg|ml|injection|infusion|inhaler|capsule|patch)\b",
    re.IGNORECASE,
)

# Simple capitalized word near a medication context signal
_MED_NAME_NEAR_CONTEXT = re.compile(
    r"\b([A-Z][a-z]{3,20}(?:ine|ol|am|an|en|il|um|ide|ate|one|cin|ine|mab|zole|pril|sartan|statin)?)\b"
)

# Well-known drug names to also scan for directly (INN names)
_KNOWN_INNS = [
    "metamizole", "dipyrone", "thalidomide", "rofecoxib", "vioxx",
    "phenylbutazone", "diethylstilbestrol", "chloramphenicol",
    "amoxicillin", "ibuprofen", "aspirin", "paracetamol", "acetaminophen",
    "metformin", "atorvastatin", "lisinopril", "amlodipine", "omeprazole",
    "warfarin", "clopidogrel", "metoprolol", "losartan", "simvastatin",
    "rosiglitazone", "domperidone", "phenylephrine",
]

# Spanish and Hindi drug-name variants that should be normalised to their INN
# before the registry check so the keyword scanner catches them even when Stage 1
# (translation) has not yet been applied, or when the LLM returned the Spanish
# form instead of the English INN.
_INN_ALIASES: dict[str, str] = {
    # Spanish variants
    "metamizol":      "metamizole",
    "dipirona":       "metamizole",
    "ibuprofeno":     "ibuprofen",
    "amoxicilina":    "amoxicillin",
    "talidomida":     "thalidomide",
    "cloranfenicol":  "chloramphenicol",
    "warfarina":      "warfarin",
    "metformina":     "metformin",
    # Brand name → INN mappings (for well-known brand names that may appear
    # in patient text without the INN, e.g. "Avandia" → "rosiglitazone")
    "avandia":        "rosiglitazone",
    "vioxx":          "rofecoxib",
    # Hindi transliterations (common romanised spellings)
    "mетамизол":      "metamizole",   # Cyrillic spillover — defensively included
    "aibuprophen":    "ibuprofen",
}


def _extract_medication_candidates(text: str) -> List[str]:
    """
    Return a list of candidate medication names found in *text*.

    Combines known INN names (and their Spanish/Hindi aliases) with a
    heuristic scan near medication context words.  Alias variants are
    normalised to their canonical INN so the registry lookup succeeds.
    """
    lower = text.lower()
    candidates: list[str] = []

    # Alias normalisation — map Spanish/Hindi variants to canonical INN first
    for alias, canonical in _INN_ALIASES.items():
        if alias in lower:
            candidates.append(canonical)

    # Known INN names
    for inn in _KNOWN_INNS:
        if inn in lower:
            candidates.append(inn)

    # Capitalised words adjacent to medication context words
    for _match in _MED_CONTEXT_WORDS.finditer(text):
        # Look 50 chars before and after the context word
        start = max(0, _match.start() - 50)
        end = min(len(text), _match.end() + 50)
        window = text[start:end]
        for name_match in _MED_NAME_NEAR_CONTEXT.finditer(window):
            candidate = name_match.group(1).lower()
            # Exclude common non-drug words that match the pattern
            if candidate not in {
                "patient", "hospital", "doctor", "nurse", "insurance",
                "medical", "clinical", "injection", "tablet", "capsule",
                "prescription", "medicine",
            }:
                candidates.append(candidate)

    return list(dict.fromkeys(candidates))  # deduplicate, preserve order


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def interpret(
    text: str,
    jurisdiction: JurisdictionContext,
    client: WatsonxClient,
) -> MedicalInterpretationResult:
    """
    Rewrite *text* in plain language and check medications against the registry.

    Parameters
    ──────────
    text         : English-language (translated) user input without raw PII.
    jurisdiction : Resolved JurisdictionContext from Stage 0.
    client       : WatsonxClient instance.

    Returns
    ───────
    MedicalInterpretationResult.
    """
    system = _INTERPRET_SYSTEM.format(
        glossary=_CLINICAL_GLOSSARY,
        registry=jurisdiction.registry,
        privacy_law=jurisdiction.privacy_law,
    )
    prompt = _INTERPRET_PROMPT.format(text=text)

    wx_resp: WatsonxResponse = client.generate(
        prompt,
        system_prompt=system,
        max_new_tokens=600,
    )

    # ── Registry medication checks ────────────────────────────────────────────
    medication_flags: List[MedicationFlag] = []
    has_banned = False

    candidates = _extract_medication_candidates(text)
    registry_key = jurisdiction.registry  # US_FDA or EU_EMA

    for med_name in candidates:
        record = check_medication(med_name, registry_key)
        if record:
            flag = MedicationFlag(
                name=record.name_generic,
                jurisdiction=record.jurisdiction,
                status=record.status,
                restriction_reason=record.restriction_reason,
                therapeutic_alternatives=record.therapeutic_alternatives,
                found_in_registry=True,
            )
            medication_flags.append(flag)
            if record.status in ("banned", "restricted"):
                has_banned = True
                logger.warning(
                    "Medication flagged: %s status=%s jurisdiction=%s",
                    record.name_generic, record.status, record.jurisdiction,
                )
        else:
            # Not in registry — not necessarily a problem, but log for audit
            logger.debug("Medication candidate not in registry: %s", med_name)

    logger.debug(
        "Medical interpretation: %d medication(s) checked, has_banned=%s",
        len(medication_flags), has_banned,
    )

    return MedicalInterpretationResult(
        plain_language_text=wx_resp.text.strip(),
        medication_flags=medication_flags,
        has_banned_medication=has_banned,
        confidence=wx_resp.confidence,
        mock=wx_resp.mock,
    )
