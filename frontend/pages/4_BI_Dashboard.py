"""
frontend/pages/4_BI_Dashboard.py
──────────────────────────────────
BI Dashboard: interactive Plotly/Streamlit charts from GET /analytics/dashboard.

Charts:
1. Queries by language (bar)
2. User persona breakdown (pie)
3. Top flagged medications — US FDA vs EU EMA (bar)
4. Escalation rate gauge (metric)
5. Jurisdiction breakdown (bar)
6. Avg pipeline stages completed (metric)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import requests
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="BI Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 BI Analytics Dashboard")
st.caption("Aggregate, anonymized interaction metrics — zero raw query text or PII")
st.markdown("---")


# ── Filters ───────────────────────────────────────────────────────────────────
filter_col1, filter_col2, filter_col3 = st.columns(3)

with filter_col1:
    date_from: Optional[date] = st.date_input(
        "Date From",
        value=None,
        help="Filter live telemetry from this date",
    )
with filter_col2:
    date_to: Optional[date] = st.date_input(
        "Date To",
        value=None,
        help="Filter live telemetry up to this date",
    )
with filter_col3:
    jurisdiction_filter = st.selectbox(
        "Jurisdiction Filter",
        ["All", "US_FDA", "EU_EMA"],
    )

params: dict = {}
if date_from:
    params["date_from"] = str(date_from)
if date_to:
    params["date_to"] = str(date_to)
if jurisdiction_filter != "All":
    params["jurisdiction"] = jurisdiction_filter

if st.button("🔄 Refresh Dashboard"):
    st.rerun()


# ── Fetch data ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def fetch_dashboard(params_key: str) -> Optional[dict]:
    """Cached dashboard fetch (30s TTL)."""
    import json
    p = json.loads(params_key)
    try:
        resp = requests.get(f"{API_BASE}/analytics/dashboard", params=p, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None
    except requests.exceptions.ConnectionError:
        return None


import json as _json
params_key = _json.dumps(params, sort_keys=True)
data = fetch_dashboard(params_key)

if data is None:
    st.error(
        "⚠️ Cannot load dashboard data. "
        "Make sure the backend is running: `uvicorn backend.main:app`"
    )
    st.stop()


# ── Top metrics row ───────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Queries", data.get("total_queries", 0))
m2.metric(
    "Escalation Rate",
    f"{data.get('escalation_rate', 0.0):.1%}",
    delta=None,
)
m3.metric(
    "Avg Pipeline Stages",
    f"{data.get('avg_pipeline_stages_completed', 4.0):.1f}",
)
med_flags_count = sum(
    entry.get("count", 0) for entry in data.get("top_medication_flags", [])
)
m4.metric("Total Medication Flags", med_flags_count)

st.markdown("---")

# ── Charts ────────────────────────────────────────────────────────────────────
if not HAS_PLOTLY:
    st.warning(
        "Plotly is not installed. Install it with `pip install plotly` for interactive charts."
    )
    st.json(data)
    st.stop()

row1_left, row1_right = st.columns(2)

# Chart 1: Queries by language
with row1_left:
    st.subheader("Queries by Language")
    lang_data = data.get("queries_by_language", {})
    if lang_data:
        fig = px.bar(
            x=list(lang_data.keys()),
            y=list(lang_data.values()),
            labels={"x": "Language Code", "y": "Count"},
            color=list(lang_data.keys()),
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No language data available yet.")

# Chart 2: User persona breakdown (pie)
with row1_right:
    st.subheader("User Persona Breakdown")
    user_data = data.get("queries_by_user_type", {})
    if user_data:
        fig = px.pie(
            values=list(user_data.values()),
            names=list(user_data.keys()),
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No user type data available yet.")

row2_left, row2_right = st.columns(2)

# Chart 3: Top flagged medications
with row2_left:
    st.subheader("Top Flagged Medications")
    flags = data.get("top_medication_flags", [])
    if flags:
        meds = [f["medication"] for f in flags]
        counts = [f["count"] for f in flags]
        fig = px.bar(
            x=counts,
            y=meds,
            orientation="h",
            labels={"x": "Flag Count", "y": "Medication (INN)"},
            color=counts,
            color_continuous_scale="Reds",
        )
        fig.update_layout(height=320, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No medication flags recorded yet.")

# Chart 4: Jurisdiction breakdown
with row2_right:
    st.subheader("Jurisdiction Breakdown")
    jur_data = data.get("jurisdiction_breakdown", {})
    if jur_data:
        fig = px.bar(
            x=list(jur_data.keys()),
            y=list(jur_data.values()),
            labels={"x": "Jurisdiction", "y": "Count"},
            color=list(jur_data.keys()),
            color_discrete_map={"US_FDA": "#1f77b4", "EU_EMA": "#2ca02c", "OTHER": "#ff7f0e"},
        )
        fig.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No jurisdiction data from live telemetry yet.")

st.markdown("---")

# ── Escalation rate gauge ─────────────────────────────────────────────────────
st.subheader("Escalation Rate Gauge")
escalation_rate = data.get("escalation_rate", 0.0)
fig_gauge = go.Figure(go.Indicator(
    mode="gauge+number+delta",
    value=escalation_rate * 100,
    number={"suffix": "%"},
    title={"text": "Escalation Rate (% of live queries)"},
    gauge={
        "axis": {"range": [0, 100]},
        "bar": {"color": "darkblue"},
        "steps": [
            {"range": [0, 10], "color": "lightgreen"},
            {"range": [10, 30], "color": "lightyellow"},
            {"range": [30, 100], "color": "lightcoral"},
        ],
        "threshold": {
            "line": {"color": "red", "width": 4},
            "thickness": 0.75,
            "value": 30,
        },
    },
))
fig_gauge.update_layout(height=280)
st.plotly_chart(fig_gauge, use_container_width=True)

st.caption(
    "🔒 Privacy: this dashboard contains only aggregate counts, language codes, "
    "and medication INN names. No raw query text or patient identifiers are present."
)
