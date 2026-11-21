"""
backend/seed_demo_data.py
─────────────────────────
Repeatable demo-data seeder for the BI & Analytics Dashboard and HITL Queue.

Run from the repo root:
    python -m backend.seed_demo_data

Idempotency
───────────
  HITL SQLite rows: identified by ``session_id LIKE 'demo-%'``.
    Re-running deletes all matching rows and re-inserts a fresh set.
  Patient logs JSON: ``synthetic_data/patient_logs.json`` is fully rewritten.
  Telemetry store: in-memory; seeder injects events on each run.
    (The in-memory store is wiped between test runs by test fixtures, so there
    is no interaction with the test suite.)

Privacy
───────
  Zero PII: no names, emails, phone numbers, real addresses, or real patient
  text.  All query templates are short synthetic strings with no personal data.

Constraints respected
─────────────────────
  - status IN ('pending', 'approved', 'rejected')
  - user_type IN ('patient', 'provider', 'coordinator')
  - source_language is a BCP-47 tag
  - country is an ISO 3166-1 alpha-2 code
  - escalation_rules is a JSON list of string labels
  - pipeline_trace is a JSON object (no raw text)
  - All NOT NULL columns are always populated
  - Wrapped in a transaction; a failure leaves the DB unchanged
"""

from __future__ import annotations

import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Fixed random seed for reproducibility ─────────────────────────────────────
_RNG = random.Random(42)

# ── Paths ──────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent
_SYNTHETIC_DATA_DIR = _REPO_ROOT / "synthetic_data"
_PATIENT_LOGS_PATH = _SYNTHETIC_DATA_DIR / "patient_logs.json"

# ── Demo-row marker ────────────────────────────────────────────────────────────
_DEMO_SESSION_PREFIX = "demo-"

# ── Volume ─────────────────────────────────────────────────────────────────────
_HITL_ROWS = 240          # rows in hitl_queue
_PATIENT_LOG_ROWS = 200   # rows in patient_logs.json

# ── Jurisdictions / language mapping ──────────────────────────────────────────
# (jurisdiction_code, country_alpha2, language_bcp47)
_LOCALE_MAP: List[Tuple[str, str, str]] = [
    ("US_FDA", "US", "en"),
    ("US_FDA", "US", "en"),
    ("US_FDA", "US", "en"),   # US weighted 3x
    ("EU_EMA", "ES", "es"),
    ("EU_EMA", "ES", "es"),
    ("EU_EMA", "DE", "de"),
    ("EU_EMA", "DE", "de"),
    ("EU_EMA", "FR", "fr"),
    ("EU_EMA", "GB", "en"),
    ("IN",     "IN", "hi"),
    ("IN",     "IN", "en"),
]

# ── Persona weights: ~70% patient, ~30% provider ──────────────────────────────
_USER_TYPES = (["patient"] * 7) + (["provider"] * 3)

# ── Flagged cross-border medications ──────────────────────────────────────────
_FLAGGED_MEDS = [
    "metamizole",
    "rosiglitazone",
    "codeine",
    "nimesulide",
    "dipyrone",
]

# ── HITL review-state distribution ────────────────────────────────────────────
# pending ~35%, approved ~45%, rejected ~20%
_STATUS_POOL = (
    ["pending"]  * 35 +
    ["approved"] * 45 +
    ["rejected"] * 20
)

# ── Escalation rules (triggered labels) ───────────────────────────────────────
_ESCALATION_RULES = [
    "rule_1_low_confidence",
    "rule_2_banned_medication",
    "rule_3_complex_medical_term",
    "rule_4_high_stakes_consent",
    "rule_5_ambiguous_jurisdiction",
]

