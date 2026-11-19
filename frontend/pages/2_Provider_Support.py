"""
frontend/pages/2_Provider_Support.py
──────────────────────────────────────
Healthcare provider page: generate culturally adapted explanations,
local policy checklists, and view flagged drug alerts for international
patients.
"""

from __future__ import annotations

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Provider Support",
    page_icon="👩‍⚕️",
    layout="wide",
)

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

PATIENT_LANG_OPTIONS = {
    "English": "en",
    "Español (Spanish)": "es",
    "हिन्दी (Hindi)": "hi",
}

st.title("👩‍⚕️ Provider Support")
st.caption("Culturally adapted clinical communication tools for healthcare providers")
st.markdown("---")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_explain, tab_policy, tab_meds = st.tabs([
    "📋 Procedure Explanation",
    "📜 Local Policy Checklist",
    "💊 Drug Alert Checker",
])


# ── Tab 1: Procedure explanation ──────────────────────────────────────────────
with tab_explain:
    st.subheader("Generate Culturally Adapted Procedure Explanation")
    st.markdown(
        "Describe a procedure or clinical situation in plain English. "
        "The pipeline will adapt the explanation for the patient's language, "
        "culture, and jurisdiction."
    )

    col_lang, col_country = st.columns(2)
    with col_lang:
        patient_lang_label = st.selectbox(
            "Patient Language", list(PATIENT_LANG_OPTIONS.keys()),
            key="explain_lang",
        )
        patient_lang = PATIENT_LANG_OPTIONS[patient_lang_label]
    with col_country:
        patient_country_label = st.selectbox(
            "Patient Country", list(COUNTRY_OPTIONS.keys()),
            key="explain_country",
        )
        patient_country = COUNTRY_OPTIONS[patient_country_label]

    procedure_text = st.text_area(
        "Procedure or clinical context (in English)",
        placeholder=(
            "e.g. 'The patient requires a laparoscopic cholecystectomy under general anaesthesia. "
            "Explain the procedure, risks, and recovery to them in culturally sensitive terms.'"
        ),
        height=120,
        key="explain_text",
    )

    if st.button("Generate Explanation", key="btn_explain"):
        if not procedure_text.strip():
            st.warning("Please enter a procedure description.")
        else:
            with st.spinner("Generating culturally adapted explanation…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/agent/query",
                        json={
                            "text": procedure_text,
                            "source_language": "en",
                            "user_type": "provider",
                            "country": patient_country,
                        },
                        timeout=60,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.success("Explanation generated")
                        st.markdown("### For Provider Review")
                        st.write(data.get("response_text", ""))

                        with st.expander("Pipeline Trace"):
                            trace = data.get("pipeline_trace", {})
                            for stage, label in [
                                ("medical_interpretation", "Medical Interpretation"),
                                ("cultural_context", "Cultural Context"),
                                ("next_steps", "Next Steps"),
                            ]:
                                st.markdown(f"**{label}**")
                                st.write(trace.get(stage, ""))

                    elif resp.status_code == 202:
                        data = resp.json()
                        st.info(
                            f"⏳ This explanation has been flagged for clinical review.\n\n"
                            f"Review ID: `{data.get('review_id', '')}`"
                        )
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")
                except requests.exceptions.ConnectionError:
                    st.error("⚠️ Cannot reach the backend.")


# ── Tab 2: Local policy checklist ─────────────────────────────────────────────
with tab_policy:
    st.subheader("Local Policy Checklist")
    st.markdown(
        "Retrieve consent or billing documents applicable to the patient's "
        "language and jurisdiction for pre-procedure review."
    )

    col_doc, col_lang2, col_country2 = st.columns(3)
    with col_doc:
        doc_type = st.selectbox(
            "Document Type",
            [
                "consent_icu_admission",
                "consent_surgery",
                "billing_deductible_explanation",
            ],
            key="policy_doc",
        )
    with col_lang2:
        policy_lang_label = st.selectbox(
            "Language", list(PATIENT_LANG_OPTIONS.keys()),
            key="policy_lang",
        )
        policy_lang = PATIENT_LANG_OPTIONS[policy_lang_label]
    with col_country2:
        st.selectbox("Country", list(COUNTRY_OPTIONS.keys()), key="policy_country")

    if st.button("Load Policy Document", key="btn_policy"):
        try:
            resp = requests.get(
                f"{API_BASE}/documents/{doc_type}/{policy_lang}",
                timeout=10,
            )
            if resp.status_code == 200:
                doc = resp.json()
                st.markdown(f"### {doc['title']}")
                st.text_area("Document", value=doc["content"], height=350, key="policy_doc_content")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Cannot reach the backend.")


# ── Tab 3: Drug alert checker ─────────────────────────────────────────────────
with tab_meds:
    st.subheader("Cross-Border Drug Alert Checker")
    st.markdown(
        "Check a patient's medication list against the target jurisdiction registry. "
        "Flags banned, restricted, or delisted medications."
    )

    medication_input = st.text_input(
        "Medication name (INN or brand)",
        placeholder="e.g. metamizole, domperidone, Valium",
        key="med_name",
    )
    jurisdiction = st.selectbox(
        "Target Jurisdiction",
        ["US_FDA", "EU_EMA"],
        key="med_jurisdiction",
    )

    if st.button("🔍 Check Medication", key="btn_med_check"):
        if not medication_input.strip():
            st.warning("Please enter a medication name.")
        else:
            try:
                resp = requests.get(
                    f"{API_BASE}/registry/check",
                    params={
                        "medication_name": medication_input.strip(),
                        "jurisdiction": jurisdiction,
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    rec = resp.json()
                    status_val = rec.get("status", "unknown")
                    if status_val == "approved":
                        st.success(f"✅ **{rec['name_generic']}** ({rec['name_brand']}) — `{status_val}` in {jurisdiction}")
                    elif status_val in ("restricted", "delisted"):
                        st.warning(
                            f"⚠️ **{rec['name_generic']}** — `{status_val}` in {jurisdiction}\n\n"
                            f"Reason: {rec.get('restriction_reason', 'See registry details')}"
                        )
                        if rec.get("therapeutic_alternatives"):
                            st.markdown(
                                "**Alternatives**: " + ", ".join(rec["therapeutic_alternatives"])
                            )
                    elif status_val == "banned":
                        st.error(
                            f"🚫 **{rec['name_generic']}** — **BANNED** in {jurisdiction}\n\n"
                            f"Reason: {rec.get('restriction_reason', '')}"
                        )
                        if rec.get("therapeutic_alternatives"):
                            st.markdown(
                                "**Alternatives**: " + ", ".join(rec["therapeutic_alternatives"])
                            )
                elif resp.status_code == 404:
                    st.info(f"ℹ️ No record found for `{medication_input}` in `{jurisdiction}`.")
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except requests.exceptions.ConnectionError:
                st.error("⚠️ Cannot reach the backend.")
