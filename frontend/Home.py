"""
frontend/Home.py
─────────────────
Streamlit multi-page app — landing page.

Displays the system overview and lets users identify their role before
navigating to the appropriate page.
"""

import streamlit as st

st.set_page_config(
    page_title="Multilingual Clinical AI Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar navigation hint ───────────────────────────────────────────────────
st.sidebar.title("Navigation")
st.sidebar.info(
    "Use the pages in the sidebar to navigate:\n\n"
    "• **Patient Assistant** — multilingual form & query support\n"
    "• **Provider Support** — culturally adapted clinical explanations\n"
    "• **HITL Review** — care coordinator review queue\n"
    "• **BI Dashboard** — aggregate interaction metrics\n"
    "• **Registry Explorer** — cross-border medication lookup"
)

# ── Hero header ───────────────────────────────────────────────────────────────
st.title("🏥 Multilingual Clinical AI Agent & BI Platform")
st.caption("Powered by IBM watsonx.ai · Granite 3 · Cross-Border Medication Registry")

st.markdown("---")

# ── Role selector ──────────────────────────────────────────────────────────────
st.subheader("Who are you?")
col1, col2, col3 = st.columns(3)

with col1:
    st.info(
        "### 🌍 Foreign Patient / International Traveler\n\n"
        "Get consent forms and billing documents explained in your language, "
        "check if your medications are allowed in this country, and understand "
        "your care options.\n\n"
        "👉 Go to **Patient Assistant**"
    )

with col2:
    st.success(
        "### 👩‍⚕️ Healthcare Provider\n\n"
        "Generate culturally adapted procedure explanations, review local "
        "policy checklists, and check for cross-border drug alerts for your "
        "international patients.\n\n"
        "👉 Go to **Provider Support**"
    )

with col3:
    st.warning(
        "### 🗂️ Care Coordinator / Administrator\n\n"
        "Review AI-generated responses that require human oversight, approve "
        "or edit draft responses, monitor system-wide BI metrics, and "
        "explore the medication registry.\n\n"
        "👉 Go to **HITL Review** or **BI Dashboard**"
    )

st.markdown("---")

# ── System overview ────────────────────────────────────────────────────────────
st.subheader("System Overview")

overview_col, diagram_col = st.columns([3, 2])

with overview_col:
    st.markdown(
        """
        This platform provides **multilingual, compliance-aware** clinical AI support
        across three user groups, powered by IBM **watsonx.ai** (Granite 3).

        **Agentic Pipeline** (5 stages):
        1. **Stage 0 — PII Redaction**: strips personal identifiers before any LLM call
        2. **Stage 1 — Translation**: renders the query in English for downstream stages
        3. **Stage 2 — Medical Interpretation**: extracts clinical meaning + registry check
        4. **Stage 3 — Cultural Context**: adapts framing for jurisdiction and culture
        5. **Stage 4 — Next Steps**: generates role-appropriate guidance

        **Human-in-the-Loop (HITL)**: high-risk outputs (banned medications, low
        confidence, ICU/surgery topics) are automatically escalated for coordinator
        review before reaching the patient.

        **Jurisdiction Support**: US FDA · EU EMA · dynamic registry sync
        """
    )

with diagram_col:
    st.markdown(
        """
        **Privacy Guarantees**
        - Zero real patient PII in development
        - Raw query text never enters analytics
        - Medication registry uses INN names only
        - All secrets managed via `.env` (never committed)

        **Supported Languages**
        | Code | Language |
        |------|----------|
        | `en` | English  |
        | `es` | Spanish  |
        | `hi` | Hindi    |

        **Jurisdictions**
        | Code | Registry |
        |------|----------|
        | `US_FDA` | FDA Orange Book |
        | `EU_EMA` | EU Union Register |
        """
    )

st.markdown("---")
st.caption(
    "Backend: FastAPI · http://localhost:8000 · "
    "Docs: [/docs](http://localhost:8000/docs)"
)
