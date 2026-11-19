"""
tests/test_document_upload.py
──────────────────────────────
Unit and API integration tests for POST /documents/analyze.

Covers:
  - .txt file upload → 200 OK with structured breakdown
  - .pdf file upload → 200 OK with text extraction
  - PII is stripped before the LLM receives the text
  - Empty file → 400
  - Unsupported file type (.docx) → 400
  - Extracted-but-whitespace-only content → 400
"""

from __future__ import annotations

import io
import os
import struct

# Force mock mode before importing backend modules
os.environ["WATSONX_MOCK_MODE"] = "true"

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.routers.documents import router as documents_router
from backend.watsonx.client import get_client


# ──────────────────────────────────────────────────────────────────────────────
# Test app / client
# ──────────────────────────────────────────────────────────────────────────────

def build_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(documents_router)
    return app


@pytest.fixture(autouse=True)
def reset_singletons():
    """Clear lru_cache singletons between tests."""
    get_settings.cache_clear()
    get_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_client.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(build_test_app(), raise_server_exceptions=True)


# ──────────────────────────────────────────────────────────────────────────────
# Minimal valid PDF builder (uses only stdlib struct/bytes — no external deps)
# ──────────────────────────────────────────────────────────────────────────────

def _make_minimal_pdf(text: str) -> bytes:
    """
    Build a minimal, valid single-page PDF containing *text* in a stream.

    This avoids a dependency on reportlab/fpdf in tests.  The resulting
    PDF is valid enough for pypdf to extract the text stream from it.
    """
    # Encode as latin-1; replace unmappable chars
    encoded = text.encode("latin-1", errors="replace")

    # PDF content stream
    stream = (
        b"BT\n"
        b"/F1 12 Tf\n"
        b"50 700 Td\n"
        b"(" + encoded + b") Tj\n"
        b"ET\n"
    )
    stream_len = len(stream)

    # Build PDF objects
    objects: list[bytes] = []

    # Object 1: Catalog
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    # Object 2: Pages
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    # Object 3: Page
    objects.append(
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 612 792] "
        b"/Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>\n"
        b"endobj\n"
    )
    # Object 4: Content stream
    objects.append(
        b"4 0 obj\n"
        b"<< /Length " + str(stream_len).encode() + b" >>\n"
        b"stream\n" + stream + b"\nendstream\nendobj\n"
    )
    # Object 5: Font (minimal Type1)
    objects.append(
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        b"endobj\n"
    )

    # Build cross-reference table
    header = b"%PDF-1.4\n"
    body = b""
    offsets: list[int] = []
    pos = len(header)
    for obj in objects:
        offsets.append(pos)
        body += obj
        pos += len(obj)

    xref_offset = pos
    xref = b"xref\n"
    xref += f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()

    trailer = (
        b"trailer\n"
        b"<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    )

    return header + body + xref + trailer


# ══════════════════════════════════════════════════════════════════════════════
# .txt upload tests
# ══════════════════════════════════════════════════════════════════════════════

class TestTxtUpload:

    def test_txt_upload_returns_200(self, client: TestClient):
        content = b"This is a consent form. The patient agrees to the ICU admission."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consent.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200

    def test_txt_response_has_required_fields(self, client: TestClient):
        content = b"Deductible: $2,000. Copay: $50 per visit."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("bill.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "filename" in data
        assert "detected_language" in data
        assert "jurisdiction" in data
        assert "pii_redacted" in data
        assert "redacted_preview" in data
        assert "analysis" in data

    def test_txt_filename_echoed_in_response(self, client: TestClient):
        content = b"Surgery consent form text."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("my_surgery_consent.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "my_surgery_consent.txt"

    def test_txt_language_and_country_echoed(self, client: TestClient):
        content = "Formulario de consentimiento quir\u00fargico.".encode("utf-8")
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consentimiento.txt", content, "text/plain")},
            data={"source_language": "es", "country": "MX"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected_language"] == "es"
        assert data["jurisdiction"] == "MX"

    def test_txt_analysis_field_is_non_empty(self, client: TestClient):
        content = b"This is a hospital billing statement."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("bill.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["analysis"]) > 0

    def test_txt_default_language_and_country(self, client: TestClient):
        """Omitting form fields uses defaults: en, US."""
        content = b"ICU admission consent."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("icu.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["detected_language"] == "en"
        assert data["jurisdiction"] == "US"


# ══════════════════════════════════════════════════════════════════════════════
# .pdf upload tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPdfUpload:

    def test_pdf_upload_returns_200(self, client: TestClient):
        pdf_bytes = _make_minimal_pdf("This is a surgical consent form.")
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consent.pdf", pdf_bytes, "application/pdf")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200

    def test_pdf_response_has_required_fields(self, client: TestClient):
        pdf_bytes = _make_minimal_pdf("Deductible amount is $1,500 per year.")
        resp = client.post(
            "/documents/analyze",
            files={"file": ("billing.pdf", pdf_bytes, "application/pdf")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in ("filename", "detected_language", "jurisdiction",
                      "pii_redacted", "redacted_preview", "analysis"):
            assert field in data, f"Missing field: {field}"

    def test_pdf_filename_echoed(self, client: TestClient):
        pdf_bytes = _make_minimal_pdf("ICU consent.")
        resp = client.post(
            "/documents/analyze",
            files={"file": ("icu_consent.pdf", pdf_bytes, "application/pdf")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"] == "icu_consent.pdf"


# ══════════════════════════════════════════════════════════════════════════════
# PII stripping before LLM tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPiiRedactionBeforeLLM:
    """
    Verify that PII is stripped before the LLM sees the text.

    In mock mode the LLM echoes back the first 80 chars of its prompt.
    We embed a known SSN in the document and confirm it does NOT appear
    in the analysis response (meaning it was redacted before reaching
    the mock stub).
    """

    def test_ssn_not_in_analysis(self, client: TestClient):
        content = b"Patient SSN: 234-56-7890. Please sign the consent form."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consent.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        body_str = str(resp.json())
        assert "234-56-7890" not in body_str, (
            "Raw SSN must not appear in any part of the API response."
        )

    def test_email_not_in_analysis(self, client: TestClient):
        content = b"Contact: patient@example.com. This is your hospital bill."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("bill.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        body_str = str(resp.json())
        assert "patient@example.com" not in body_str

    def test_pii_flag_set_when_pii_found(self, client: TestClient):
        content = b"Patient SSN: 234-56-7890. Sign here."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consent.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        assert resp.json()["pii_redacted"] is True

    def test_pii_flag_false_when_no_pii(self, client: TestClient):
        content = b"This form explains your deductible obligations for the year."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("clean.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        assert resp.json()["pii_redacted"] is False

    def test_pii_placeholder_in_redacted_preview(self, client: TestClient):
        """The redacted_preview must contain the [SSN] placeholder, not the raw value."""
        content = b"SSN: 234-56-7890 is the patient identifier. Please verify."
        resp = client.post(
            "/documents/analyze",
            files={"file": ("consent.txt", content, "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 200
        preview = resp.json()["redacted_preview"]
        assert "[SSN]" in preview
        assert "234-56-7890" not in preview


# ══════════════════════════════════════════════════════════════════════════════
# Error handling tests
# ══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:

    def test_empty_file_returns_400(self, client: TestClient):
        resp = client.post(
            "/documents/analyze",
            files={"file": ("empty.txt", b"", "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_unsupported_extension_returns_400(self, client: TestClient):
        resp = client.post(
            "/documents/analyze",
            files={"file": ("report.docx", b"PK\x03\x04fake_docx_content", "application/octet-stream")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"].lower()
        assert "unsupported" in detail or "not accepted" in detail or ".txt" in detail

    def test_whitespace_only_txt_returns_400(self, client: TestClient):
        resp = client.post(
            "/documents/analyze",
            files={"file": ("blank.txt", b"   \n\t  \n", "text/plain")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 400

    def test_invalid_pdf_bytes_returns_400(self, client: TestClient):
        """Sending random bytes named .pdf must return 400, not 500."""
        resp = client.post(
            "/documents/analyze",
            files={"file": ("bad.pdf", b"this is not a valid pdf", "application/pdf")},
            data={"source_language": "en", "country": "US"},
        )
        assert resp.status_code == 400
        assert "pdf" in resp.json()["detail"].lower()