# ── Synthetic query templates (zero PII) ─────────────────────────────────────
_QUERY_TEMPLATES = [
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

# ── Patient log diet flags ─────────────────────────────────────────────────────
_DIET_FLAGS = ["halal", "kosher", "vegan", "gluten-free", "vegetarian"]

# ── Patient log ICD-10 chapters ───────────────────────────────────────────────
_ICD10_CODES = [
    "E00-E89", "I00-I99", "J00-J99", "K00-K95",
    "M00-M99", "N00-N99", "R00-R99", "F01-F99",
]

# ── Patient log nationalities ─────────────────────────────────────────────────
_NATIONALITIES = ["US", "ES", "DE", "IN", "GB", "MX", "FR", "BR", "CN", "SA"]

# ── Patient log visit types ───────────────────────────────────────────────────
_VISIT_TYPES = ["outpatient", "inpatient", "ER", "telehealth"]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _random_past_dt(days_back_max: int = 60, days_back_min: int = 0) -> datetime:
    """Return a random UTC datetime within the past ``days_back_max`` days."""
    offset_seconds = _RNG.randint(
        int(timedelta(days=days_back_min).total_seconds()),
        int(timedelta(days=days_back_max).total_seconds()),
    )
    return datetime.now(tz=timezone.utc) - timedelta(seconds=offset_seconds)


def _build_pipeline_trace(jurisdiction: str, escalated: bool) -> Dict:
    """Return a minimal pipeline-trace dict (no raw text, no PII)."""
    return {
        "jurisdiction": jurisdiction,
        "pii_redacted": True,
        "translation": "stub",
        "medical_interpretation": "stub",
        "cultural_context": "stub",
        "next_steps": "stub",
        "escalated": escalated,
    }


def _draft_response(language: str, medication: Optional[str]) -> str:
    """Return a short, synthetic draft response — no PII."""
    if medication:
        return (
            f"[DRAFT] Cross-border medication flag: {medication}. "
            "Jurisdiction check required before dispensing."
        )
    return f"[DRAFT] Clinical query response in language '{language}'. Pending review."


def _draft_response_english(medication: Optional[str]) -> str:
    if medication:
        return (
            f"[DRAFT-EN] Cross-border medication flag: {medication}. "
            "Jurisdiction check required before dispensing."
        )
    return "[DRAFT-EN] Clinical query response. Pending review."


def _english_inquiry(template: str) -> str:
    return f"[REDACTED] {template}"


# ──────────────────────────────────────────────────────────────────────────────
# Generate HITL rows
# ──────────────────────────────────────────────────────────────────────────────

def _generate_hitl_rows(n: int) -> List[Dict]:
    """
    Generate ``n`` HITL queue row dicts, tagged with the demo session prefix.

    Escalation rate target: ~18-25% of rows have a flagged medication.
    Review-state distribution: ~35% pending, ~45% approved, ~20% rejected.
    """
    rows = []
    for i in range(n):
        jurisdiction, country, language = _RNG.choice(_LOCALE_MAP)
        user_type = _RNG.choice(_USER_TYPES)
        status = _RNG.choice(_STATUS_POOL)
        template = _RNG.choice(_QUERY_TEMPLATES)
        submitted_dt = _random_past_dt(days_back_max=60)

        # Escalation: ~21% chance of flagged medication
        escalated = _RNG.random() < 0.21
        medication: Optional[str] = _RNG.choice(_FLAGGED_MEDS) if escalated else None
        escalation_rules = (
            [_RNG.choice(_ESCALATION_RULES[:3])] if escalated else []
        )

        review_id = f"demo-{uuid.UUID(int=_RNG.getrandbits(128))}"
        session_id = f"{_DEMO_SESSION_PREFIX}{uuid.UUID(int=_RNG.getrandbits(128))}"

        reviewed_at: Optional[str] = None
        approved_response: Optional[str] = None
        reviewer_note: Optional[str] = None
        rejection_reason: Optional[str] = None
        rejection_reason_english: Optional[str] = None

        if status == "approved":
            reviewed_dt = submitted_dt + timedelta(hours=_RNG.randint(1, 48))
            reviewed_at = reviewed_dt.isoformat()
            approved_response = (
                f"[APPROVED] Guidance provided for query re: {template[:40]}"
            )
            reviewer_note = "Demo: reviewed and approved."
        elif status == "rejected":
            reviewed_dt = submitted_dt + timedelta(hours=_RNG.randint(1, 24))
            reviewed_at = reviewed_dt.isoformat()
            rejection_reason = "Insufficient context for safe guidance."
            if language != "en":
                rejection_reason_english = rejection_reason

        rows.append({
            "review_id": review_id,
            "session_id": session_id,
            "submitted_at": submitted_dt.isoformat(),
            "status": status,
            "user_type": user_type,
            "country": country,
            "pipeline_trace": json.dumps(
                _build_pipeline_trace(jurisdiction, escalated)
            ),
            "draft_response": _draft_response(language, medication),
            "draft_response_english": (
                _draft_response_english(medication) if language != "en" else None
            ),
            "source_language": language,
            "redacted_original_text": f"[REDACTED] {template}",
            "english_inquiry": _english_inquiry(template),
            "escalation_rules": json.dumps(escalation_rules),
            "reviewed_at": reviewed_at,
            "approved_response": approved_response,
            "reviewer_note": reviewer_note,
            "rejection_reason": rejection_reason,
            "rejection_reason_english": rejection_reason_english,
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Generate patient log entries
# ──────────────────────────────────────────────────────────────────────────────

def _generate_patient_logs(n: int) -> List[Dict]:
    """
    Generate ``n`` synthetic patient log entries for the analytics baseline.

    Fields required by _build_proactive_recommendations():
      nationality, diet_flags, condition_codes, medications_current,
      interaction_language, visit_type.

    Uses opaque patient IDs — no names, no real identifiers.
    """
    logs = []
    for i in range(n):
        nat = _RNG.choice(_NATIONALITIES)
        lang = _RNG.choice(["en", "es", "de", "hi", "fr"])
        diet = []
        if _RNG.random() < 0.3:
            diet = [_RNG.choice(_DIET_FLAGS)]

        # 1-2 ICD-10 codes per log
        codes = _RNG.sample(_ICD10_CODES, k=_RNG.randint(1, 2))

        # ~15% of patients currently on a cross-border conflict med
        current_meds: List[str] = []
        if _RNG.random() < 0.15:
            current_meds = [_RNG.choice(_FLAGGED_MEDS)]

        logs.append({
            "patient_id": f"DEMO-{i:05d}",
            "age_band": _RNG.choice(["18-30", "31-45", "46-60", "61+"]),
            "nationality": nat,
            "condition_codes": codes,
            "medications_current": current_meds,
            "diet_flags": diet,
            "interaction_language": lang,
            "visit_type": _RNG.choice(_VISIT_TYPES),
        })
    return logs


# ──────────────────────────────────────────────────────────────────────────────
# Seed HITL SQLite
# ──────────────────────────────────────────────────────────────────────────────

_INSERT_SQL = """
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

_DELETE_DEMO_SQL = "DELETE FROM hitl_queue WHERE session_id LIKE 'demo-%';"
_COUNT_DEMO_SQL  = "SELECT COUNT(*) FROM hitl_queue WHERE session_id LIKE 'demo-%';"
_COUNT_ALL_SQL   = "SELECT COUNT(*) FROM hitl_queue;"

_CREATE_TABLE_SQL = """
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


def _seed_hitl(db_path: str, rows: List[Dict]) -> int:
    """
    Delete all demo rows in ``db_path`` and insert ``rows``.

    Wrapped in a single transaction — a failure leaves the DB unchanged.
    Returns the number of rows inserted.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_CREATE_TABLE_SQL)
        # Migrate: add bilingual columns to pre-existing databases
        _MIGRATE = [
            "ALTER TABLE hitl_queue ADD COLUMN draft_response_english TEXT;",
            "ALTER TABLE hitl_queue ADD COLUMN source_language TEXT NOT NULL DEFAULT 'en';",
            "ALTER TABLE hitl_queue ADD COLUMN redacted_original_text TEXT;",
            "ALTER TABLE hitl_queue ADD COLUMN english_inquiry TEXT;",
            "ALTER TABLE hitl_queue ADD COLUMN rejection_reason_english TEXT;",
        ]
        for stmt in _MIGRATE:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()

        with conn:  # transaction block — rolls back on exception
            conn.execute(_DELETE_DEMO_SQL)
            conn.executemany(_INSERT_SQL, rows)
        inserted = conn.execute(_COUNT_DEMO_SQL).fetchone()[0]
    finally:
        conn.close()
    return inserted


# ──────────────────────────────────────────────────────────────────────────────
# Seed in-memory telemetry
# ──────────────────────────────────────────────────────────────────────────────

def _seed_telemetry(hitl_rows: List[Dict]) -> int:
    """
    Inject a TelemetryEvent into the live in-memory store for each HITL row.

    Does NOT clear existing non-demo events — only adds the demo events.
    Running twice will append duplicate events, but test fixtures call
    get_telemetry_store().clear() before each test so there is no test impact.
    Returns the number of events injected.
    """
    from backend.analytics.aggregator import TelemetryEvent, get_telemetry_store

    store = get_telemetry_store()
    count = 0
    for row in hitl_rows:
        trace = json.loads(row["pipeline_trace"])
        jurisdiction = trace.get("jurisdiction", "OTHER")
        escalated = trace.get("escalated", False)
        escalation_rules: List[str] = json.loads(row["escalation_rules"])
        medication_flags: List[str] = []
        if escalated and escalation_rules:
            # Extract medication name from draft if present
            draft = row.get("draft_response", "")
            for med in _FLAGGED_MEDS:
                if med in draft.lower():
                    medication_flags.append(med)
                    break

        # Spread timestamps across the last 60 days
        ts = datetime.fromisoformat(row["submitted_at"])

        store.record(TelemetryEvent(
            language=row["source_language"],
            user_type=row["user_type"],
            jurisdiction=jurisdiction,
            escalated=escalated,
            medication_flags=medication_flags,
            pipeline_stages_completed=_RNG.randint(3, 5),
            timestamp=ts,
        ))
        count += 1
    return count


# ──────────────────────────────────────────────────────────────────────────────
# Seed patient logs
# ──────────────────────────────────────────────────────────────────────────────

def _seed_patient_logs(logs: List[Dict]) -> int:
    """Write patient logs JSON, overwriting any previous file. Returns count."""
    _SYNTHETIC_DATA_DIR.mkdir(parents=True, exist_ok=True)
    _PATIENT_LOGS_PATH.write_text(
        json.dumps(logs, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(logs)


# ──────────────────────────────────────────────────────────────────────────────
# Summary report
# ──────────────────────────────────────────────────────────────────────────────

def _print_summary(
    hitl_rows: List[Dict],
    telemetry_count: int,
    log_count: int,
) -> None:
    from collections import Counter

    statuses = Counter(r["status"] for r in hitl_rows)
    personas = Counter(r["user_type"] for r in hitl_rows)
    jurisdictions = Counter(
        json.loads(r["pipeline_trace"]).get("jurisdiction", "OTHER")
        for r in hitl_rows
    )
    escalated_count = sum(
        1 for r in hitl_rows
        if json.loads(r["pipeline_trace"]).get("escalated", False)
    )
    escalation_rate = escalated_count / len(hitl_rows) if hitl_rows else 0.0

    print()
    print("=" * 60)
    print("  Demo Data Seeder — Summary")
    print("=" * 60)
    print(f"  HITL queue rows inserted : {len(hitl_rows)}")
    print(f"  Patient log rows written : {log_count}")
    print(f"  Telemetry events injected: {telemetry_count}")
    print()
    print("  HITL review-state breakdown:")
    for status, count in sorted(statuses.items()):
        print(f"    {status:<10} {count:>4}")
    print()
    print("  Persona split:")
    for persona, count in sorted(personas.items()):
        pct = 100.0 * count / len(hitl_rows)
        print(f"    {persona:<12} {count:>4}  ({pct:.1f}%)")
    print()
    print("  Jurisdiction breakdown (HITL telemetry):")
    for jur, count in sorted(jurisdictions.items()):
        print(f"    {jur:<12} {count:>4}")
    print()
    print(f"  Escalation rate          : {escalation_rate:.1%}")
    print("=" * 60)
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────────────────────────────

def seed() -> None:
    """Run the full demo seeder."""
    # Load DB path from application settings
    from backend.config import get_settings
    settings = get_settings()
    db_path = settings.hitl_db_path

    print(f"[seed] HITL DB path : {db_path}")
    print(f"[seed] Patient logs : {_PATIENT_LOGS_PATH}")

    # 1. Generate data
    hitl_rows = _generate_hitl_rows(_HITL_ROWS)
    patient_logs = _generate_patient_logs(_PATIENT_LOG_ROWS)

    # 2. Seed HITL SQLite (idempotent — deletes demo rows first)
    hitl_inserted = _seed_hitl(db_path, hitl_rows)
    print(f"[seed] HITL rows inserted: {hitl_inserted}")

    # 3. Seed patient logs JSON (always overwritten)
    log_count = _seed_patient_logs(patient_logs)
    print(f"[seed] Patient log rows written: {log_count}")

    # 4. Seed in-memory telemetry (append; tests will clear it themselves)
    telemetry_count = _seed_telemetry(hitl_rows)
    print(f"[seed] Telemetry events injected: {telemetry_count}")

    # 5. Print summary
    _print_summary(hitl_rows, telemetry_count, log_count)


if __name__ == "__main__":
    seed()
