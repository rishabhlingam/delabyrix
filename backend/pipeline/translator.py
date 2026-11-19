"""
backend/pipeline/translator.py
────────────────────────────────
Stage 1 — Translation & Language Mismatch Detection.

Translates the (already-redacted) user input between supported languages
and flags when the declared source language does not match the detected
language of the text.

Supported language codes: "en", "es", "hi"
Model: ibm/granite-3-8b-instruct via backend/watsonx/client.py

Usage
─────
    from backend.pipeline.translator import translate
    result = translate(
        text="Necesito entender mi deducible de seguro.",
        source_language="es",
        target_language="en",
        client=client,
    )
    print(result.translated_text)   # English translation
    print(result.language_mismatch) # False (declared=detected=es)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from backend.watsonx.client import WatsonxClient, WatsonxResponse

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Supported languages
# ──────────────────────────────────────────────────────────────────────────────

SUPPORTED_LANGUAGES = {"en", "es", "hi"}

_LANGUAGE_NAMES = {
    "en": "English",
    "es": "Spanish",
    "hi": "Hindi",
}

# ──────────────────────────────────────────────────────────────────────────────
# Lightweight language detector
# ──────────────────────────────────────────────────────────────────────────────

# High-frequency function words that are distinctive to each language.
# Words that appear in multiple Latin-script languages (e.g. "no", "en", "al")
# are intentionally excluded to avoid cross-language false positives.
_LANG_MARKERS: dict[str, list[str]] = {
    # Exclusively Spanish function words (not shared with English)
    "es": ["del", "las", "los", "una", "que", "para", "por", "pero", "como",
           "cuando", "porque", "donde", "quien", "cuál", "también", "muy",
           "médica", "médico", "paciente", "necesita"],
    # Hindi uses Devanagari script — zero overlap with Latin scripts
    "hi": ["है", "की", "को", "में", "और", "का", "से", "ने", "पर", "भी",
           "एक", "यह", "वह", "हैं", "कि", "नहीं", "हो", "था", "थी", "जो"],
    # Exclusively English function words (not shared with Spanish)
    "en": ["the", "are", "was", "were", "with", "this", "that", "have",
           "has", "their", "they", "been", "would", "should", "could",
           "patient", "insurance", "hospital", "doctor"],
}


def detect_language(text: str) -> Optional[str]:
    """
    Heuristically detect the language of *text*.

    Returns one of "en", "es", "hi", or None if ambiguous.
    This is intentionally simple — full language detection is handled by
    Granite in the full pipeline; this provides a fast pre-check.
    """
    tokens = set(re.findall(r"\b\w+\b", text.lower()))
    scores = {
        lang: sum(1 for w in markers if w in tokens)
        for lang, markers in _LANG_MARKERS.items()
    }
    best_lang, best_score = max(scores.items(), key=lambda x: x[1])
    second_score = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    # Require a clear winner: at least 1 exclusive marker and strictly more
    # than any other language (or ≥2 matches if tied at 1)
    if best_score >= 1 and best_score > second_score:
        return best_lang
    if best_score >= 2 and best_score >= 2 * max(second_score, 1):
        return best_lang
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TranslationResult:
    """
    Output of the translation stage.

    Attributes
    ──────────
    translated_text   : Text in the target language.
    source_language   : Declared source language code.
    target_language   : Target language code.
    detected_language : Heuristically detected language (may be None).
    language_mismatch : True when detected != declared source language.
    confidence        : Model confidence from the LLM call.
    mock              : True when the response came from a mock stub.
    """

    translated_text: str
    source_language: str
    target_language: str
    detected_language: Optional[str]
    language_mismatch: bool
    confidence: float
    mock: bool = False


# ──────────────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────────────

_TRANSLATE_PROMPT = """\
Translate the following text from {source_lang_name} to {target_lang_name}.
Preserve medical terminology accuracy. Output ONLY the translated text with no
preamble, explanation, or quotation marks.

Text: {text}

Translation:"""


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def translate(
    text: str,
    source_language: str,
    target_language: str,
    client: WatsonxClient,
) -> TranslationResult:
    """
    Translate *text* from *source_language* to *target_language*.

    Parameters
    ──────────
    text             : Redacted user input (must NOT contain raw PII).
    source_language  : BCP-47 code declared by the caller ("en", "es", "hi").
    target_language  : Desired output language code.
    client           : WatsonxClient instance.

    Returns
    ───────
    TranslationResult.  When source == target, the text is returned unchanged
    with a confidence of 1.0 and no LLM call is made.
    """
    src = source_language.lower().strip()
    tgt = target_language.lower().strip()

    # Detect declared vs actual language mismatch
    detected = detect_language(text)
    language_mismatch = detected is not None and detected != src

    # No translation needed if same language
    if src == tgt:
        return TranslationResult(
            translated_text=text,
            source_language=src,
            target_language=tgt,
            detected_language=detected,
            language_mismatch=language_mismatch,
            confidence=1.0,
            mock=False,
        )

    src_name = _LANGUAGE_NAMES.get(src, src)
    tgt_name = _LANGUAGE_NAMES.get(tgt, tgt)

    prompt = _TRANSLATE_PROMPT.format(
        source_lang_name=src_name,
        target_lang_name=tgt_name,
        text=text,
    )

    wx_resp: WatsonxResponse = client.generate(prompt, max_new_tokens=512)

    # Strip any leading/trailing artifacts Granite might prepend
    translated = wx_resp.text.strip().strip('"').strip("'")

    logger.debug(
        "Translation: %s -> %s | mismatch=%s | confidence=%.4f",
        src, tgt, language_mismatch, wx_resp.confidence,
    )

    return TranslationResult(
        translated_text=translated,
        source_language=src,
        target_language=tgt,
        detected_language=detected,
        language_mismatch=language_mismatch,
        confidence=wx_resp.confidence,
        mock=wx_resp.mock,
    )
