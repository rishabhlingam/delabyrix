"""
backend/routers/synthetic.py
──────────────────────────────
FastAPI router for triggering a fresh synthetic data generation run.

Endpoints
─────────
  POST /synthetic/generate — regenerate all synthetic data files

Matches architecture.md §6.6.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.synthetic.consent_billing_docs import generate_consent_billing_docs
from backend.synthetic.medication_registry import generate_medication_registry
from backend.synthetic.patient_logs import generate_patient_logs
from backend.registry.sync import reload_registry

router = APIRouter(prefix="/synthetic", tags=["synthetic"])

_SYNTHETIC_DATA_ROOT = (
    Path(__file__).parent.parent.parent / "synthetic_data"
)


# ──────────────────────────────────────────────────────────────────────────────
# Request / response models
# ──────────────────────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    seed: Optional[int] = Field(
        default=None,
        description="RNG seed for reproducibility (None = use module default)",
    )
    medication_count: int = Field(
        default=50,
        description="Number of medication records (default 50; actual value is fixed by generator)",
    )
    patient_log_count: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Number of patient log records to generate",
    )


class GenerateCounts(BaseModel):
    medications: int
    patient_logs: int
    documents: int


class GenerateResponse(BaseModel):
    status: str
    counts: GenerateCounts


# ──────────────────────────────────────────────────────────────────────────────
# POST /synthetic/generate
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Trigger a fresh synthetic data generation run",
)
def generate_synthetic_data(body: GenerateRequest) -> GenerateResponse:
    """
    Regenerate all synthetic data files and reload the in-memory registry.

    - Overwrites `synthetic_data/medication_registry.json`
    - Overwrites `synthetic_data/patient_logs.json`
    - Overwrites all 9 consent/billing documents in `synthetic_data/consent_docs/`

    The in-memory medication registry is reloaded immediately after generation.
    """
    root = _SYNTHETIC_DATA_ROOT
    root.mkdir(parents=True, exist_ok=True)

    # ── 1. Medication registry ────────────────────────────────────────────────
    med_records = generate_medication_registry()
    med_path = root / "medication_registry.json"
    med_path.write_text(json.dumps(med_records, indent=2, default=str), encoding="utf-8")

    # ── 2. Patient logs ───────────────────────────────────────────────────────
    patient_logs = generate_patient_logs(body.patient_log_count)
    logs_path = root / "patient_logs.json"
    logs_path.write_text(json.dumps(patient_logs, indent=2), encoding="utf-8")

    # ── 3. Consent & billing documents ───────────────────────────────────────
    docs = generate_consent_billing_docs()
    doc_count = 0
    for (doc_type, lang), doc in docs.items():
        lang_dir = root / "consent_docs" / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        (lang_dir / f"{doc_type}.txt").write_text(doc["content"], encoding="utf-8")
        doc_count += 1

    # ── 4. Reload in-memory registry ─────────────────────────────────────────
    reload_registry()

    return GenerateResponse(
        status="generated",
        counts=GenerateCounts(
            medications=len(med_records),
            patient_logs=len(patient_logs),
            documents=doc_count,
        ),
    )
