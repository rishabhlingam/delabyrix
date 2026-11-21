"""
backend/seed_demo_data.py
─────────────────────────
Repeatable demo-data seeder for the BI & Analytics Dashboard and HITL Queue.

Run from the repo root:
    python -m backend.seed_demo_data

What gets written and where
───────────────────────────
  SQLite table ``hitl_queue``        — HITL queue rows (pending/approved/rejected)
  SQLite table ``telemetry_events``  — live telemetry rows read by build_dashboard()
  JSON file   ``synthetic_data/patient_logs.json`` — baseline for proactive recs

The live dashboard metrics (escalation_rate, jurisdiction_breakdown,
top_medication_flags, avg_pipeline_stages_completed, queries_by_language live
portion, queries_by_user_type live portion) all come exclusively from
``telemetry_events``.  The seeder writes directly to that SQLite table so the
data is visible to the FastAPI server process when it next calls snapshot().

Both SQLite tables live in the same file: ``data/hitl_queue.db`` by default
(configured via settings.hitl_db_path).

Idempotency
───────────
  hitl_queue rows        : ``session_id LIKE 'demo-%'`` rows are deleted and
                           re-inserted on each run.
  telemetry_events rows  : the entire table is truncated and re-inserted so
                           counts never double.
  patient_logs.json      : file is fully overwritten.

  Test fixtures call ``get_telemetry_store().clear()`` which clears only the
  in-memory cache (and pins _hydrated=True so the DB is not re-read).  The DB
  rows written by the seeder are therefore invisible during test runs — tests
  remain fully isolated.

Privacy
───────
  Zero PII: no names, emails, phone numbers, real addresses, or real patient
  text.  All query templates are short synthetic strings with no personal data.
  Patient IDs are opaque counters (DEMO-00000 …).

Constraints respected
─────────────────────
  - status IN ('pending', 'approved', 'rejected')
  - user_type IN ('patient', 'provider', 'coordinator')
  - source_language is a BCP-47 tag
  - country is an ISO 3166-1 alpha-2 code
  - escalation_rules is a JSON list of string labels
  - pipeline_trace is a JSON object (no raw text)
  - All NOT NULL columns are always populated
  - HITL inserts are wrapped in a transaction; a failure leaves the DB unchanged
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Fixed random seed for reproducibility ─────────────────────────────────────
_RNG = random.Random(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
_SYNTHETIC_DATA_DIR = _REPO_ROOT / "synthetic_data"
_PATIENT_LOGS_PATH = _SYNTHETIC_DATA_DIR / "patient_logs.json"

# ── Volume ─────────────────────────────────────────────────────────────────────
_HITL_ROWS = 240       # rows in hitl_queue  (also drives telemetry_events 1-to-1)
_PATIENT_LOG_ROWS = 200  # rows in patient_logs.json (baseline for proactive recs)

# ── Locale map: (jurisdiction, ISO-3166-1 country, BCP-47 language) ───────────
# Weights reflect realistic multilingual usage patterns.
_LOCALE_MAP: List[Tuple[str, str, str]] = [
    ("US_FDA", "US", "en"),
    ("US_FDA", "US", "en"),
    ("US_FDA", "US", "en"),   # US/en weighted 3×
    ("EU_EMA", "ES", "es"),
    ("EU_EMA", "ES", "es"),
    ("EU_EMA", "DE", "de"),
    ("EU_EMA", "DE", "de"),
    ("EU_EMA", "FR", "fr"),
    ("EU_EMA", "GB", "en"),
    ("IN",     "IN", "hi"),
    ("IN",     "IN", "en"),
]

# ── Persona weights: ~70 % patient, ~30 % provider ────────────────────────────
_USER_TYPES: List[str] = ["patient"] * 7 + ["provider"] * 3

# ── Flagged cross-border medications ──────────────────────────────────────────
_FLAGGED_MEDS: List[str] = [
    "metamizole",
    "rosiglitazone",
    "codeine",
    "nimesulide",
    "dipyrone",
]

# ── HITL review-state pool: ~35 % pending, ~45 % approved, ~20 % rejected ────
_STATUS_POOL: List[str] = ["pending"] * 35 + ["approved"] * 45 + ["rejected"] * 20

# ── Escalation rule labels ─────────────────────────────────────────────────────
_ESCALATION_RULES: List[str] = [
    "rule_1_low_confidence",
    "rule_2_banned_medication",
    "rule_3_complex_medical_term",
    "rule_4_high_stakes_consent",
    "rule_5_ambiguous_jurisdiction",
]

# ── Synthetic query topic stubs (zero PII) ────────────────────────────────────
_QUERY_TEMPLATES: List[str] = [
    "Query regarding deductible and copay amounts.",
    "Medication dosage clarification for chronic condition.",
    "Explanation of consent form for surgical procedure.",
    "Insurance coverage for specialist referral.",
    "Cross-border prescription validity check.",
    "Inquiry about generic drug equivalents.",
    "Billing explanation for emergency room visit.",
    "Question about pre-authorisation requirement.",
    "Request for culturally adapted dietary guidance.",
    "Clarification on ICD-10 coded diagnosis.",
    "Jurisdiction-specific OTC medication rules.",
    "Post-operative care instruction translation.",
    "Paediatric dosing inquiry.",
    "Pharmacy dispensing restriction query.",
    "Prescription renewal eligibility check.",
]

# ── Patient log reference data ─────────────────────────────────────────────────
_DIET_FLAGS: List[str] = ["halal", "kosher", "vegan", "gluten-free", "vegetarian"]
_ICD10_CODES: List[str] = [
    "E00-E89", "I00-I99", "J00-J99", "K00-K95",
    "M00-M99", "N00-N99", "R00-R99", "F01-F99",
]
_NATIONALITIES: List[str] = ["US", "ES", "DE", "IN", "GB", "MX", "FR", "BR", "CN", "SA"]
_VISIT_TYPES: List[str] = ["outpatient", "inpatient", "ER", "telehealth"]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _past_dt(days_max: int = 60) -> datetime:
    """Random UTC datetime within the past ``days_max`` days."""
    secs = _RNG.randint(0, int(timedelta(days=days_max).total_seconds()))
    return datetime.now(tz=timezone.utc) - timedelta(seconds=secs)


def _pipeline_trace(jurisdiction: str, escalated: bool) -> str:
    """JSON blob for pipeline_trace — no raw text, no PII."""
    return json.dumps({
        "jurisdiction": jurisdiction,
        "pii_redacted": True,
        "translation": "stub",
        "medical_interpretation": "stub",
        "cultural_context": "stub",
        "next_steps": "stub",
        "escalated": escalated,
    })


def _draft(language: str, medication: Optional[str]) -> str:
    if medication:
        return (
            f"[DRAFT] Cross-border medication flag: {medication}. "
            "Jurisdiction check required before dispensing."
        )
    return f"[DRAFT] Clinical query response in language '{language}'. Pending review."


def _draft_en(medication: Optional[str]) -> str:
    if medication:
        return (
            f"[DRAFT-EN] Cross-border medication flag: {medication}. "
            "Jurisdiction check required before dispensing."
        )
    return "[DRAFT-EN] Clinical query response. Pending review."


# ──────────────────────────────────────────────────────────────────────────────
# Row generation
# ──────────────────────────────────────────────────────────────────────────────

def _make_hitl_rows(n: int) -> List[Dict]:
    """
    Generate n HITL queue row dicts.

    Each row is tagged with session_id prefix 'demo-' for idempotent cleanup.
    Escalation rate target: ~21 % (within the 18-25 % window).
    medication_flags is set directly from the chosen medication, NOT by
    scraping draft text, so telemetry_events always carries correct flags.
    """
    rows: List[Dict] = []
    for _ in range(n):
        jurisdiction, country, language = _RNG.choice(_LOCALE_MAP)
        user_type = _RNG.choice(_USER_TYPES)
        status = _RNG.choice(_STATUS_POOL)
        template = _RNG.choice(_QUERY_TEMPLATES)
        submitted_dt = _past_dt(60)

        # Escalation decision — ~21 % of all rows
        escalated: bool = _RNG.random() < 0.21
        medication: Optional[str] = _RNG.choice(_FLAGGED_MEDS) if escalated else None
        # Escalated rows always get rule_2 when a med is flagged, else rule_1/3/4/5
        if escalated and medication:
            esc_rules = ["rule_2_banned_medication"]
        elif escalated:
            esc_rules = [_RNG.choice([r for r in _ESCALATION_RULES if r != "rule_2_banned_medication"])]
        else:
            esc_rules = []

        reviewed_at: Optional[str] = None
        approved_response: Optional[str] = None
        reviewer_note: Optional[str] = None
        rejection_reason: Optional[str] = None
        rejection_reason_english: Optional[str] = None

        if status == "approved":
            reviewed_dt = submitted_dt + timedelta(hours=_RNG.randint(1, 48))
            reviewed_at = reviewed_dt.isoformat()
            approved_response = f"[APPROVED] Guidance provided re: {template[:40]}"
            reviewer_note = "Demo: reviewed and approved."
        elif status == "rejected":
            reviewed_dt = submitted_dt + timedelta(hours=_RNG.randint(1, 24))
            reviewed_at = reviewed_dt.isoformat()
            rejection_reason = "Insufficient context for safe guidance."
            if language != "en":
                rejection_reason_english = rejection_reason

        rows.append({
            # Idempotency marker: both review_id and session_id carry 'demo-' prefix
            "review_id":   f"demo-{uuid.UUID(int=_RNG.getrandbits(128))}",
            "session_id":  f"demo-{uuid.UUID(int=_RNG.getrandbits(128))}",
            "submitted_at": submitted_dt.isoformat(),
            "status":      status,
            "user_type":   user_type,
            "country":     country,
            "pipeline_trace": _pipeline_trace(jurisdiction, escalated),
            "draft_response": _draft(language, medication),
            "draft_response_english": _draft_en(medication) if language != "en" else None,
            "source_language": language,
            "redacted_original_text": f"[REDACTED] {template}",
            "english_inquiry": f"[REDACTED] {template}",
            "escalation_rules": json.dumps(esc_rules),
            "reviewed_at":   reviewed_at,
            "approved_response": approved_response,
            "reviewer_note": reviewer_note,
            "rejection_reason": rejection_reason,
            "rejection_reason_english": rejection_reason_english,
            # Carry medication alongside the row so _make_telemetry_events can use it
            # directly (not stored in DB — popped before insert).
            "_medication": medication,
        })
    return rows


def _make_patient_logs(n: int) -> List[Dict]:
    """Generate n synthetic patient log entries for the baseline JSON file."""
    logs: List[Dict] = []
    for i in range(n):
        diet: List[str] = [_RNG.choice(_DIET_FLAGS)] if _RNG.random() < 0.3 else []
        current_meds: List[str] = (
            [_RNG.choice(_FLAGGED_MEDS)] if _RNG.random() < 0.15 else []
        )
        logs.append({
            "patient_id": f"DEMO-{i:05d}",
            "age_band": _RNG.choice(["18-30", "31-45", "46-60", "61+"]),
            "nationality": _RNG.choice(_NATIONALITIES),
            "condition_codes": _RNG.sample(_ICD10_CODES, k=_RNG.randint(1, 2)),
            "medications_current": current_meds,
            "diet_flags": diet,
            "interaction_language": _RNG.choice(["en", "es", "de", "hi", "fr"]),
            "visit_type": _RNG.choice(_VISIT_TYPES),
        })
    return logs


# ──────────────────────────────────────────────────────────────────────────────
# Telemetry event generation (uses _medication directly — no text scraping)
# ──────────────────────────────────────────────────────────────────────────────

def _make_telemetry_events(hitl_rows: List[Dict]) -> list:
    """
    Build one TelemetryEvent per HITL row.

    medication_flags is taken directly from the row's '_medication' key so
    every escalated row with a flagged med carries the correct INN name in
    telemetry_events.  This is what populates top_medication_flags on the
    analytics dashboard.
    """
    from backend.analytics.aggregator import TelemetryEvent

    events = []
    for row in hitl_rows:
        trace = json.loads(row["pipeline_trace"])
        medication: Optional[str] = row["_medication"]
        med_flags: List[str] = [medication] if medication else []
        events.append(TelemetryEvent(
            language=row["source_language"],
            user_type=row["user_type"],
            jurisdiction=trace["jurisdiction"],
            escalated=trace["escalated"],
            medication_flags=med_flags,
            pipeline_stages_completed=_RNG.randint(3, 5),
            timestamp=datetime.fromisoformat(row["submitted_at"]),
        ))
    return events


# ──────────────────────────────────────────────────────────────────────────────
# SQLite helpers — hitl_queue
# ──────────────────────────────────────────────────────────────────────────────

_HITL_CREATE = """
CREATE TABLE IF NOT EXISTS hitl_queue (
    review_id              TEXT PRIMARY KEY,
    session_id             TEXT NOT NULL,
    submitted_at           TEXT NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'pending',
    user_type              TEXT NOT NULL,
    country                TEXT NOT NULL,
    pipeline_trace         TEXT NOT NULL DEFAULT '{}',
    draft_response         TEXT NOT NULL DEFAULT '',
    draft_response_english TEXT,
    source_language        TEXT NOT NULL DEFAULT 'en',
    redacted_original_text TEXT,
    english_inquiry        TEXT,
    escalation_rules       TEXT NOT NULL DEFAULT '[]',
    reviewed_at            TEXT,
    approved_response      TEXT,
    reviewer_note          TEXT,
    rejection_reason       TEXT,
    rejection_reason_english TEXT
);
"""

_HITL_MIGRATE = [
    "ALTER TABLE hitl_queue ADD COLUMN draft_response_english TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN source_language TEXT NOT NULL DEFAULT 'en';",
    "ALTER TABLE hitl_queue ADD COLUMN redacted_original_text TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN english_inquiry TEXT;",
    "ALTER TABLE hitl_queue ADD COLUMN rejection_reason_english TEXT;",
]

_HITL_DELETE_DEMO = "DELETE FROM hitl_queue WHERE session_id LIKE 'demo-%';"
_HITL_COUNT_DEMO  = "SELECT COUNT(*) FROM hitl_queue WHERE session_id LIKE 'demo-%';"
_HITL_INSERT = """
INSERT INTO hitl_queue (
    review_id, session_id, submitted_at, status,
    user_type, country, pipeline_trace, draft_response,
    draft_response_english, source_language,
    redacted_original_text, english_inquiry, escalation_rules,
    reviewed_at, approved_response, reviewer_note,
    rejection_reason, rejection_reason_english
) VALUES (
    :review_id, :session_id, :submitted_at, :status,
    :user_type, :country, :pipeline_trace, :draft_response,
    :draft_response_english, :source_language,
    :redacted_original_text, :english_inquiry, :escalation_rules,
    :reviewed_at, :approved_response, :reviewer_note,
    :rejection_reason, :rejection_reason_english
);
"""


def _seed_hitl(db_path: str, rows: List[Dict]) -> int:
    """
    Idempotently replace all 'demo-' session rows and return the inserted count.
    Pop the internal '_medication' key before passing rows to SQLite.
    """
    # Strip internal helper key — not a DB column
    db_rows = [{k: v for k, v in r.items() if k != "_medication"} for r in rows]

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_HITL_CREATE)
        for stmt in _HITL_MIGRATE:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
        with conn:
            conn.execute(_HITL_DELETE_DEMO)
            conn.executemany(_HITL_INSERT, db_rows)
        return conn.execute(_HITL_COUNT_DEMO).fetchone()[0]
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# SQLite helpers — telemetry_events
# ──────────────────────────────────────────────────────────────────────────────

def _seed_telemetry(db_path: str, events: list) -> int:
    """
    Truncate telemetry_events and bulk-insert ``events``.

    Writing directly to SQLite (not to the in-memory singleton) ensures the
    FastAPI server process sees the demo data on its next snapshot() call.
    Truncation guarantees idempotency — no duplicates on re-run.
    """
    from backend.analytics.aggregator import bulk_insert_telemetry_events, delete_demo_telemetry_events
    delete_demo_telemetry_events(db_path, [])
    return bulk_insert_telemetry_events(db_path, events)


# ──────────────────────────────────────────────────────────────────────────────
# Patient-log JSON
# ──────────────────────────────────────────────────────────────────────────────

def _seed_patient_logs(logs: List[Dict]) -> int:
    _SYNTHETIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PATIENT_LOGS_PATH.write_text(
        json.dumps(logs, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return len(logs)


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────

def _summarise(hitl_rows: List[Dict], telemetry_count: int, log_count: int) -> None:
    statuses     = Counter(r["status"] for r in hitl_rows)
    personas     = Counter(r["user_type"] for r in hitl_rows)
    jurisdictions = Counter(
        json.loads(r["pipeline_trace"])["jurisdiction"] for r in hitl_rows
    )
    escalated_n  = sum(
        1 for r in hitl_rows if json.loads(r["pipeline_trace"])["escalated"]
    )
    med_flags    = Counter(
        r["_medication"] for r in hitl_rows if r["_medication"]
    )
    esc_rate     = escalated_n / len(hitl_rows) if hitl_rows else 0.0

    print()
    print("=" * 60)
    print("  Demo Data Seeder — Summary")
    print("=" * 60)
    print(f"  HITL queue rows inserted  : {len(hitl_rows)}")
    print(f"  Telemetry events inserted : {telemetry_count}")
    print(f"  Patient log rows written  : {log_count}")
    print()
    print("  HITL review-state breakdown:")
    for s, n in sorted(statuses.items()):
        print(f"    {s:<10} {n:>4}")
    print()
    print("  Persona split:")
    for p, n in sorted(personas.items()):
        print(f"    {p:<12} {n:>4}  ({100*n/len(hitl_rows):.1f}%)")
    print()
    print("  Jurisdiction breakdown:")
    for j, n in sorted(jurisdictions.items()):
        print(f"    {j:<12} {n:>4}")
    print()
    print(f"  Escalation rate           : {esc_rate:.1%}")
    print()
    print("  Top medication flags (telemetry):")
    for med, n in med_flags.most_common():
        print(f"    {med:<18} {n:>4}")
    print("=" * 60)
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def seed() -> None:
    """Run the full demo seeder."""
    from backend.config import get_settings
    db_path = get_settings().hitl_db_path

    print(f"[seed] HITL / telemetry DB : {db_path}")
    print(f"[seed] Patient logs        : {_PATIENT_LOGS_PATH}")

    # 1. Generate all data with a fixed RNG seed (reproducible)
    hitl_rows    = _make_hitl_rows(_HITL_ROWS)
    patient_logs = _make_patient_logs(_PATIENT_LOG_ROWS)
    tel_events   = _make_telemetry_events(hitl_rows)

    # 2. Write HITL queue rows (idempotent: delete demo- rows, re-insert)
    hitl_n = _seed_hitl(db_path, hitl_rows)
    print(f"[seed] hitl_queue rows inserted    : {hitl_n}")

    # 3. Write telemetry events (idempotent: truncate, re-insert)
    tel_n = _seed_telemetry(db_path, tel_events)
    print(f"[seed] telemetry_events inserted   : {tel_n}")

    # 4. Write patient-log baseline JSON (always overwritten)
    log_n = _seed_patient_logs(patient_logs)
    print(f"[seed] patient_logs.json written   : {log_n}")

    # 5. Summary
    _summarise(hitl_rows, tel_n, log_n)


if __name__ == "__main__":
    seed()
