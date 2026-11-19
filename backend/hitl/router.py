"""
backend/hitl/router.py
────────────────────────
FastAPI router for HITL Review Queue endpoints.

Endpoints
─────────
  GET  /hitl/queue      — list all pending review items
  POST /hitl/approve    — approve a draft response
  POST /hitl/reject     — reject a draft response

Matches the API contracts in architecture.md §6.4.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.hitl.models import (
    ApproveRequest,
    HITLQueueResponse,
    RejectRequest,
    ReviewActionResponse,
)
from backend.hitl.queue import get_queue

router = APIRouter(prefix="/hitl", tags=["hitl"])


# ──────────────────────────────────────────────────────────────────────────────
# GET /hitl/queue
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/queue",
    response_model=HITLQueueResponse,
    summary="List all pending HITL review items",
)
def get_hitl_queue() -> HITLQueueResponse:
    """
    Return all pending review items ordered by submission time (oldest first).

    Intended for care coordinators / HITL reviewers.
    """
    q = get_queue()
    pending = q.get_pending()
    return HITLQueueResponse(
        pending_count=len(pending),
        items=pending,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /hitl/approve
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/approve",
    response_model=ReviewActionResponse,
    summary="Approve a draft response and release it to the user",
)
def approve_review(body: ApproveRequest) -> ReviewActionResponse:
    """
    Approve a pending review item with the reviewer's final response text.

    - **review_id**: UUID of the pending item.
    - **approved_response**: Final edited response text.
    - **reviewer_note**: Optional internal note (not shown to users).
    """
    q = get_queue()
    try:
        q.approve(
            review_id=body.review_id,
            approved_response=body.approved_response,
            reviewer_note=body.reviewer_note,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"review_id not found: {body.review_id!r}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return ReviewActionResponse(status="approved")


# ──────────────────────────────────────────────────────────────────────────────
# POST /hitl/reject
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/reject",
    response_model=ReviewActionResponse,
    summary="Reject and discard a draft response",
)
def reject_review(body: RejectRequest) -> ReviewActionResponse:
    """
    Reject a pending review item.

    - **review_id**: UUID of the pending item.
    - **rejection_reason**: Explanation for why the draft was rejected.
    """
    q = get_queue()
    try:
        q.reject(
            review_id=body.review_id,
            rejection_reason=body.rejection_reason,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"review_id not found: {body.review_id!r}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return ReviewActionResponse(status="rejected")
