"""
backend/analytics/router.py
────────────────────────────
FastAPI router for the analytics dashboard endpoint.

Endpoints
─────────
  GET /analytics/dashboard — return aggregated, anonymized BI metrics
                             including proactive care recommendations

Matches architecture.md §6.5 and idea.txt proactive analytics requirement.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.analytics.aggregator import build_dashboard

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ──────────────────────────────────────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────────────────────────────────────

class MedicationFlagEntry(BaseModel):
    medication: str
    status: str
    count: int


class ProactiveRecommendation(BaseModel):
    """
    One proactive care recommendation derived from patient-log pattern analysis.
    Contains zero PII — only aggregate counts and group codes.
    """
    category: str = Field(
        ...,
        description="dietary | icd10_cluster | medication_conflict",
    )
    title: str
    description: str
    affected_groups: List[str] = Field(
        default_factory=list,
        description="Nationality codes, language tags, or visit-type labels",
    )
    magnitude: int = Field(..., description="Patient count driving this recommendation")


class DashboardResponse(BaseModel):
    total_queries: int
    escalation_rate: float = Field(..., ge=0.0, le=1.0)
    queries_by_language: Dict[str, int]
    queries_by_user_type: Dict[str, int]
    top_medication_flags: List[MedicationFlagEntry]
    avg_pipeline_stages_completed: float
    jurisdiction_breakdown: Dict[str, int]
    proactive_recommendations: List[ProactiveRecommendation] = Field(
        default_factory=list,
        description=(
            "Emerging care needs derived from patient-log analysis — "
            "dietary demand, ICD-10 clusters, and cross-border medication conflicts. "
            "Zero PII."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /analytics/dashboard
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Return aggregated, anonymized BI metrics",
)
def get_dashboard(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    jurisdiction: Optional[str] = None,
) -> Any:
    """
    Return aggregate interaction metrics for the BI dashboard.

    **Privacy guarantee**: raw query text and patient identifiers are never
    present in this response. Only language codes, user-type counts,
    medication INN names, and boolean escalation flags are aggregated.

    The ``proactive_recommendations`` list surfaces emerging care needs
    (dietary accommodation demand, high-frequency ICD-10 clusters by visitor
    group, and cross-border medication conflict hotspots) derived from the
    anonymized patient-log baseline — zero PII.
    """
    payload = build_dashboard(
        date_from=date_from,
        date_to=date_to,
        jurisdiction_filter=jurisdiction,
    )
    return DashboardResponse(**payload)
