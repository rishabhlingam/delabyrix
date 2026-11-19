"""
backend/routers/documents.py
─────────────────────────────
FastAPI router for consent and billing document retrieval.

Endpoints
─────────
  GET /documents/{doc_type}/{language} — retrieve a multilingual document

Matches architecture.md §6.3.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

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
# Response model
# ──────────────────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    doc_type: str
    language: str
    title: str
    content: str


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
