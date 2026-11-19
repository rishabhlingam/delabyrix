"""
scripts/generate_synthetic_data.py
────────────────────────────────────
One-shot script to generate all synthetic data and write it to synthetic_data/.

Outputs:
  synthetic_data/medication_registry.json        — 50 medication records
  synthetic_data/patient_logs.json               — 200 patient log records
  synthetic_data/consent_docs/{lang}/{doc_type}.txt — 9 multilingual documents

Run from the repository root:
    python scripts/generate_synthetic_data.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ── Make sure the repo root is on the path regardless of cwd ─────────────────
_REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(_REPO_ROOT))

from backend.synthetic.medication_registry import generate_medication_registry
from backend.synthetic.consent_billing_docs import generate_consent_billing_docs
from backend.synthetic.patient_logs import generate_patient_logs


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> None:
    out_root = _REPO_ROOT / "synthetic_data"
    _ensure(out_root)

    # ── 1. Medication registry ────────────────────────────────────────────────
    med_records = generate_medication_registry()
    med_path = out_root / "medication_registry.json"
    med_path.write_text(json.dumps(med_records, indent=2, default=str), encoding="utf-8")
    print(f"[OK] medication_registry.json  - {len(med_records)} records -> {med_path}")

    # ── 2. Patient logs ───────────────────────────────────────────────────────
    patient_logs = generate_patient_logs(200)
    logs_path = out_root / "patient_logs.json"
    logs_path.write_text(json.dumps(patient_logs, indent=2), encoding="utf-8")
    print(f"[OK] patient_logs.json         - {len(patient_logs)} records -> {logs_path}")

    # ── 3. Consent & billing documents ───────────────────────────────────────
    docs = generate_consent_billing_docs()
    doc_count = 0
    for (doc_type, lang), doc in docs.items():
        lang_dir = _ensure(out_root / "consent_docs" / lang)
        file_path = lang_dir / f"{doc_type}.txt"
        file_path.write_text(doc["content"], encoding="utf-8")
        doc_count += 1
        print(f"[OK] consent_docs/{lang}/{doc_type}.txt  ({len(doc['content'])} chars)")

    print(
        f"\n[DONE] Synthetic data generation complete: "
        f"{len(med_records)} medications, {len(patient_logs)} patient logs, "
        f"{doc_count} documents."
    )


if __name__ == "__main__":
    main()
