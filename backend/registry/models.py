"""
backend/registry/models.py
────────────────────────────
Pydantic models for medication registry records.

Matches the schema defined in architecture.md §5a and the
GET /registry/check + GET /registry/list API contracts (§6.2).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Jurisdiction(str, Enum):
    US_FDA = "US_FDA"
    EU_EMA = "EU_EMA"
    OTHER = "OTHER"


class MedicationStatus(str, Enum):
    approved = "approved"
    restricted = "restricted"
    banned = "banned"
    delisted = "delisted"


class MedicationRecord(BaseModel):
    """
    A single medication registry entry for one jurisdiction.

    One medication (by INN name) may have multiple records — one per
    jurisdiction — with different statuses.
    """

    medication_id: str = Field(..., description="UUID for this registry entry")
    name_generic: str = Field(..., description="INN (generic) drug name, lowercase")
    name_brand: str = Field(..., description="Trade / brand name")
    jurisdiction: Jurisdiction
    status: MedicationStatus
    restriction_reason: Optional[str] = Field(
        None, description="Human-readable reason for restriction/ban/delist"
    )
    therapeutic_alternatives: List[str] = Field(
        default_factory=list,
        description="1–3 INN alternatives for restricted/banned medications",
    )
    last_updated: date = Field(..., description="Registry sync date (ISO8601)")
    source_registry: str = Field(
        ...,
        description="Originating registry name, e.g. 'FDA Orange Book' or 'EU Union Register'",
    )

    model_config = {"use_enum_values": True}


class RegistryListResponse(BaseModel):
    """Paginated list response for GET /registry/list."""

    total: int
    page: int
    page_size: int
    records: List[MedicationRecord]


class RegistryCheckResponse(BaseModel):
    """Response body for GET /registry/check (single record lookup)."""

    medication_id: str
    name_generic: str
    name_brand: str
    jurisdiction: str
    status: str
    restriction_reason: Optional[str]
    therapeutic_alternatives: List[str]
    last_updated: date
    source_registry: str
