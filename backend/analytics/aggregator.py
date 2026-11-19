"""
backend/analytics/aggregator.py
─────────────────────────────────
Aggregate anonymized interaction telemetry for the BI dashboard.

Privacy rules (architecture.md §10):
  - Raw query text NEVER enters this module.
  - Only aggregate counts and enum values are stored.
  - Patient logs come from synthetic_data/patient_logs.json (zero real PII).
  - Live interaction telemetry is recorded via record_interaction() using
    only: language, user_type, country/jurisdiction, escalated flag,
    medication flags (INN names only), and pipeline stage count.

The in-memory telemetry store is a lightweight append-only list protected
by a threading.Lock — same pattern as HITLQueue.

Matches GET /analytics/dashboard contract (architecture.md §6.5).
Proactive care pattern analytics added per idea.txt requirement.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

_PATIENT_LOGS_PATH = (
    Path(__file__).parent.parent.parent / "synthetic_data" / "patient_logs.json"
)

# ICD-10 chapter labels for human-readable cluster names
_ICD10_LABELS: Dict[str, str] = {
    "A00-B99": "Infectious & Parasitic",
    "C00-D49": "Neoplasms",
    "D50-D89": "Blood Disorders",
    "E00-E89": "Endocrine & Metabolic",
    "F01-F99": "Mental & Behavioural",
    "G00-G99": "Nervous System",
    "H00-H59": "Eye Disorders",
    "H60-H95": "Ear Disorders",
    "I00-I99": "Circulatory System",
    "J00-J99": "Respiratory System",
    "K00-K95": "Digestive System",
    "L00-L99": "Skin Disorders",
    "M00-M99": "Musculoskeletal",
    "N00-N99": "Genitourinary",
    "O00-O9A": "Pregnancy & Childbirth",
    "P00-P96": "Perinatal Conditions",
    "Q00-Q99": "Congenital Anomalies",
    "R00-R99": "Symptoms & Signs",
    "S00-T88": "Injury & Poisoning",
    "V00-Y99": "External Causes",
    "Z00-Z99": "Health Status Factors",
}

# Known cross-border conflict medications (a subset of the synthetic registry)
_CROSS_BORDER_CONFLICT_MEDS = {
    "metamizole", "domperidone", "phenylbutazone", "nimesulide",
    "clenbuterol", "sibutramine", "rimonabant", "tegaserod",
}


# ──────────────────────────────────────────────────────────────────────────────
# Live telemetry event (zero PII)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TelemetryEvent:
    """One interaction event — strictly no raw text or patient identifiers."""
    language: str            # BCP-47 tag
    user_type: str           # patient | provider | coordinator
    jurisdiction: str        # US_FDA | EU_EMA | OTHER
    escalated: bool
    medication_flags: List[str] = field(default_factory=list)   # INN names only
    pipeline_stages_completed: int = 4
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


# ──────────────────────────────────────────────────────────────────────────────
# In-memory telemetry store (singleton)
# ──────────────────────────────────────────────────────────────────────────────

class _TelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[TelemetryEvent] = []

    def record(self, event: TelemetryEvent) -> None:
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> List[TelemetryEvent]:
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        """Test helper — clears all telemetry."""
        with self._lock:
            self._events.clear()


_store_instance: Optional[_TelemetryStore] = None
_store_lock = threading.Lock()


def get_telemetry_store() -> _TelemetryStore:
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = _TelemetryStore()
    return _store_instance


def record_interaction(
    language: str,
    user_type: str,
    jurisdiction: str,
    escalated: bool,
    medication_flags: Optional[List[str]] = None,
    pipeline_stages_completed: int = 4,
) -> None:
    """
    Record a single pipeline interaction event.

    Called from the agent router immediately after the pipeline completes.
    Raw query text must NEVER be passed here.
    """
    get_telemetry_store().record(
        TelemetryEvent(
            language=language,
            user_type=user_type,
            jurisdiction=jurisdiction,
            escalated=escalated,
            medication_flags=medication_flags or [],
            pipeline_stages_completed=pipeline_stages_completed,
        )
    )


# ──────────────────────────────────────────────────────────────────────────────
# Patient log baseline loader (synthetic_data/patient_logs.json)
# ──────────────────────────────────────────────────────────────────────────────

def _load_patient_logs() -> List[dict]:
    """Load synthetic patient logs; return empty list if file missing."""
    try:
        return json.loads(_PATIENT_LOGS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ──────────────────────────────────────────────────────────────────────────────
# Proactive care pattern analytics
# ──────────────────────────────────────────────────────────────────────────────

def _build_proactive_recommendations(logs: List[dict]) -> List[Dict]:
    """
    Analyse patient logs grouped by nationality, interaction_language,
    visit_type, condition_codes, and diet_flags to surface emerging care
    needs as actionable, zero-PII recommendations.

    Returns a list of recommendation dicts, each with:
      category       : "dietary" | "icd10_cluster" | "medication_conflict"
      title          : short label
      description    : one-sentence narrative
      affected_groups: list of nationality / language / visit_type identifiers
      magnitude      : integer count driving the recommendation
    """
    if not logs:
        return []

    recommendations: List[Dict] = []

    # ── 1. Dietary accommodation demand ──────────────────────────────────────
    diet_by_flag: Counter = Counter()
    diet_by_nationality: Dict[str, Counter] = {}
    for log in logs:
        nat = log.get("nationality", "XX")
        for flag in log.get("diet_flags", []):
            diet_by_flag[flag] += 1
            diet_by_nationality.setdefault(nat, Counter())[flag] += 1

    for diet_flag, total_count in diet_by_flag.most_common(5):
        if total_count < 2:
            continue
        top_nationalities = sorted(
            diet_by_nationality.items(),
            key=lambda kv: kv[1].get(diet_flag, 0),
            reverse=True,
        )[:3]
        affected = [nat for nat, _ in top_nationalities if _.get(diet_flag, 0) > 0]
        recommendations.append({
            "category": "dietary",
            "title": f"High demand: {diet_flag} dietary accommodation",
            "description": (
                f"{total_count} patients require {diet_flag} meals. "
                f"Top requesting nationalities: {', '.join(affected) or 'varied'}. "
                "Consider proactive dietary intake forms in relevant languages."
            ),
            "affected_groups": affected,
            "magnitude": total_count,
        })

    # ── 2. High-frequency ICD-10 clusters by visitor group ───────────────────
    icd_by_code: Counter = Counter()
    icd_by_visit: Dict[str, Counter] = {}
    icd_by_lang: Dict[str, Counter] = {}
    for log in logs:
        visit = log.get("visit_type", "outpatient")
        lang = log.get("interaction_language", "en")
        for code in log.get("condition_codes", []):
            icd_by_code[code] += 1
            icd_by_visit.setdefault(visit, Counter())[code] += 1
            icd_by_lang.setdefault(lang, Counter())[code] += 1

    for icd_code, total_count in icd_by_code.most_common(5):
        if total_count < 3:
            continue
        label = _ICD10_LABELS.get(icd_code, icd_code)
        top_visits = [
            vt for vt, cnt in sorted(
                icd_by_visit.items(),
                key=lambda kv: kv[1].get(icd_code, 0),
                reverse=True,
            )[:2]
            if cnt.get(icd_code, 0) > 0
        ]
        top_langs = [
            lg for lg, cnt in sorted(
                icd_by_lang.items(),
                key=lambda kv: kv[1].get(icd_code, 0),
                reverse=True,
            )[:2]
            if cnt.get(icd_code, 0) > 0
        ]
        recommendations.append({
            "category": "icd10_cluster",
            "title": f"Emerging cluster: {label} ({icd_code})",
            "description": (
                f"{total_count} patient encounters coded {icd_code} ({label}). "
                f"Highest in visit types: {', '.join(top_visits) or 'varied'}. "
                f"Primary interaction languages: {', '.join(top_langs) or 'varied'}. "
                "Consider specialty protocol briefings for care teams."
            ),
            "affected_groups": top_visits + top_langs,
            "magnitude": total_count,
        })

    # ── 3. Cross-border medication conflict hotspots ──────────────────────────
    conflict_meds: Counter = Counter()
    conflict_by_nationality: Dict[str, Counter] = {}
    for log in logs:
        nat = log.get("nationality", "XX")
        for med in log.get("medications_current", []):
            if med.lower() in _CROSS_BORDER_CONFLICT_MEDS:
                conflict_meds[med.lower()] += 1
                conflict_by_nationality.setdefault(nat, Counter())[med.lower()] += 1

    for med_name, total_count in conflict_meds.most_common(5):
        if total_count < 1:
            continue
        top_nats = [
            nat for nat, cnt in sorted(
                conflict_by_nationality.items(),
                key=lambda kv: kv[1].get(med_name, 0),
                reverse=True,
            )[:3]
            if cnt.get(med_name, 0) > 0
        ]
        recommendations.append({
            "category": "medication_conflict",
            "title": f"Cross-border conflict hotspot: {med_name}",
            "description": (
                f"{total_count} patients currently on {med_name}, "
                "which has divergent FDA/EMA regulatory status. "
                f"Highest prevalence in nationalities: {', '.join(top_nats) or 'varied'}. "
                "Flag for jurisdiction check before dispensing."
            ),
            "affected_groups": top_nats,
            "magnitude": total_count,
        })

    # Sort by descending magnitude so the most critical items surface first
    recommendations.sort(key=lambda r: r["magnitude"], reverse=True)
    return recommendations


# ──────────────────────────────────────────────────────────────────────────────
# Dashboard aggregation
# ──────────────────────────────────────────────────────────────────────────────

def build_dashboard(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    jurisdiction_filter: Optional[str] = None,
) -> dict:
    """
    Combine patient-log baseline trends with live telemetry to produce the
    analytics dashboard payload.

    Returns a dict matching architecture.md §6.5 — no raw text, no PII.
    Includes a ``proactive_recommendations`` list from patient-log analysis.
    """
    # ── Live telemetry snapshot ───────────────────────────────────────────────
    events = get_telemetry_store().snapshot()

    # Apply date filters (telemetry only — patient logs are static baseline)
    if date_from:
        events = [e for e in events if e.timestamp.date() >= date_from]
    if date_to:
        events = [e for e in events if e.timestamp.date() <= date_to]
    if jurisdiction_filter:
        jf = jurisdiction_filter.upper()
        events = [e for e in events if e.jurisdiction.upper() == jf]

    # ── Patient log baseline (language distribution) ──────────────────────────
    logs = _load_patient_logs()
    log_lang_counts: Counter = Counter()
    log_user_type_counts: Counter = Counter({"patient": len(logs)})  # all logs = patients
    for log in logs:
        lang = log.get("interaction_language", "en")
        log_lang_counts[lang] += 1

    # ── Live counters ─────────────────────────────────────────────────────────
    live_lang: Counter = Counter(e.language for e in events)
    live_user_type: Counter = Counter(e.user_type for e in events)
    live_jurisdiction: Counter = Counter(e.jurisdiction for e in events)
    live_med_flags: Counter = Counter(
        flag for e in events for flag in e.medication_flags
    )
    live_escalations = sum(1 for e in events if e.escalated)
    live_stages = [e.pipeline_stages_completed for e in events]

    total_live = len(events)
    total_baseline = len(logs)
    total_queries = total_live + total_baseline

    # Merge language counts: baseline (patient logs) + live
    merged_lang: Dict[str, int] = dict(log_lang_counts)
    for lang, cnt in live_lang.items():
        merged_lang[lang] = merged_lang.get(lang, 0) + cnt

    # Merge user_type: baseline all-patient + live
    merged_user_type: Dict[str, int] = dict(log_user_type_counts)
    for ut, cnt in live_user_type.items():
        merged_user_type[ut] = merged_user_type.get(ut, 0) + cnt

    # Top medication flags: live telemetry only (baseline has no "flags")
    top_med_flags = [
        {"medication": med, "count": cnt, "status": "flagged"}
        for med, cnt in live_med_flags.most_common(10)
    ]

    escalation_rate = (live_escalations / total_live) if total_live > 0 else 0.0
    avg_stages = (sum(live_stages) / len(live_stages)) if live_stages else 4.0

    # ── Proactive care recommendations from patient-log analysis ─────────────
    proactive_recommendations = _build_proactive_recommendations(logs)

    return {
        "total_queries": total_queries,
        "escalation_rate": round(escalation_rate, 4),
        "queries_by_language": merged_lang,
        "queries_by_user_type": merged_user_type,
        "top_medication_flags": top_med_flags,
        "avg_pipeline_stages_completed": round(avg_stages, 2),
        "jurisdiction_breakdown": dict(live_jurisdiction),
        "proactive_recommendations": proactive_recommendations,
    }
