"""
frontend/pages/1_Patient_Assistant.py
──────────────────────────────────────
Patient-facing page: multilingual clinical query assistant.

Features:
- Language selector (en, es, hi)
- Country / jurisdiction selector
- Consent / billing form loader OR free-text query input
- Pipeline trace expander showing each stage
- Rerun-based non-blocking HITL polling
- Input form always visible; rejection shown as red alert with reason
"""

import time

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

ESCALATION_POLL_INTERVAL = 3  # seconds between polling reruns

# ── Page header ───────────────────────────────────────────────────────────────
st.title("🌍 Patient Assistant")
st.caption("Multilingual clinical support for international patients and travelers")
st.markdown("---")

# ── Session state initialisation ──────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = None
# True during the POST pass (spinner only, no prior output visible).
if "submitting" not in st.session_state:
    st.session_state.submitting = False
# Form values stashed for the POST pass (widget values don't survive rerun).
if "_queued_query" not in st.session_state:
    st.session_state._queued_query = None
if "_queued_lang" not in st.session_state:
    st.session_state._queued_lang = None
if "_queued_country" not in st.session_state:
    st.session_state._queued_country = None
# Set to session_id while awaiting HITL review; None otherwise.
if "pending_session_id" not in st.session_state:
    st.session_state.pending_session_id = None
# Populated on 200 OK (direct or approved-after-HITL).
if "response_text" not in st.session_state:
    st.session_state.response_text = None
if "pipeline_trace" not in st.session_state:
    st.session_state.pipeline_trace = None
# Populated on HITL rejection: {"reason": str | None}
if "rejected_info" not in st.session_state:
    st.session_state.rejected_info = None
# POST-level error message.
if "error_msg" not in st.session_state:
    st.session_state.error_msg = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.header("Session")
if st.session_state.session_id:
    st.sidebar.text(f"Session: {st.session_state.session_id[:8]}…")
    if st.sidebar.button("New Session"):
        st.session_state.session_id = None
        st.session_state.submitting = False
        st.session_state._queued_query = None
        st.session_state._queued_lang = None
        st.session_state._queued_country = None
        st.session_state.pending_session_id = None
        st.session_state.response_text = None
        st.session_state.pipeline_trace = None
        st.session_state.rejected_info = None
        st.session_state.error_msg = None
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
    # Input form is always visible regardless of state.
    query_text = st.text_area(
        "Your question or concern",
        placeholder=(
            "e.g. 'I take metamizole at home. Is this allowed in the US?' "
            "/ 'Tomo metamizol en casa. ¿Está permitido en los Estados Unidos?'"
        ),
        height=120,
    )

    submit_clicked = st.button("🚀 Submit", disabled=not query_text.strip())

    # All output widgets live inside this single placeholder.
    # Replacing its contents (or leaving it empty) is atomic from the
    # browser's perspective — no old child nodes persist across branches.
    output_slot = st.empty()

    # ── Branch A: Submit clicked ──────────────────────────────────────────────
    # Null every output key and rerun immediately.  This pass draws nothing
    # inside output_slot, so the browser shows a blank output area at once.
    if submit_clicked:
        st.session_state.response_text = None
        st.session_state.pipeline_trace = None
        st.session_state.rejected_info = None
        st.session_state.error_msg = None
        st.session_state.pending_session_id = None
        st.session_state.submitting = True
        st.session_state._queued_query = query_text
        st.session_state._queued_lang = language_code
        st.session_state._queued_country = country_code
        st.rerun()

    # ── Branch B: Fire the POST ───────────────────────────────────────────────
    elif st.session_state.submitting:
        with output_slot.container():
            with st.spinner("Processing your query through the clinical pipeline…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/agent/query",
                        json={
                            "text": st.session_state._queued_query,
                            "source_language": st.session_state._queued_lang,
                            "user_type": "patient",
                            "country": st.session_state._queued_country,
                        },
                        timeout=60,
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.session_id = data["session_id"]
                        st.session_state.response_text = data.get("response_text", "")
                        st.session_state.pipeline_trace = data.get("pipeline_trace", {})

                    elif resp.status_code == 202:
                        data = resp.json()
                        st.session_state.session_id = data["session_id"]
                        st.session_state.pending_session_id = data["session_id"]

                    else:
                        st.session_state.error_msg = (
                            f"Pipeline error {resp.status_code}: {resp.text}"
                        )

                except requests.exceptions.ConnectionError:
                    st.session_state.error_msg = (
                        "⚠️ Cannot reach the backend. "
                        "Is `uvicorn backend.main:app` running?"
                    )
                except requests.exceptions.Timeout:
                    st.session_state.error_msg = (
                        "⚠️ Request timed out. The pipeline may still be running."
                    )

        st.session_state.submitting = False
        st.session_state._queued_query = None
        st.session_state._queued_lang = None
        st.session_state._queued_country = None
        st.rerun()

    # ── Branch C: HITL polling ────────────────────────────────────────────────
    elif st.session_state.pending_session_id:
        with output_slot.container():
            st.info(
                f"⏳ Your query is under clinical review "
                f"(Session: `{st.session_state.pending_session_id}`).\n\n"
                "Polling for result every few seconds…"
            )
        try:
            poll_resp = requests.get(
                f"{API_BASE}/agent/session/{st.session_state.pending_session_id}",
                timeout=10,
            )
            if poll_resp.status_code == 200:
                poll_data = poll_resp.json()
                poll_status = poll_data.get("status", "pending")

                if poll_status == "approved":
                    st.session_state.response_text = poll_data.get("response_text", "")
                    st.session_state.pipeline_trace = None
                    st.session_state.pending_session_id = None
                    st.rerun()

                elif poll_status == "rejected":
                    st.session_state.rejected_info = {
                        "reason": poll_data.get("rejection_reason") or None
                    }
                    st.session_state.pending_session_id = None
                    st.rerun()

                else:
                    time.sleep(ESCALATION_POLL_INTERVAL)
                    st.rerun()
            else:
                time.sleep(ESCALATION_POLL_INTERVAL)
                st.rerun()

        except requests.exceptions.ConnectionError:
            with output_slot.container():
                st.error("⚠️ Cannot reach the backend while polling.")

    # ── Branch D: HITL rejection ──────────────────────────────────────────────
    elif st.session_state.rejected_info is not None:
        reason = st.session_state.rejected_info.get("reason") or ""
        reason_line = f"\n\n**Reason:** {reason}" if reason else ""
        with output_slot.container():
            st.error(
                "🚫 **Rejected by Clinical Reviewer**\n\n"
                "Your request was reviewed by our clinical team and could not be "
                f"answered at this time.{reason_line}\n\n"
                "Please consult a healthcare provider directly or submit a revised "
                "question with more context."
            )

    # ── Branch E: Response ready ──────────────────────────────────────────────
    elif st.session_state.response_text is not None:
        with output_slot.container():
            st.success("✅ Response ready")
            st.markdown("### Response")
            st.write(st.session_state.response_text)

            if st.session_state.pipeline_trace:
                with st.expander("🔍 Pipeline Trace (for transparency)"):
                    trace = st.session_state.pipeline_trace
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

    # ── Branch F: POST-level error ────────────────────────────────────────────
    elif st.session_state.error_msg is not None:
        with output_slot.container():
            st.error(st.session_state.error_msg)
