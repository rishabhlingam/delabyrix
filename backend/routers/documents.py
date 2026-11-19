"""
backend/routers/documents.py
─────────────────────────────
FastAPI router for consent and billing document retrieval and analysis.

Endpoints
─────────
  GET  /documents/{doc_type}/{language} — retrieve a multilingual document
  POST /documents/analyze               — upload and analyze a custom document
                                          (.txt or .pdf), with PII redaction
                                          and clause-by-clause breakdown via
                                          IBM Granite 4.

Matches architecture.md §6.3.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from backend.pipeline.pii_redactor import redact
from backend.watsonx.client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

_DOCS_ROOT = (
    Path(__file__).parent.parent.parent / "synthetic_data" / "consent_docs"
)

_VALID_DOC_TYPES = frozenset({
    "consent_icu_admission",
    "consent_surgery",
    "billing_deductible_explanation",
})

_VALID_LANGUAGES = frozenset({"en", "es", "hi"})

_TITLES: dict = {
    ("consent_icu_admission", "en"): "ICU Admission Consent Form",
    ("consent_icu_admission", "es"): "Formulario de Consentimiento de Admisión a UCI",
    ("consent_icu_admission", "hi"): "आईसीयू प्रवेश सहमति फॉर्म",
    ("consent_surgery", "en"): "Surgical Procedure Consent Form",
    ("consent_surgery", "es"): "Formulario de Consentimiento para Procedimiento Quirúrgico",
    ("consent_surgery", "hi"): "शल्य प्रक्रिया सहमति फॉर्म",
    ("billing_deductible_explanation", "en"): "Deductible and Copayment Explanation",
    ("billing_deductible_explanation", "es"): "Explicación de Deducible y Copago",
    ("billing_deductible_explanation", "hi"): "कटौती और सह-भुगतान की व्याख्या",
}


# ──────────────────────────────────────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    doc_type: str
    language: str
    title: str
    content: str


class DocumentAnalysisResponse(BaseModel):
    filename: str
    detected_language: str
    jurisdiction: str
    pii_redacted: bool
    redacted_preview: str
    analysis: str


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _extract_text(filename: str, raw_bytes: bytes) -> str:
    """
    Extract plain text from an uploaded file.

    Supports .txt (UTF-8) and .pdf (via pypdf).
    Raises HTTPException 400 for unsupported types or unreadable PDFs.
    """
    lower = filename.lower()

    if lower.endswith(".txt"):
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not decode .txt file as UTF-8: {exc}",
            ) from exc

    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore[import-untyped]
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pypdf is not installed — PDF extraction unavailable.",
            ) from exc
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not parse PDF: {exc}",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Unsupported file type for {filename!r}. "
            "Only .txt and .pdf files are accepted."
        ),
    )


_ANALYSIS_SYSTEM_PROMPT = (
    "You are a clinical document specialist. "
    "Your task is to analyze medical and financial documents and produce a "
    "clear, plain-language breakdown for patients and their families. "
    "Never include raw personally identifiable information. "
    "Do NOT use section labels like 'PART 1', 'PART 2', etc. "
    "Structure your response with these three clearly named sections:\n"
    "1. Document Summary\n"
    "2. Key Clauses & Financial/Clinical Terms\n"
    "3. Questions to Ask Before Signing / Paying\n"
    "Write in plain, accessible language. Use bullet points where helpful."
)


def _build_analysis_prompt(
    redacted_text: str,
    source_language: str,
    country: str,
) -> str:
    """Build the user-turn prompt for the clause breakdown."""
    lang_note = (
        f"Write your response in the language with BCP-47 code '{source_language}'. "
        if source_language.lower() != "en"
        else "Write your response in English. "
    )
    country_note = (
        f"Apply jurisdiction-specific context for {country} where relevant "
        "(e.g. HIPAA rights for US, GDPR rights for EU countries, "
        "deductible/copay structures for US insurance, NHS context for GB)."
    )
    return (
        f"{lang_note}{country_note}\n\n"
        "Analyze the following document and produce a structured breakdown:\n\n"
        f"{redacted_text}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /documents/{doc_type}/{language}
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{doc_type}/{language}",
    response_model=DocumentResponse,
    summary="Retrieve a synthetic consent or billing document",
)
def get_document(doc_type: str, language: str) -> DocumentResponse:
    """
    Retrieve a synthetic multilingual document by type and language.

    - **doc_type**: `consent_icu_admission` | `consent_surgery` | `billing_deductible_explanation`
    - **language**: `en` | `es` | `hi`
    """
    if doc_type not in _VALID_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid doc_type={doc_type!r}. "
                f"Valid values: {sorted(_VALID_DOC_TYPES)}"
            ),
        )
    if language not in _VALID_LANGUAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid language={language!r}. "
                f"Valid values: {sorted(_VALID_LANGUAGES)}"
            ),
        )

    file_path = _DOCS_ROOT / language / f"{doc_type}.txt"
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document file not found: {file_path.name}",
        )

    content = file_path.read_text(encoding="utf-8")
    title = _TITLES.get((doc_type, language), doc_type.replace("_", " ").title())

    return DocumentResponse(
        doc_type=doc_type,
        language=language,
        title=title,
        content=content,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /documents/analyze
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=DocumentAnalysisResponse,
    summary="Upload and analyze a custom consent form or hospital bill",
)
async def analyze_document(
    file: UploadFile = File(..., description="A .txt or .pdf document to analyze"),
    source_language: str = Form(default="en", description="BCP-47 language code for the response"),
    country: str = Form(default="US", description="ISO 3166-1 alpha-2 country code for jurisdiction context"),
) -> DocumentAnalysisResponse:
    """
    Upload a custom document (.txt or .pdf), apply PII redaction, then
    produce a structured plain-language clause-by-clause breakdown using
    IBM Granite 4.

    The response includes:
    - **filename**: original upload filename
    - **detected_language**: echoes back the requested source_language
    - **jurisdiction**: the country code used for jurisdiction context
    - **pii_redacted**: whether any PII was found and masked
    - **redacted_preview**: first 500 chars of the PII-redacted text
    - **analysis**: structured clause breakdown (Document Summary,
      Key Clauses & Financial/Clinical Terms, Questions to Ask)
    """
    filename = file.filename or "uploaded_document"
    raw_bytes = await file.read()

    if not raw_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── Extract plain text ────────────────────────────────────────────────────
    extracted_text = _extract_text(filename, raw_bytes)

    if not extracted_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text could be extracted from the uploaded file.",
        )

    # ── Stage 0: PII Redaction ────────────────────────────────────────────────
    redaction = redact(extracted_text)
    redacted_text = redaction.redacted_text
    pii_found = redaction.redaction_count > 0

    # Build a short preview (first 500 chars) for display
    redacted_preview = redacted_text[:500].strip()
    if len(redacted_text) > 500:
        redacted_preview += "…"

    # ── LLM: Clause Breakdown ─────────────────────────────────────────────────
    client = get_client()
    prompt = _build_analysis_prompt(
        redacted_text=redacted_text,
        source_language=source_language,
        country=country,
    )

    logger.info(
        "Analyzing document: filename=%r lang=%s country=%s pii_redacted=%s",
        filename,
        source_language,
        country,
        pii_found,
    )

    response = client.generate(
        prompt=prompt,
        system_prompt=_ANALYSIS_SYSTEM_PROMPT,
        max_new_tokens=1024,
        temperature=0.3,
    )

    return DocumentAnalysisResponse(
        filename=filename,
        detected_language=source_language,
        jurisdiction=country,
        pii_redacted=pii_found,
        redacted_preview=redacted_preview,
        analysis=response.text,
    )
