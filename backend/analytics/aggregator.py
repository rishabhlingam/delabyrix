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

Telemetry is also persisted to a ``telemetry_events`` table in the same
SQLite database as the HITL queue (``data/hitl_queue.db`` by default).
This allows the demo seeder — which runs as a separate process — to write
events that the FastAPI server process will see on its next snapshot.

Matches GET /analytics/dashboard contract (architecture.md §6.5).
Proactive care pattern analytics added per idea.txt requirement.
"""

from __future__ import annotations

import json
import sqlite3
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
# SQLite persistence helpers for telemetry
# ──────────────────────────────────────────────────────────────────────────────

_CREATE_TELEMETRY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS telemetry_events (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    language                TEXT NOT NULL DEFAULT 'en',
    user_type               TEXT NOT NULL DEFAULT 'patient',
    jurisdiction            TEXT NOT NULL DEFAULT 'OTHER',
    escalated               INTEGER NOT NULL DEFAULT 0,
    medication_flags        TEXT NOT NULL DEFAULT '[]',
    pipeline_stages_completed INTEGER NOT NULL DEFAULT 4,
    timestamp               TEXT NOT NULL
);
"""

_INSERT_TELEMETRY_SQL = """
INSERT INTO telemetry_events
    (language, user_type, jurisdiction, escalated,
     medication_flags, pipeline_stages_completed, timestamp)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_TELEMETRY_SQL = """
SELECT language, user_type, jurisdiction, escalated,
       medication_flags, pipeline_stages_completed, timestamp
FROM telemetry_events;
"""

_DELETE_DEMO_TELEMETRY_SQL = """
DELETE FROM telemetry_events WHERE json_extract(medication_flags, '$') IS NOT NULL
    AND id IN (
        SELECT id FROM telemetry_events ORDER BY id DESC LIMIT 999999
    )
    AND timestamp >= datetime('now', '-61 days');
"""


def _get_db_path() -> str:
    """Return the configured HITL DB path (same DB for telemetry)."""
    from backend.config import get_settings
    return get_settings().hitl_db_path


def _ensure_telemetry_table(db_path: str) -> None:
    """Create the telemetry_events table if it does not already exist."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TELEMETRY_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def _persist_event(db_path: str, event: "TelemetryEvent") -> None:
    """Append a single TelemetryEvent row to the SQLite table."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TELEMETRY_TABLE_SQL)
        conn.execute(
            _INSERT_TELEMETRY_SQL,
            (
                event.language,
                event.user_type,
                event.jurisdiction,
                1 if event.escalated else 0,
                json.dumps(event.medication_flags),
                event.pipeline_stages_completed,
                event.timestamp.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _load_events_from_db(db_path: str) -> List["TelemetryEvent"]:
    """Read all rows from telemetry_events and return as TelemetryEvent objects."""
    if not Path(db_path).exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_CREATE_TELEMETRY_TABLE_SQL)
        conn.commit()
        rows = conn.execute(_SELECT_TELEMETRY_SQL).fetchall()
    finally:
        conn.close()

    events: List[TelemetryEvent] = []
    for row in rows:
        try:
            ts = datetime.fromisoformat(row["timestamp"])
        except ValueError:
            ts = datetime.now(tz=timezone.utc)
        events.append(
            TelemetryEvent(
                language=row["language"],
                user_type=row["user_type"],
                jurisdiction=row["jurisdiction"],
                escalated=bool(row["escalated"]),
                medication_flags=json.loads(row["medication_flags"] or "[]"),
                pipeline_stages_completed=row["pipeline_stages_completed"],
                timestamp=ts,
            )
        )
    return events


def bulk_insert_telemetry_events(db_path: str, events: List["TelemetryEvent"]) -> int:
    """
    Insert a batch of TelemetryEvent rows directly into the SQLite table.

    Used by the demo seeder so that events written in one process are visible
    to the FastAPI server process on its next snapshot() call.
    Returns the number of rows inserted.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TELEMETRY_TABLE_SQL)
        rows = [
            (
                e.language,
                e.user_type,
                e.jurisdiction,
                1 if e.escalated else 0,
                json.dumps(e.medication_flags),
                e.pipeline_stages_completed,
                e.timestamp.isoformat(),
            )
            for e in events
        ]
        with conn:
            conn.executemany(_INSERT_TELEMETRY_SQL, rows)
        return len(rows)
    finally:
        conn.close()


def delete_demo_telemetry_events(db_path: str, demo_prefix_timestamps: List[str]) -> int:
    """
    Delete telemetry rows whose timestamp matches the demo-seeded set.

    Because telemetry rows carry no session_id tag, idempotency is achieved
    by truncating ALL rows and re-inserting — same approach as the HITL seeder.
    Returns the number of rows deleted.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_CREATE_TELEMETRY_TABLE_SQL)
        conn.commit()
        with conn:
            cur = conn.execute("DELETE FROM telemetry_events;")
            return cur.rowcount
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# In-memory telemetry store (singleton)
# ──────────────────────────────────────────────────────────────────────────────

class _TelemetryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: List[TelemetryEvent] = []
        self._hydrated = False   # True once we've loaded from the DB once

    def _hydrate(self) -> None:
        """Load all persisted events from the DB into memory (called once)."""
        try:
            db_path = _get_db_path()
            db_events = _load_events_from_db(db_path)
            self._events = db_events
        except Exception:
            pass  # If DB is unavailable, fall back to empty in-memory state
        self._hydrated = True

    def record(self, event: TelemetryEvent) -> None:
        with self._lock:
            self._events.append(event)
        # Persist to DB so other processes (e.g. the seeder) and server restarts
        # see the same events.
        try:
            _persist_event(_get_db_path(), event)
        except Exception:
            pass  # Non-fatal: in-memory event is still counted for this process

    def snapshot(self) -> List[TelemetryEvent]:
        with self._lock:
            if not self._hydrated:
                self._hydrate()
            return list(self._events)

    def clear(self) -> None:
        """Test helper — clears in-memory events only (does not touch the DB)."""
        with self._lock:
            self._events.clear()
            self._hydrated = True  # prevent re-hydration from DB during tests


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
