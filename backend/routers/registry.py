"""
backend/routers/registry.py
────────────────────────────
FastAPI router for medication registry endpoints.

Endpoints
─────────
  GET  /registry/check      — look up a medication in a given jurisdiction
  GET  /registry/list        — paginated full registry listing
  POST /registry/sync        — ingest a simulated FDA/EMA regulatory bulletin
  GET  /registry/changelog   — return the versioned sync history

Matches architecture.md §6.2 and idea.txt dynamic-registry commitments.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.registry.models import RegistryCheckResponse, RegistryListResponse
from backend.registry.query import check_medication, list_medications
from backend.registry.sync import apply_bulletin, get_changelog, reload_registry

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


# ──────────────────────────────────────────────────────────────────────────────
# POST /registry/sync  — ingest a regulatory bulletin
# ──────────────────────────────────────────────────────────────────────────────

class BulletinRequest(BaseModel):
    """
    Request body for POST /registry/sync.

    Simulates receiving a regulatory bulletin from FDA or EMA that updates
    a medication's status, restriction_reason, or other mutable fields.
    """
    medication_id: str = Field(..., description="UUID of the registry record to update")
    source: str = Field(
        ...,
        description="Registry source label, e.g. 'FDA Orange Book' or 'EU Union Register'",
    )
    updates: Dict[str, Any] = Field(
        ...,
        description=(
            "Map of field → new value. Allowed mutable fields: "
            "status, restriction_reason, therapeutic_alternatives."
        ),
    )


class BulletinResponse(BaseModel):
    sync_version: str
    timestamp: str
    source: str
    changes: List[Dict[str, Any]]


@router.post(
    "/sync",
    response_model=BulletinResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a simulated FDA/EMA regulatory bulletin",
)
def registry_sync(body: BulletinRequest) -> BulletinResponse:
    """
    Apply a regulatory bulletin update to a single medication record.

    The update is applied in-memory, a field-level diff is computed,
    and a versioned changelog entry is recorded.

    Returns the new changelog entry including `sync_version`, `timestamp`,
    `source`, and a `changes` list of `{medication_id, field, old_value, new_value}`.

    Raises **404** if `medication_id` is not found in the registry.
    Raises **400** if no mutable fields are present in `updates`.
    """
    # Guard: only allow mutable fields to be patched via bulletin
    _MUTABLE_FIELDS = {"status", "restriction_reason", "therapeutic_alternatives"}
    filtered_updates = {k: v for k, v in body.updates.items() if k in _MUTABLE_FIELDS}
    if not filtered_updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No mutable fields in updates. "
                f"Allowed: {sorted(_MUTABLE_FIELDS)}"
            ),
        )

    entry = apply_bulletin(
        medication_id=body.medication_id,
        source=body.source,
        updates=filtered_updates,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No registry record found for medication_id={body.medication_id!r}.",
        )
    return BulletinResponse(**entry)


# ──────────────────────────────────────────────────────────────────────────────
# GET /registry/changelog  — versioned sync history
# ──────────────────────────────────────────────────────────────────────────────

class ChangelogResponse(BaseModel):
    total_entries: int
    entries: List[BulletinResponse]


@router.get(
    "/changelog",
    response_model=ChangelogResponse,
    summary="Return the versioned regulatory sync changelog",
)
def registry_changelog(
    limit: int = Query(default=50, ge=1, le=200, description="Max entries to return"),
) -> ChangelogResponse:
    """
    Return the most recent regulatory sync history entries in reverse
    chronological order (newest first).

    Each entry records: `sync_version`, `timestamp`, `source`,
    and a `changes` list of field-level diffs applied to registry records.
    """
    all_entries = get_changelog()
    sliced = all_entries[:limit]
    return ChangelogResponse(
        total_entries=len(all_entries),
        entries=[BulletinResponse(**e) for e in sliced],
    )
