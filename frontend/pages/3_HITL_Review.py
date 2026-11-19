"""
frontend/pages/3_HITL_Review.py
─────────────────────────────────
Care coordinator HITL review queue.

Features:
- Read GET /hitl/queue to list pending items
- Side-by-side pipeline trace inspection
- Approve (with optional edit) or Reject actions
"""

from __future__ import annotations

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="HITL Review Queue",
    page_icon="🗂️",
    layout="wide",
)

st.title("🗂️ HITL Review Queue")
st.caption("Care coordinator review queue — human-in-the-loop oversight")
st.markdown("---")

# ── Load queue ────────────────────────────────────────────────────────────────
def load_queue() -> dict:
    try:
        resp = requests.get(f"{API_BASE}/hitl/queue", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"Error loading queue: {resp.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot reach the backend.")
    return {"pending_count": 0, "items": []}


col_refresh, col_count = st.columns([1, 5])
with col_refresh:
    if st.button("🔄 Refresh Queue"):
        st.rerun()

queue_data = load_queue()
pending_count = queue_data.get("pending_count", 0)
items = queue_data.get("items", [])

with col_count:
    if pending_count == 0:
        st.success("✅ No pending items — queue is clear.")
    else:
        st.warning(f"**{pending_count}** item(s) pending review")

st.markdown("---")

# ── Queue items ───────────────────────────────────────────────────────────────
if not items:
    st.info("No items in the review queue.")
else:
    for idx, item in enumerate(items):
        review_id = item.get("review_id", "")
        session_id = item.get("session_id", "")
        submitted_at = item.get("submitted_at", "")
        user_type = item.get("user_type", "")
        country = item.get("country", "")
        pipeline_trace = item.get("pipeline_trace", {})
        draft_response = item.get("draft_response", "")
        escalation_rules = item.get("escalation_rules", [])

        with st.expander(
            f"Item {idx + 1}: `{review_id[:8]}…` | {user_type} | {country} | {submitted_at[:19]}",
            expanded=(idx == 0),
        ):
            left_col, right_col = st.columns(2)

            with left_col:
                st.markdown("#### Pipeline Trace")
                st.markdown(f"**Jurisdiction**: `{pipeline_trace.get('jurisdiction', '')}`")
                st.markdown(f"**PII Redacted**: `{pipeline_trace.get('pii_redacted', False)}`")

                st.markdown("**Medical Interpretation**")
                st.text_area(
                    "med_interp",
                    value=pipeline_trace.get("medical_interpretation", ""),
                    height=100,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"trace_med_{review_id}",
                )
                st.markdown("**Cultural Context**")
                st.text_area(
                    "cult_ctx",
                    value=pipeline_trace.get("cultural_context", ""),
                    height=80,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"trace_cult_{review_id}",
                )
                st.markdown("**Next Steps**")
                st.text_area(
                    "next_steps",
                    value=pipeline_trace.get("next_steps", ""),
                    height=80,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"trace_steps_{review_id}",
                )

                if escalation_rules:
                    st.markdown("**Escalation Rules Triggered**")
                    for rule in escalation_rules:
                        st.markdown(f"- `{rule}`")

            with right_col:
                st.markdown("#### Draft Response (editable)")
                edited_response = st.text_area(
                    "Edit draft response before approving",
                    value=draft_response,
                    height=200,
                    key=f"draft_{review_id}",
                )
                reviewer_note = st.text_input(
                    "Reviewer note (optional, internal)",
                    key=f"note_{review_id}",
                )
                rejection_reason = st.text_input(
                    "Rejection reason (required to reject)",
                    key=f"reject_reason_{review_id}",
                )

                approve_col, reject_col = st.columns(2)

                with approve_col:
                    if st.button("✅ Approve", key=f"approve_{review_id}"):
                        try:
                            resp = requests.post(
                                f"{API_BASE}/hitl/approve",
                                json={
                                    "review_id": review_id,
                                    "approved_response": edited_response,
                                    "reviewer_note": reviewer_note or None,
                                },
                                timeout=10,
                            )
                            if resp.status_code == 200:
                                st.success(f"✅ Item `{review_id[:8]}…` approved.")
                                st.rerun()
                            else:
                                st.error(f"Error: {resp.status_code} — {resp.text}")
                        except requests.exceptions.ConnectionError:
                            st.error("⚠️ Cannot reach the backend.")

                with reject_col:
                    if st.button("❌ Reject", key=f"reject_{review_id}"):
                        if not rejection_reason.strip():
                            st.warning("Please provide a rejection reason.")
                        else:
                            try:
                                resp = requests.post(
                                    f"{API_BASE}/hitl/reject",
                                    json={
                                        "review_id": review_id,
                                        "rejection_reason": rejection_reason,
                                    },
                                    timeout=10,
                                )
                                if resp.status_code == 200:
                                    st.error(f"❌ Item `{review_id[:8]}…` rejected.")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {resp.status_code} — {resp.text}")
                            except requests.exceptions.ConnectionError:
                                st.error("⚠️ Cannot reach the backend.")
