"""
frontend/pages/1_Patient_Assistant.py
──────────────────────────────────────
Patient-facing page: multilingual clinical query assistant.

Features:
- Language selector (en, es, hi)
- Country / jurisdiction selector
- Consent / billing form loader OR free-text query input
- Pipeline trace expander showing each stage
- Auto-polling when session is in HITL review (202 Pending)
"""

from __future__ import annotations

import time
from typing import Optional

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Patient Assistant",
    page_icon="🌍",
    layout="centered",
)

# ── Language / country configuration ─────────────────────────────────────────
LANGUAGE_OPTIONS = {
    "English": "en",
    "Español (Spanish)": "es",
    "हिन्दी (Hindi)": "hi",
}

COUNTRY_OPTIONS = {
    "United States 🇺🇸": "US",
    "Germany 🇩🇪": "DE",
    "France 🇫🇷": "FR",
    "India 🇮🇳": "IN",
    "Mexico 🇲🇽": "MX",
    "Spain 🇪🇸": "ES",
    "United Kingdom 🇬🇧": "GB",
    "Canada 🇨🇦": "CA",
}

DOC_TYPES = {
    "ICU Admission Consent": "consent_icu_admission",
    "Surgery Consent": "consent_surgery",
    "Billing & Deductible Explanation": "billing_deductible_explanation",
}

ESCALATION_POLL_INTERVAL = 3  # seconds

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🌍 Patient Assistant")
st.caption("Multilingual clinical support for international patients and travelers")
st.markdown("---")

# ── Sidebar: session info ─────────────────────────────────────────────────────
st.sidebar.header("Session")
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "pending_review_id" not in st.session_state:
    st.session_state.pending_review_id = None

if st.session_state.session_id:
    st.sidebar.text(f"Session: {st.session_state.session_id[:8]}…")
    if st.sidebar.button("New Session"):
        st.session_state.session_id = None
        st.session_state.pending_review_id = None
        st.rerun()

# ── Language & country selectors ──────────────────────────────────────────────
col_lang, col_country = st.columns(2)
with col_lang:
    lang_label = st.selectbox("Language", list(LANGUAGE_OPTIONS.keys()), index=0)
    language_code = LANGUAGE_OPTIONS[lang_label]
with col_country:
    country_label = st.selectbox("Country / Jurisdiction", list(COUNTRY_OPTIONS.keys()), index=0)
    country_code = COUNTRY_OPTIONS[country_label]

st.markdown("---")

# ── Mode selector ─────────────────────────────────────────────────────────────
mode = st.radio(
    "What do you need help with?",
    ["📋 Load a Consent / Billing Document", "💬 Ask a Clinical Question"],
    horizontal=True,
)

# ── Consent / billing document mode ──────────────────────────────────────────
if mode == "📋 Load a Consent / Billing Document":
    doc_label = st.selectbox("Document Type", list(DOC_TYPES.keys()))
    doc_type = DOC_TYPES[doc_label]

    if st.button("📄 Fetch Document"):
        try:
            resp = requests.get(
                f"{API_BASE}/documents/{doc_type}/{language_code}",
                timeout=10,
            )
            if resp.status_code == 200:
                doc = resp.json()
                st.subheader(doc["title"])
                st.text_area("Document Content", value=doc["content"], height=400)
            else:
                st.error(f"Error fetching document: {resp.status_code} — {resp.text}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Cannot reach the backend. Is `uvicorn backend.main:app` running?")

# ── Free-text clinical query mode ─────────────────────────────────────────────
else:
    # Polling for HITL escalation
    if st.session_state.pending_review_id:
        st.info(
            f"⏳ Your query is under clinical review (Session: `{st.session_state.session_id}`).\n\n"
            "Polling for result every few seconds…"
        )
        try:
            poll_resp = requests.get(
                f"{API_BASE}/agent/session/{st.session_state.session_id}",
                timeout=10,
            )
            if poll_resp.status_code == 200:
                poll_data = poll_resp.json()
                poll_status = poll_data.get("status", "pending")
                if poll_status == "approved":
                    st.success("✅ Your query has been reviewed and approved!")
                    st.markdown("### Response")
                    st.write(poll_data.get("response_text", ""))
                    st.session_state.pending_review_id = None
                elif poll_status == "rejected":
                    st.error(
                        "❌ Your query could not be answered at this time. "
                        "Please contact your care team directly."
                    )
                    st.session_state.pending_review_id = None
                else:
                    time.sleep(ESCALATION_POLL_INTERVAL)
                    st.rerun()
            else:
                st.warning("Could not poll session status. Will retry…")
                time.sleep(ESCALATION_POLL_INTERVAL)
                st.rerun()
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Cannot reach the backend.")
        st.stop()

    query_text = st.text_area(
        "Your question or concern",
        placeholder=(
            "e.g. 'I take metamizole at home. Is this allowed in the US?' "
            "/ 'Tomo metamizol en casa. ¿Está permitido en los Estados Unidos?'"
        ),
        height=120,
    )

    if st.button("🚀 Submit", disabled=not query_text.strip()):
        with st.spinner("Processing your query through the clinical pipeline…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/agent/query",
                    json={
                        "text": query_text,
                        "source_language": language_code,
                        "user_type": "patient",
                        "country": country_code,
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.session_id = data["session_id"]

                    st.success("✅ Response ready")
                    st.markdown("### Response")
                    st.write(data.get("response_text", ""))

                    with st.expander("🔍 Pipeline Trace (for transparency)"):
                        trace = data.get("pipeline_trace", {})
                        st.markdown(f"**Jurisdiction**: `{trace.get('jurisdiction', '')}`")
                        st.markdown(f"**PII Redacted**: `{trace.get('pii_redacted', False)}`")
                        st.markdown("**Translation (→ EN)**")
                        st.write(trace.get("translation", ""))
                        st.markdown("**Medical Interpretation**")
                        st.write(trace.get("medical_interpretation", ""))
                        st.markdown("**Cultural Context**")
                        st.write(trace.get("cultural_context", ""))
                        st.markdown("**Next Steps**")
                        st.write(trace.get("next_steps", ""))

                elif resp.status_code == 202:
                    # HITL escalation
                    data = resp.json()
                    st.session_state.session_id = data["session_id"]
                    st.session_state.pending_review_id = data["review_id"]
                    st.warning(f"⏳ {data.get('message', 'Your request is under review.')}")
                    time.sleep(ESCALATION_POLL_INTERVAL)
                    st.rerun()

                else:
                    st.error(f"Pipeline error {resp.status_code}: {resp.text}")

            except requests.exceptions.ConnectionError:
                st.error("⚠️ Cannot reach the backend. Is `uvicorn backend.main:app` running?")
            except requests.exceptions.Timeout:
                st.error("⚠️ Request timed out. The pipeline may still be running.")
