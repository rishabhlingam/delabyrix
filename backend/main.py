"""
backend/main.py
─────────────────
FastAPI application entrypoint.

Registers all routers, configures CORS, and runs a startup check that
ensures synthetic data files exist (runs the generator automatically if
they are missing).

Startup behaviour
─────────────────
  1. Check that synthetic_data/medication_registry.json exists.
  2. If missing, run generate_synthetic_data to create it.
  3. Load the registry into the in-memory cache (registry.sync).

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.analytics.router import router as analytics_router
from backend.hitl.router import router as hitl_router
from backend.routers.agent import router as agent_router
from backend.routers.documents import router as documents_router
from backend.routers.registry import router as registry_router
from backend.routers.synthetic import router as synthetic_router
from backend.registry.sync import reload_registry

logger = logging.getLogger(__name__)

_SYNTHETIC_DATA_ROOT = Path(__file__).parent.parent / "synthetic_data"
_REGISTRY_FILE = _SYNTHETIC_DATA_ROOT / "medication_registry.json"


# ──────────────────────────────────────────────────────────────────────────────
# Application factory
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Multilingual Clinical AI Agent & BI Platform",
    description=(
        "Multilingual, compliance-aware clinical AI agent and BI platform. "
        "Supports foreign patients, healthcare providers, and care coordinators "
        "with cross-border medication registry checks, HITL review, and BI analytics."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ──────────────────────────────────────────────────────────────────────────────
# CORS middleware (permissive for local MVP development)
# ──────────────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# Router registration
# ──────────────────────────────────────────────────────────────────────────────

app.include_router(agent_router)
app.include_router(registry_router)
app.include_router(documents_router)
app.include_router(hitl_router)
app.include_router(analytics_router)
app.include_router(synthetic_router)


# ──────────────────────────────────────────────────────────────────────────────
# Startup: ensure synthetic data exists
# ──────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup_synthetic_check() -> None:
    """
    On startup, ensure synthetic data files are present.

    If the medication registry JSON is missing, generate all synthetic data
    automatically so the app starts cleanly without a manual pre-step.
    """
    if not _REGISTRY_FILE.exists():
        logger.warning(
            "synthetic_data/medication_registry.json not found — generating synthetic data."
        )
        _generate_all_synthetic_data()

    try:
        reload_registry()
        logger.info("Medication registry loaded at startup.")
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to load registry at startup: %s", exc)


def _generate_all_synthetic_data() -> None:
    """Generate and persist all synthetic data files (called on startup if missing)."""
    from backend.synthetic.medication_registry import generate_medication_registry
    from backend.synthetic.consent_billing_docs import generate_consent_billing_docs
    from backend.synthetic.patient_logs import generate_patient_logs

    _SYNTHETIC_DATA_ROOT.mkdir(parents=True, exist_ok=True)

    med_records = generate_medication_registry()
    _REGISTRY_FILE.write_text(
        json.dumps(med_records, indent=2, default=str), encoding="utf-8"
    )
    logger.info("Generated medication registry: %d records.", len(med_records))

    patient_logs = generate_patient_logs(200)
    logs_path = _SYNTHETIC_DATA_ROOT / "patient_logs.json"
    logs_path.write_text(json.dumps(patient_logs, indent=2), encoding="utf-8")
    logger.info("Generated patient logs: %d records.", len(patient_logs))

    docs = generate_consent_billing_docs()
    doc_count = 0
    for (doc_type, lang), doc in docs.items():
        lang_dir = _SYNTHETIC_DATA_ROOT / "consent_docs" / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        (lang_dir / f"{doc_type}.txt").write_text(doc["content"], encoding="utf-8")
        doc_count += 1
    logger.info("Generated consent/billing documents: %d files.", doc_count)


# ──────────────────────────────────────────────────────────────────────────────
# Health check
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"], summary="Health check")
def health_check() -> dict:
    """Return a simple health status for readiness probes."""
    return {"status": "ok", "version": app.version}
