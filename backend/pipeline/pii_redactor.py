"""
backend/pipeline/pii_redactor.py
──────────────────────────────────
Stage 0 — PII Redaction.

Strips personally-identifiable information from raw user input *before*
any text is forwarded to watsonx.ai or logged.

Patterns handled
────────────────
  * Full names (heuristic: Firstname Lastname title-cased words)
  * Email addresses
  * US/international phone numbers
  * US Social Security Numbers  (XXX-XX-XXXX or XXXXXXXXX)
  * Passport / government ID numbers  (letter + 6-9 digits)
  * Dates of birth  (various formats: MM/DD/YYYY, DD-MM-YYYY, YYYY-MM-DD,
                    "born on …", "dob …")

Design note (architecture.md §10):
  "Only the session manager holds the [redaction] mapping; never logged."
  This module returns the redacted text and a summary count.  The original
  text is NEVER stored or returned.

Usage
─────
    from backend.pipeline.pii_redactor import redact
    result = redact("My name is John Smith, SSN 123-45-6789.")
    # result.redacted_text  → "My name is [NAME], SSN [SSN]."
    # result.redaction_count → 2
    # result.has_residual_pii → False
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RedactionResult:
    """
    Output of the PII redaction stage.

    Attributes
    ──────────
    redacted_text    : Input with PII replaced by placeholder tokens.
    redaction_count  : Total number of PII patterns replaced.
    types_found      : List of PII type labels detected (for HITL escalation).
    has_residual_pii : True when heuristics suspect un-redacted PII remains
                       (triggers HITL escalation rule 3).
    """

    redacted_text: str
    redaction_count: int
    types_found: List[str] = field(default_factory=list)
    has_residual_pii: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Regex patterns  (compiled once at import time)
# ──────────────────────────────────────────────────────────────────────────────

# SSN: 123-45-6789 or 123456789
_SSN = re.compile(
    r"\b(?!000|666|9\d\d)\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
)

# Email addresses
_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# Phone numbers: +1-800-555-1234, (800)555-1234, 800.555.1234, 8005551234
_PHONE = re.compile(
    r"(?<!\d)"                               # not preceded by digit
    r"(\+?\d{1,3}[\s\-\.]?)?"               # optional country code
    r"(\(?\d{3}\)?[\s\-\.]?)"               # area code
    r"\d{3}[\s\-\.]\d{4}"                   # local number
    r"(?!\d)"                                # not followed by digit
)

# Passport / government ID: letter(s) followed by 6–9 digits
_PASSPORT = re.compile(
    r"\b[A-Z]{1,2}\d{6,9}\b"
)

# Dates of birth — contextual: "DOB", "born on", "date of birth"
_DOB_CONTEXTUAL = re.compile(
    r"""
    (?:dob|d\.o\.b|date\s+of\s+birth|born\s+on|born)\s*[:\-]?\s*
    (?:
        \d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}   # MM/DD/YYYY or DD-MM-YYYY
      | \d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}     # YYYY-MM-DD
      | \d{1,2}\s+\w+\s+\d{4}               # 12 March 1990
      | \w+\s+\d{1,2},?\s+\d{4}             # March 12, 1990
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Standalone date patterns (more aggressive — only run as residual-PII check)
_DATE_STANDALONE = re.compile(
    r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4}\b"   # MM/DD/YYYY
    r"|\b\d{4}[\/\-]\d{2}[\/\-]\d{2}\b"       # YYYY-MM-DD
)

# Full name heuristic: 2–4 consecutive title-cased words not at sentence start.
# Deliberately conservative to avoid over-redacting.
_NAME_HEURISTIC = re.compile(
    r"(?<![.!?]\s)(?<!\n)"           # not at sentence start
    r"\b([A-Z][a-z]{1,20})"          # First
    r"(?:\s+[A-Z][a-z]{1,20}){1,3}"  # Last (and optionally Middle / Suffix)
    r"\b"
)

# Words that are common medical/clinical terms but look like names — excluded
_NAME_EXCLUSIONS = frozenset({
    "United States", "New York", "Los Angeles", "San Francisco",
    "Emergency Room", "Intensive Care", "Blood Pressure",
    "Heart Rate", "Blood Type", "Medical Record",
    "Patient Name", "Provider Name", "Date Of",
    "Social Security", "Insurance Number",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
})


# ──────────────────────────────────────────────────────────────────────────────
# Ordered redaction pipeline
# ──────────────────────────────────────────────────────────────────────────────

_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # (compiled pattern, placeholder, pii_type_label)
    (_EMAIL,           "[EMAIL]",     "email"),
    (_SSN,             "[SSN]",       "ssn"),
    (_PHONE,           "[PHONE]",     "phone"),
    (_PASSPORT,        "[ID]",        "passport_id"),
    (_DOB_CONTEXTUAL,  "[DOB]",       "dob"),
]


def _redact_names(text: str) -> Tuple[str, int]:
    """Apply name heuristic, skipping known non-name phrases."""
    count = 0

    def replace_name(match: re.Match) -> str:  # type: ignore[type-arg]
        nonlocal count
        matched = match.group(0)
        # Skip if the matched string is in the exclusion list
        if matched in _NAME_EXCLUSIONS:
            return matched
        count += 1
        return "[NAME]"

    result = _NAME_HEURISTIC.sub(replace_name, text)
    return result, count


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def redact(text: str) -> RedactionResult:
    """
    Strip PII from *text* and return a RedactionResult.

    The original *text* is never stored or returned — only the redacted
    version and summary statistics are exposed.

    Parameters
    ──────────
    text : Raw user input (may contain PII).

    Returns
    ───────
    RedactionResult with redacted_text, redaction_count, types_found, and
    has_residual_pii flag.
    """
    if not text:
        return RedactionResult(
            redacted_text="",
            redaction_count=0,
            types_found=[],
            has_residual_pii=False,
        )

    working = text
    total_count = 0
    types: List[str] = []

    # Apply all structured patterns in order
    for pattern, placeholder, pii_type in _PATTERNS:
        new_text, n = _apply_pattern(working, pattern, placeholder)
        if n:
            total_count += n
            types.append(pii_type)
            working = new_text

    # Apply name heuristic last (after structured PII is already masked)
    working, name_count = _redact_names(working)
    if name_count:
        total_count += name_count
        types.append("name")

    # Residual-PII heuristic: check for standalone dates that may be DOBs
    # We flag but do NOT redact (too aggressive — could be appointment dates)
    residual = bool(_DATE_STANDALONE.search(working))

    return RedactionResult(
        redacted_text=working,
        redaction_count=total_count,
        types_found=types,
        has_residual_pii=residual,
    )


def _apply_pattern(
    text: str, pattern: re.Pattern, placeholder: str  # type: ignore[type-arg]
) -> Tuple[str, int]:
    """Replace all matches of *pattern* with *placeholder*; return (new_text, count)."""
    count = 0

    def _replace(_match: re.Match) -> str:  # type: ignore[type-arg]
        nonlocal count
        count += 1
        return placeholder

    new_text = pattern.sub(_replace, text)
    return new_text, count
