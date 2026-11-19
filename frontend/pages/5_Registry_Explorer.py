"""
frontend/pages/5_Registry_Explorer.py
────────────────────────────────────────
Cross-border medication registry explorer.

Features:
- Search by medication name (INN or brand)
- Filter by jurisdiction (US_FDA / EU_EMA / All)
- Status-highlighted table (banned = red, restricted = orange, approved = green)
- Side-by-side US vs EU regulatory divergence view
- Therapeutic alternatives display
"""

from __future__ import annotations

from typing import Optional

import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Registry Explorer",
    page_icon="💊",
    layout="wide",
)

st.title("💊 Cross-Border Medication Registry Explorer")
st.caption(
    "Search the synthetic medication registry for cross-jurisdictional "
    "regulatory divergences between US FDA and EU EMA."
)
st.markdown("---")

# ── Status color helper ───────────────────────────────────────────────────────
STATUS_COLORS = {
    "approved": "🟢",
    "restricted": "🟡",
    "banned": "🔴",
    "delisted": "⚪",
}


def status_badge(status: str) -> str:
    icon = STATUS_COLORS.get(status, "❓")
    return f"{icon} {status.capitalize()}"


# ── Search & filter controls ──────────────────────────────────────────────────
search_col, jur_col, page_col = st.columns([3, 2, 1])

with search_col:
    search_query = st.text_input(
        "Search by medication name (INN or brand)",
        placeholder="e.g. metamizole, domperidone, Valium",
    )
with jur_col:
    jur_filter = st.selectbox("Jurisdiction", ["All", "US_FDA", "EU_EMA"])
with page_col:
    page_num = st.number_input("Page", min_value=1, value=1, step=1)

page_size = 20

# ── Single medication lookup ──────────────────────────────────────────────────
if search_query.strip():
    st.subheader(f"Results for: `{search_query}`")
    jurs_to_check = ["US_FDA", "EU_EMA"] if jur_filter == "All" else [jur_filter]
    results = {}

    for jur in jurs_to_check:
        try:
            resp = requests.get(
                f"{API_BASE}/registry/check",
                params={"medication_name": search_query.strip(), "jurisdiction": jur},
                timeout=10,
            )
            if resp.status_code == 200:
                results[jur] = resp.json()
            elif resp.status_code == 404:
                results[jur] = None
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except requests.exceptions.ConnectionError:
            st.error("⚠️ Cannot reach the backend.")
            st.stop()

    if not any(results.values()):
        st.info(f"No records found for `{search_query}` in the selected jurisdiction(s).")
    else:
        # Side-by-side US vs EU comparison
        cols = st.columns(len([k for k, v in results.items() if v is not None]))
        col_idx = 0
        for jur, rec in results.items():
            if rec is None:
                continue
            with cols[col_idx]:
                st.markdown(f"### {jur.replace('_', ' ')}")
                status = rec.get("status", "unknown")
                st.markdown(f"**Status**: {status_badge(status)}")
                st.markdown(f"**Generic (INN)**: `{rec.get('name_generic', '')}`")
                st.markdown(f"**Brand Name**: {rec.get('name_brand', '')}")
                st.markdown(f"**Registry**: {rec.get('source_registry', '')}")
                st.markdown(f"**Last Updated**: {rec.get('last_updated', '')}")

                reason = rec.get("restriction_reason")
                if reason:
                    st.markdown("**Restriction/Ban Reason**")
                    st.warning(reason)

                alts = rec.get("therapeutic_alternatives", [])
                if alts:
                    st.markdown("**Therapeutic Alternatives**")
                    st.markdown(", ".join(f"`{a}`" for a in alts))
            col_idx += 1

        # Divergence alert
        if len(results) == 2 and results.get("US_FDA") and results.get("EU_EMA"):
            us_status = results["US_FDA"].get("status", "")
            eu_status = results["EU_EMA"].get("status", "")
            if us_status != eu_status:
                st.error(
                    f"⚠️ **Regulatory Divergence Detected**: "
                    f"US FDA `{us_status}` ≠ EU EMA `{eu_status}`. "
                    "Verify the patient's jurisdiction before prescribing or dispensing."
                )

    st.markdown("---")

# ── Full registry table ───────────────────────────────────────────────────────
st.subheader("Full Registry" if jur_filter == "All" else f"Registry — {jur_filter}")

list_params: dict = {"page": page_num, "page_size": page_size}
if jur_filter != "All":
    list_params["jurisdiction"] = jur_filter

try:
    list_resp = requests.get(f"{API_BASE}/registry/list", params=list_params, timeout=10)
    if list_resp.status_code == 200:
        list_data = list_resp.json()
        records = list_data.get("records", [])
        total = list_data.get("total", 0)

        st.caption(
            f"Showing page {page_num} · {len(records)} of {total} record(s)"
        )

        if records:
            # Build display rows
            rows = []
            for rec in records:
                status_val = rec.get("status", "unknown")
                rows.append({
                    "Status": status_badge(status_val),
                    "Generic (INN)": rec.get("name_generic", ""),
                    "Brand": rec.get("name_brand", ""),
                    "Jurisdiction": rec.get("jurisdiction", ""),
                    "Source Registry": rec.get("source_registry", ""),
                    "Last Updated": rec.get("last_updated", ""),
                    "Alternatives": ", ".join(rec.get("therapeutic_alternatives", [])),
                })

            st.dataframe(rows, use_container_width=True)

            # Pagination controls
            nav_prev, nav_info, nav_next = st.columns([1, 2, 1])
            with nav_prev:
                if page_num > 1 and st.button("◀ Previous"):
                    st.query_params["page"] = str(page_num - 1)
            with nav_info:
                total_pages = (total + page_size - 1) // page_size
                st.caption(f"Page {page_num} of {total_pages}")
            with nav_next:
                if page_num < total_pages and st.button("Next ▶"):
                    st.query_params["page"] = str(page_num + 1)
        else:
            st.info("No records found.")

    else:
        st.error(f"Error loading registry: {list_resp.status_code}")

except requests.exceptions.ConnectionError:
    st.error("⚠️ Cannot reach the backend. Is `uvicorn backend.main:app` running?")

st.markdown("---")
st.markdown(
    "**Legend**: 🟢 Approved · 🟡 Restricted · 🔴 Banned · ⚪ Delisted\n\n"
    "Data source: synthetic cross-border medication registry "
    "(based on publicly documented FDA / EMA regulatory decisions)."
)
