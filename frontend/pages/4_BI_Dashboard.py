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
7. Emerging Care Needs & Proactive Service Recommendations (section)
   - Dietary accommodation demand (bar chart)
   - High-frequency ICD-10 clusters by visitor group (bar chart)
   - Cross-border medication conflict hotspots (bar chart)
   - Recommendation cards with magnitude and affected groups
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

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# Section: Emerging Care Needs & Proactive Service Recommendations
# ══════════════════════════════════════════════════════════════════════════════

st.subheader("🔮 Emerging Care Needs & Proactive Service Recommendations")
st.caption(
    "Pattern analysis from anonymized patient logs — dietary accommodation demand, "
    "high-frequency ICD-10 clusters by visitor group, and cross-border medication "
    "conflict hotspots. Zero PII."
)

recs = data.get("proactive_recommendations", [])

if not recs:
    st.info(
        "No proactive recommendations computed yet. "
        "Make sure `synthetic_data/patient_logs.json` exists "
        "(run `python scripts/generate_synthetic_data.py`)."
    )
else:
    # ── Split by category ─────────────────────────────────────────────────────
    dietary_recs = [r for r in recs if r.get("category") == "dietary"]
    icd_recs = [r for r in recs if r.get("category") == "icd10_cluster"]
    conflict_recs = [r for r in recs if r.get("category") == "medication_conflict"]

    # ── Chart: Dietary accommodation demand ──────────────────────────────────
    if dietary_recs:
        st.markdown("#### 🍽️ Dietary Accommodation Demand")
        diet_col_chart, diet_col_cards = st.columns([3, 2])
        with diet_col_chart:
            diet_labels = [
                r["title"].replace("High demand: ", "").replace(" dietary accommodation", "")
                for r in dietary_recs
            ]
            diet_counts = [r["magnitude"] for r in dietary_recs]
            fig_diet = px.bar(
                x=diet_counts,
                y=diet_labels,
                orientation="h",
                labels={"x": "Patient Count", "y": "Dietary Flag"},
                color=diet_counts,
                color_continuous_scale="Greens",
                title="Patient Dietary Requirements",
            )
            fig_diet.update_layout(height=max(200, 60 * len(dietary_recs)),
                                   coloraxis_showscale=False)
            st.plotly_chart(fig_diet, use_container_width=True)
        with diet_col_cards:
            for rec in dietary_recs[:3]:
                with st.container(border=True):
                    st.markdown(f"**{rec['title']}**")
                    st.caption(rec["description"])
                    if rec.get("affected_groups"):
                        st.markdown(
                            "Nationalities: " +
                            " · ".join(f"`{g}`" for g in rec["affected_groups"])
                        )

    # ── Chart: ICD-10 clusters ────────────────────────────────────────────────
    if icd_recs:
        st.markdown("#### 🩺 High-Frequency ICD-10 Clusters by Visitor Group")
        icd_col_chart, icd_col_cards = st.columns([3, 2])
        with icd_col_chart:
            icd_labels = [r["title"].replace("Emerging cluster: ", "") for r in icd_recs]
            icd_counts = [r["magnitude"] for r in icd_recs]
            fig_icd = px.bar(
                x=icd_labels,
                y=icd_counts,
                labels={"x": "ICD-10 Chapter", "y": "Patient Count"},
                color=icd_counts,
                color_continuous_scale="Blues",
                title="Encounter Volume by ICD-10 Chapter",
            )
            fig_icd.update_layout(height=320, coloraxis_showscale=False,
                                  xaxis_tickangle=-30)
            st.plotly_chart(fig_icd, use_container_width=True)
        with icd_col_cards:
            for rec in icd_recs[:3]:
                with st.container(border=True):
                    st.markdown(f"**{rec['title']}**")
                    st.caption(rec["description"])
                    if rec.get("affected_groups"):
                        st.markdown(
                            "Groups: " +
                            " · ".join(f"`{g}`" for g in rec["affected_groups"])
                        )

    # ── Chart: Medication conflict hotspots ───────────────────────────────────
    if conflict_recs:
        st.markdown("#### ⚠️ Cross-Border Medication Conflict Hotspots")
        conf_col_chart, conf_col_cards = st.columns([3, 2])
        with conf_col_chart:
            conf_labels = [
                r["title"].replace("Cross-border conflict hotspot: ", "")
                for r in conflict_recs
            ]
            conf_counts = [r["magnitude"] for r in conflict_recs]
            fig_conf = px.bar(
                x=conf_counts,
                y=conf_labels,
                orientation="h",
                labels={"x": "Patient Count", "y": "Medication (INN)"},
                color=conf_counts,
                color_continuous_scale="Reds",
                title="Patients on Cross-Jurisdiction Conflict Medications",
            )
            fig_conf.update_layout(height=max(200, 60 * len(conflict_recs)),
                                   coloraxis_showscale=False)
            st.plotly_chart(fig_conf, use_container_width=True)
        with conf_col_cards:
            for rec in conflict_recs[:3]:
                with st.container(border=True):
                    st.markdown(f"**{rec['title']}**")
                    st.caption(rec["description"])
                    if rec.get("affected_groups"):
                        st.markdown(
                            "Top nationalities: " +
                            " · ".join(f"`{g}`" for g in rec["affected_groups"])
                        )

    # ── All recommendations summary table ────────────────────────────────────
    with st.expander("📋 All recommendations (table view)"):
        rows = [
            {
                "Category": r["category"],
                "Title": r["title"],
                "Magnitude": r["magnitude"],
                "Affected Groups": ", ".join(r.get("affected_groups", [])),
                "Description": r["description"],
            }
            for r in recs
        ]
        st.dataframe(rows, use_container_width=True)

st.markdown("---")
st.caption(
    "🔒 Privacy: this dashboard contains only aggregate counts, language codes, "
    "and medication INN names. No raw query text or patient identifiers are present."
)
