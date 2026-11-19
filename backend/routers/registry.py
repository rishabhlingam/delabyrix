"""
backend/routers/registry.py
────────────────────────────
FastAPI router for medication registry endpoints.

Endpoints
─────────
  GET /registry/check  — look up a medication in a given jurisdiction
  GET /registry/list   — paginated full registry listing

Matches architecture.md §6.2.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.registry.models import RegistryCheckResponse, RegistryListResponse
from backend.registry.query import check_medication, list_medications

router = APIRouter(prefix="/registry", tags=["registry"])


# ──────────────────────────────────────────────────────────────────────────────
# GET /registry/check
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/check",
    response_model=RegistryCheckResponse,
    summary="Check a medication's status in a given jurisdiction",
)
def registry_check(
    medication_name: str = Query(..., description="INN or brand name (case-insensitive)"),
    jurisdiction: str = Query(..., description="US_FDA | EU_EMA"),
) -> RegistryCheckResponse:
    """
    Look up a medication by INN or brand name within a specific jurisdiction.

    Returns the first matching registry record, or **404** if not found.
    """
    result = check_medication(medication_name, jurisdiction)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No record found for medication={medication_name!r} "
                f"in jurisdiction={jurisdiction!r}."
            ),
        )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# GET /registry/list
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/list",
    response_model=RegistryListResponse,
    summary="Return the full medication registry (paginated)",
)
def registry_list(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page (max 100)"),
    jurisdiction: Optional[str] = Query(default=None, description="Optional filter: US_FDA | EU_EMA"),
) -> RegistryListResponse:
    """
    Return a paginated list of all medication registry records.

    Use `jurisdiction` to filter to FDA-only or EMA-only records.
    """
    return list_medications(page=page, page_size=page_size, jurisdiction=jurisdiction)
