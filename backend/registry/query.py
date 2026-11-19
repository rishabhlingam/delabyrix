"""
backend/registry/query.py
──────────────────────────
Registry query layer: search the in-memory medication registry by
medication name (INN or brand) and/or jurisdiction.

Matches the GET /registry/check and GET /registry/list API contracts
defined in architecture.md §6.2.
"""

from __future__ import annotations

import re
from typing import List, Optional

from backend.registry.models import (
    MedicationRecord,
    RegistryCheckResponse,
    RegistryListResponse,
)
from backend.registry.sync import get_registry


def _normalise(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r"\s+", " ", text.strip().lower())


def check_medication(
    medication_name: str,
    jurisdiction: str,
) -> Optional[RegistryCheckResponse]:
    """
    Look up a medication by INN or brand name within a specific jurisdiction.

    Parameters
    ──────────
    medication_name : INN or brand name (case-insensitive, partial match allowed)
    jurisdiction    : "US_FDA" | "EU_EMA"

    Returns
    ───────
    RegistryCheckResponse for the first matching record, or None if not found.
    """
    query = _normalise(medication_name)
    j = jurisdiction.upper()

    for raw in get_registry():
        if raw.get("jurisdiction", "").upper() != j:
            continue
        if query in _normalise(raw.get("name_generic", "")) or query in _normalise(
            raw.get("name_brand", "")
        ):
            record = MedicationRecord.model_validate(raw)
            return RegistryCheckResponse(
                medication_id=record.medication_id,
                name_generic=record.name_generic,
                name_brand=record.name_brand,
                jurisdiction=record.jurisdiction,
                status=record.status,
                restriction_reason=record.restriction_reason,
                therapeutic_alternatives=record.therapeutic_alternatives,
                last_updated=record.last_updated,
                source_registry=record.source_registry,
            )
    return None


def list_medications(
    page: int = 1,
    page_size: int = 20,
    jurisdiction: Optional[str] = None,
) -> RegistryListResponse:
    """
    Return a paginated list of medication registry records.

    Parameters
    ──────────
    page       : 1-based page number
    page_size  : records per page (max 100)
    jurisdiction : optional filter — "US_FDA" | "EU_EMA"

    Returns
    ───────
    RegistryListResponse with total, page, page_size, and records list.
    """
    page_size = min(page_size, 100)
    page = max(page, 1)

    all_records = get_registry()

    if jurisdiction:
        j = jurisdiction.upper()
        all_records = [r for r in all_records if r.get("jurisdiction", "").upper() == j]

    total = len(all_records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = [MedicationRecord.model_validate(r) for r in all_records[start:end]]

    return RegistryListResponse(
        total=total,
        page=page,
        page_size=page_size,
        records=page_records,
    )


def get_medication_by_id(medication_id: str) -> Optional[MedicationRecord]:
    """Return the registry record with the given medication_id, or None."""
    for raw in get_registry():
        if raw.get("medication_id") == medication_id:
            return MedicationRecord.model_validate(raw)
    return None


def find_cross_jurisdiction_conflicts(name_generic: str) -> List[MedicationRecord]:
    """
    Return all registry records for a given INN name across all jurisdictions.

    Useful for the pipeline to compare FDA vs EMA status side-by-side.
    """
    query = _normalise(name_generic)
    results = []
    for raw in get_registry():
        if query == _normalise(raw.get("name_generic", "")):
            results.append(MedicationRecord.model_validate(raw))
    return results
