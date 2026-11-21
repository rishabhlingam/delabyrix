"""
backend/hitl/models.py
────────────────────────
Pydantic models for the HITL review queue.

Matches the GET /hitl/queue, POST /hitl/approve, and POST /hitl/reject
API contracts defined in architecture.md §6.4.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ReviewStatus(str, Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


# ──────────────────────────────────────────────────────────────────────────────
# Queue item (internal + API representation)
# ──────────────────────────────────────────────────────────────────────────────

class ReviewItem(BaseModel):
    """
    A single HITL review queue entry.

    Stored in-memory; never includes raw user text (data minimization).
    """

    review_id: str = Field(..., description="UUID for this review item")
    session_id: str = Field(..., description="Session UUID from the agent request")
    submitted_at: datetime = Field(..., description="When this item entered the queue")
    user_type: str = Field(..., description="patient | provider | coordinator")
    country: str = Field(..., description="ISO 3166-1 alpha-2 country code")
    pipeline_trace: Dict[str, Any] = Field(
        ..., description="Stage outputs for reviewer context (no raw PII)"
    )
    draft_response: str = Field(..., description="Draft response text for reviewer (original language)")
    draft_response_english: Optional[str] = Field(
        default=None, description="English version of the draft response"
    )
    source_language: str = Field(
        default="en", description="BCP-47 source language code of the original query"
    )
    redacted_original_text: Optional[str] = Field(
        default=None, description="Redacted patient inquiry in original language"
    )
    english_inquiry: Optional[str] = Field(
        default=None, description="English translation of the patient inquiry"
    )
    escalation_rules: List[str] = Field(
        default_factory=list,
        description="HITL rules that triggered escalation",
    )
    status: ReviewStatus = Field(default=ReviewStatus.pending)

    # Set on approve/reject
    reviewed_at: Optional[datetime] = Field(default=None)
    approved_response: Optional[str] = Field(default=None)
    reviewer_note: Optional[str] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None)
    rejection_reason_english: Optional[str] = Field(default=None)

    model_config = {"use_enum_values": True}


# ──────────────────────────────────────────────────────────────────────────────
# API request / response models
# ──────────────────────────────────────────────────────────────────────────────

class HITLQueueResponse(BaseModel):
    """Response body for GET /hitl/queue."""

    pending_count: int
    items: List[ReviewItem]


class ApproveRequest(BaseModel):
    """Request body for POST /hitl/approve."""

    review_id: str
    approved_response: str
    reviewer_note: Optional[str] = None


class RejectRequest(BaseModel):
    """Request body for POST /hitl/reject."""

    review_id: str
    rejection_reason: str
    rejection_reason_english: Optional[str] = None


class ReviewActionResponse(BaseModel):
    """Shared response body for approve and reject."""

    status: str   # "approved" | "rejected"
