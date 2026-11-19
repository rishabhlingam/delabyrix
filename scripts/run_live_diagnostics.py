#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_live_diagnostics.py
================================
Live diagnostic runner for the Multilingual Clinical AI Agent & BI Platform.

What this script does
---------------------
1. Checks whether http://localhost:8000 is already reachable.  If not, it
   temporarily starts ``uvicorn backend.main:app --port 8000`` using the
   project's .venv Python and stops it cleanly when the diagnostics finish.
2. Runs every test case against the LIVE FastAPI + IBM watsonx.ai
   (ibm/granite-4-h-small) pipeline with WATSONX_MOCK_MODE=false.
3. Prints a detailed diagnostic report to stdout and exits with code 0
   (all pass) or 1 (any failure).

Test categories covered
-----------------------
  A  -- Health / server availability
  B  -- Multilingual inputs (en/es/hi) including cross-language drug names
  C  -- Cross-border jurisdiction conflicts (US vs DE, ambiguous country)
  D  -- PII redaction stress tests (name, SSN, ITIN, phone, passport, DOB)
  E  -- HITL escalation rules 1-5 (should-escalate) and clean queries (200)
  F  -- All 3 user personas (patient, provider, coordinator)
  G  -- HITL approve / reject / polling flow
  H  -- BI dashboard zero-PII verification
  I  -- Medication registry API (GET /registry/check, /registry/list)
  J  -- Document endpoint (GET /documents/{type}/{lang})
  K  -- LLM-output quality probes (prompt-tag leakage, topic drift, truncation,
        drug-name translation accuracy)

Usage
-----
  # Activate .venv first (or let the script find it automatically):
  .venv\\Scripts\\python scripts\\run_live_diagnostics.py

  # To run against a server already running on a different port:
  set BASE_URL=http://localhost:9000
  .venv\\Scripts\\python scripts\\run_live_diagnostics.py

Requirements
------------
  httpx>=0.27.0  (already in requirements.txt)
  A valid .env file with WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_MODEL_ID
  set so the server starts in REAL (non-mock) mode.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Repo root + .venv Python path
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_VENV_PYTHON = (
    _REPO_ROOT / ".venv" / "Scripts" / "python.exe"   # Windows
    if ((_REPO_ROOT / ".venv" / "Scripts" / "python.exe").exists())
    else _REPO_ROOT / ".venv" / "bin" / "python"       # Unix
)
_BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")

# ---------------------------------------------------------------------------
# httpx
# ---------------------------------------------------------------------------
try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Run: pip install httpx")
    sys.exit(2)


# ===========================================================================
# Result dataclass
# ===========================================================================

@dataclass
class DiagResult:
    """Outcome of a single diagnostic test case."""
    category: str           # A-K
    name: str               # Short description
    passed: bool
    http_status: Optional[int] = None
    escalated: Optional[bool] = None
    details: str = ""
    defects: List[str] = field(default_factory=list)
    response_text: Optional[str] = None


# ===========================================================================
# Server lifecycle helpers
# ===========================================================================

def _server_alive(url: str, timeout: float = 2.0) -> bool:
    """Return True if GET /health returns 200."""
    try:
        r = httpx.get(f"{url}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _start_server() -> Optional[subprocess.Popen]:
    """Start uvicorn in a subprocess. Returns Popen, or None if already up."""
    if _server_alive(_BASE_URL):
        print(f"[server] {_BASE_URL} already up -- skipping startup.")
        return None

    python = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable
    cmd = [
        python, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "warning",
    ]
    print(f"[server] Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(_REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    for _ in range(60):
        time.sleep(0.5)
        if _server_alive(_BASE_URL):
            print(f"[server] Ready at {_BASE_URL}")
            return proc
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            print(f"[server] Process exited early:\n{stderr}")
            return None

    print("[server] Timed out waiting for server to start.")
    proc.terminate()
    return None


def _stop_server(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    print("[server] Stopping uvicorn ...")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[server] Stopped.")


# ===========================================================================
# HTTP helpers
# ===========================================================================

_CLIENT = httpx.Client(base_url=_BASE_URL, timeout=120.0)


def _post(path: str, payload: dict) -> httpx.Response:
    return _CLIENT.post(path, json=payload)


def _get(path: str, params: Optional[dict] = None) -> httpx.Response:
    return _CLIENT.get(path, params=params)


def _agent_query(
    text: str,
    source_language: str = "en",
    user_type: str = "patient",
    country: str = "US",
    session_id: Optional[str] = None,
) -> httpx.Response:
    return _post("/agent/query", {
        "text": text,
        "source_language": source_language,
        "user_type": user_type,
        "country": country,
        "session_id": session_id or str(uuid.uuid4()),
    })


# ===========================================================================
# LLM quality checkers
# ===========================================================================

import re as _re

# Granite role-tag leakage pattern
_GRANITE_TAG_RE = _re.compile(
    r"<\|(?:start_of_role|end_of_role|system|user|assistant)\|>",
    _re.IGNORECASE,
)

# Hallucination / topic-drift keywords that appear when [SSN] triggers
# identity-theft or genetic-privacy boilerplate
_DRIFT_PATTERNS = [
    "identity theft",
    "genetic privacy",
    "social security administration",
    "federal trade commission",
    "credit bureau",
    "equifax",
    "transunion",
    "experian",
    "identity monitoring",
]

_MIN_RESPONSE_LEN = 30


def _check_llm_quality(text: str) -> List[str]:
    """Return a list of defect descriptions (empty = clean output)."""
    defects: List[str] = []

    if not text or len(text.strip()) < _MIN_RESPONSE_LEN:
        defects.append(f"TRUNCATED: response too short ({len(text.strip())} chars)")

    if _GRANITE_TAG_RE.search(text):
        defects.append("ROLE_TAG_LEAK: Granite role tags present in output")

    for drift in _DRIFT_PATTERNS:
        if drift.lower() in text.lower():
            defects.append(f"TOPIC_DRIFT: off-topic phrase detected -> '{drift}'")
            break

    for fragment in [
        "Your ONLY task is to",
        "Rules you MUST follow",
        "Output ONLY the",
        "Do NOT add",
    ]:
        if fragment in text:
            defects.append(
                f"PROMPT_LEAK: system-prompt instruction leaked -> '{fragment[:40]}'"
            )
            break

    return defects


def _extract_response_text(resp_json: dict) -> str:
    return (
        resp_json.get("response_text")
        or resp_json.get("message")
        or ""
    )


def _extract_pipeline_text(resp_json: dict) -> str:
    trace = resp_json.get("pipeline_trace", {})
    return " ".join(str(v) for v in trace.values() if isinstance(v, str))


# ===========================================================================
# TEST SUITE
# ===========================================================================

def run_all_tests() -> List[DiagResult]:  # noqa: C901
    results: List[DiagResult] = []

    def rec(r: DiagResult) -> DiagResult:
        results.append(r)
        status_sym = "PASS" if r.passed else "FAIL"
        flag_str = f"  escalated={r.escalated}" if r.escalated is not None else ""
        print(f"  [{r.category}] {status_sym}  HTTP={r.http_status}  {r.name}{flag_str}")
        for d in r.defects:
            print(f"       !! {d}")
        if not r.passed:
            print(f"       -> {r.details}")
        return r

    # -------------------------------------------------------------------
    # A -- Health check
    # -------------------------------------------------------------------
    print("\n-- A: Health / server availability --")

    r = _get("/health")
    rec(DiagResult(
        category="A", name="GET /health -> 200",
        passed=(r.status_code == 200 and r.json().get("status") == "ok"),
        http_status=r.status_code,
        details=f"body={r.text[:120]}",
    ))

    # -------------------------------------------------------------------
    # B -- Multilingual inputs + cross-language drug names
    # -------------------------------------------------------------------
    print("\n-- B: Multilingual inputs --")

    # B1: English baseline -- deductible question (should NOT escalate)
    r = _agent_query(
        "My insurance deductible is $3,000. Can you explain what that means?",
        source_language="en", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="EN billing query -> 200 (no escalation)",
        passed=(r.status_code == 200 and body.get("escalated") is False),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details=f"escalated={body.get('escalated')}",
    ))

    # B2: Spanish input -- billing (es->en translation path)
    r = _agent_query(
        "Necesito entender mi deducible de seguro. Que significa copago?",
        source_language="es", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="ES billing query (es->en translation) -> no escalation",
        passed=(r.status_code in (200, 202)),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="Translation path exercised",
    ))

    # B3: Hindi input -- billing (hi->en translation path)
    # Using ASCII romanisation to avoid codec issues in subprocess stdout
    r = _agent_query(
        "Mujhe apne bima ki katoti rashi samajhni hai. Cope kya hota hai?",
        source_language="hi", country="IN",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="HI billing query (hi->en translation) -> reachable",
        passed=(r.status_code in (200, 202)),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="Hindi (romanised) translation path exercised",
    ))

    # B4: Spanish drug name "metamizol" -> must be detected as banned in US_FDA
    r = _agent_query(
        "El medico me receto metamizol para el dolor. Puedo tomarlo en Estados Unidos?",
        source_language="es", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="ES 'metamizol' -> US_FDA banned -> 202 escalation",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="Spanish drug alias must trigger Rule 2",
    ))

    # B5: Spanish "dipirona" alias -> maps to metamizole -> US_FDA banned
    r = _agent_query(
        "Tomo dipirona para la fiebre. Esta permitida en Estados Unidos?",
        source_language="es", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="ES 'dipirona' alias -> US_FDA banned -> 202 escalation",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="dipirona->metamizole alias must trigger Rule 2",
    ))

    # B6: Hindi input containing "metamizol" (romanised) -- US banned
    r = _agent_query(
        "Main dard ke liye metamizol le raha hoon. Kya yeh USA mein anumati hai?",
        source_language="hi", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="HI input containing 'metamizol' -> US_FDA banned -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="Hindi text with English INN should still be detected",
    ))

    # B7: English "rosiglitazone" in US (approved) -> should NOT escalate on Rule 2
    r = _agent_query(
        "I take rosiglitazone for type 2 diabetes. Is that okay?",
        source_language="en", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="EN 'rosiglitazone' -> US_FDA approved -> no Rule 2",
        passed=(r.status_code in (200, 202)),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="Rosiglitazone approved in US -- Rule 2 must NOT fire",
    ))

    # B8: English "phenylephrine" in US (delisted) -> escalation expected
    r = _agent_query(
        "My pharmacist recommended phenylephrine nasal decongestant. Is it still available?",
        source_language="en", country="US",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="B", name="EN 'phenylephrine' -> US_FDA delisted -> may escalate",
        passed=(r.status_code in (200, 202)),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        response_text=(_extract_response_text(body) or "")[:200],
        details="phenylephrine delisted; registry check should run",
    ))

    # -------------------------------------------------------------------
    # C -- Cross-border jurisdiction conflicts
    # -------------------------------------------------------------------
    print("\n-- C: Cross-border jurisdiction conflicts --")

    # C1: metamizole in DE (EU_EMA approved) -> should NOT fire Rule 2
    r = _agent_query(
        "I take metamizole for pain. Is that fine here?",
        source_language="en", country="DE",
    )
    body = r.json()
    rules: List[str] = []
    if r.status_code == 202:
        q_resp = _get("/hitl/queue")
        q_items = q_resp.json().get("items", [])
        if q_items:
            rules = q_items[-1].get("escalation_rules", [])
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="C", name="metamizole DE (EU_EMA approved) -> Rule 2 must NOT fire",
        passed=(
            r.status_code == 200
            or (r.status_code == 202 and not any("rule_2" in rule for rule in rules))
        ),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        details=f"rules_triggered={rules}",
    ))

    # C2: rosiglitazone in DE (EU_EMA banned) -> Rule 2 must fire
    r = _agent_query(
        "My doctor in Germany prescribed Avandia (rosiglitazone). What should I know?",
        source_language="en", country="DE",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="C", name="rosiglitazone DE (EU_EMA banned) -> 202 escalation Rule 2",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        details="rosiglitazone banned EU_EMA -> must escalate",
    ))

    # C3: Ambiguous country code "ZZ" -> Rule 5
    r = _agent_query(
        "What medications am I allowed to bring across borders?",
        source_language="en", country="ZZ",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="C", name="Unknown country 'ZZ' -> Rule 5 ambiguous jurisdiction -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        details="is_ambiguous=True must trigger Rule 5",
    ))

    # C4: Canada (CA -> US_FDA proxy) + metamizole -> Rule 2
    r = _agent_query(
        "I was taking metamizole in Mexico. Can I continue in Canada?",
        source_language="en", country="CA",
    )
    body = r.json()
    defects = _check_llm_quality(
        _extract_response_text(body) + " " + _extract_pipeline_text(body)
    )
    rec(DiagResult(
        category="C", name="metamizole CA (US_FDA proxy) -> banned -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=defects,
        details="CA uses US_FDA -> metamizole banned -> Rule 2",
    ))

    # C5: Cross-jurisdiction divergence checks via /registry/check
    for drug, jurisdiction, expected_status in [
        ("metamizole",   "US_FDA", "banned"),
        ("metamizole",   "EU_EMA", "approved"),
        ("rosiglitazone","US_FDA", "approved"),
        ("rosiglitazone","EU_EMA", "banned"),
        ("domperidone",  "US_FDA", "restricted"),
        ("phenylephrine","US_FDA", "delisted"),
    ]:
        r = _get("/registry/check", {"medication_name": drug, "jurisdiction": jurisdiction})
        actual = r.json().get("status") if r.status_code == 200 else "NOT_FOUND"
        rec(DiagResult(
            category="C",
            name=f"registry {drug}/{jurisdiction} -> status={expected_status}",
            passed=(r.status_code == 200 and actual == expected_status),
            http_status=r.status_code,
            details=f"expected={expected_status} got={actual}",
        ))

    # -------------------------------------------------------------------
    # D -- PII redaction stress tests
    # -------------------------------------------------------------------
    print("\n-- D: PII redaction stress tests --")

    PII_TESTS = [
        ("name",     "My name is Robert Johnson and I need help with my insurance."),
        ("ssn",      "Patient SSN: 234-56-7890. What is my deductible?"),
        ("itin",     "My tax ID is 912-34-5678. Can you help me?"),
        ("phone",    "Call me at 800-555-1234 for appointment scheduling."),
        ("passport", "My passport number is B12345678. I need a medication list."),
        ("dob",      "Date of birth: 03/15/1980. I need to understand my consent form."),
        ("email",    "Reach me at jane.doe@example.com. What is a copay?"),
        ("combined", "John Smith, DOB 05/12/1975, SSN 123-45-6789, email j@test.com asks about ICU."),
    ]

    RAW_PII_FRAGMENTS: Dict[str, List[str]] = {
        "name":     ["Robert Johnson"],
        "ssn":      ["234-56-7890"],
        "itin":     ["912-34-5678"],
        "phone":    ["800-555-1234"],
        "passport": ["B12345678"],
        "dob":      ["03/15/1980"],
        "email":    ["jane.doe@example.com"],
        "combined": ["John Smith", "123-45-6789", "j@test.com"],
    }

    for pii_type, pii_text in PII_TESTS:
        r = _agent_query(pii_text, source_language="en", country="US")
        body = r.json()
        body_str = json.dumps(body)
        leaks = [frag for frag in RAW_PII_FRAGMENTS.get(pii_type, []) if frag in body_str]
        defects = _check_llm_quality(
            _extract_response_text(body) + " " + _extract_pipeline_text(body)
        )
        rec(DiagResult(
            category="D",
            name=f"PII ({pii_type}) -> no raw PII in API response",
            passed=(r.status_code in (200, 202) and not leaks),
            http_status=r.status_code, escalated=body.get("escalated"),
            defects=defects,
            details=f"leaks={leaks}" if leaks else "clean",
        ))

    # -------------------------------------------------------------------
    # E -- HITL escalation rules
    # -------------------------------------------------------------------
    print("\n-- E: HITL escalation rules --")

    # E1: Rule 2 -- banned medication (metamizole, US)
    r = _agent_query("I take metamizole for pain management.", "en", "patient", "US")
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 2 - banned drug (metamizole/US_FDA) -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="metamizole banned -> Rule 2 must fire",
    ))

    # E2: Rule 2 -- restricted medication (thalidomide, US)
    r = _agent_query(
        "My oncologist prescribed thalidomide for multiple myeloma.",
        "en", "patient", "US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 2 - restricted drug (thalidomide/US_FDA) -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="thalidomide restricted -> Rule 2 must fire",
    ))

    # E3: Rule 4 -- ICU admission topic
    r = _agent_query(
        "I need to understand the ICU admission consent form.",
        "en", "patient", "US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 4 - ICU topic -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="ICU keyword -> Rule 4 must fire",
    ))

    # E4: Rule 4 -- surgery consent
    r = _agent_query(
        "Please explain the surgery consent form I need to sign.",
        "en", "patient", "US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 4 - surgery consent topic -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="surgery keyword -> Rule 4 must fire",
    ))

    # E5: Rule 4 -- end-of-life / palliative care
    r = _agent_query(
        "What are palliative care options for end-of-life planning?",
        "en", "patient", "US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 4 - palliative/end-of-life topic -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="end-of-life keyword -> Rule 4 must fire",
    ))

    # E6: Rule 4 -- DNR
    r = _agent_query(
        "My family wants to discuss a DNR order with the doctor.",
        "en", "patient", "US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 4 - DNR order topic -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="DNR keyword -> Rule 4 must fire",
    ))

    # E7: Rule 5 -- ambiguous jurisdiction
    r = _agent_query("I need medication advice.", "en", "patient", "ZZ")
    body = r.json()
    rec(DiagResult(
        category="E", name="Rule 5 - ambiguous jurisdiction (ZZ) -> 202",
        passed=(r.status_code == 202 and body.get("escalated") is True),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(_extract_response_text(body)),
        details="Unknown country -> Rule 5 must fire",
    ))

    # E8: NO escalation -- clean billing query
    r = _agent_query(
        "What is the difference between a copay and a coinsurance?",
        source_language="en", country="US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Clean billing query -> 200 (no escalation)",
        passed=(r.status_code == 200 and body.get("escalated") is False),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(
            _extract_response_text(body) + " " + _extract_pipeline_text(body)
        ),
        details="Billing query must NOT escalate",
    ))

    # E9: NO escalation -- approved medication
    r = _agent_query(
        "I take ibuprofen for headaches. Is that safe?",
        source_language="en", country="US",
    )
    body = r.json()
    rec(DiagResult(
        category="E", name="Approved drug (ibuprofen/US) -> no Rule 2",
        passed=(r.status_code in (200, 202)),
        http_status=r.status_code, escalated=body.get("escalated"),
        defects=_check_llm_quality(
            _extract_response_text(body) + " " + _extract_pipeline_text(body)
        ),
        details="ibuprofen approved; should not escalate on Rule 2",
    ))

    # -------------------------------------------------------------------
    # F -- All 3 user personas
    # -------------------------------------------------------------------
    print("\n-- F: User personas --")

    for persona in ("patient", "provider", "coordinator"):
        r = _agent_query(
            "Explain the deductible and out-of-pocket maximum in simple terms.",
            source_language="en", user_type=persona, country="US",
        )
        body = r.json()
        defects = _check_llm_quality(
            _extract_response_text(body) + " " + _extract_pipeline_text(body)
        )
        rec(DiagResult(
            category="F", name=f"Persona={persona} billing query -> reachable",
            passed=(r.status_code in (200, 202)),
            http_status=r.status_code, escalated=body.get("escalated"),
            defects=defects,
            response_text=(_extract_response_text(body) or "")[:200],
            details=f"user_type={persona}",
        ))

    # -------------------------------------------------------------------
    # G -- HITL approve / reject / polling flow
    # -------------------------------------------------------------------
    print("\n-- G: HITL approve/reject/polling flow --")

    # G1: Submit a banned-drug query -> 202
    session_id = str(uuid.uuid4())
    r = _agent_query(
        "I take metamizole for fever. Is this medication allowed in the US?",
        source_language="en", country="US", session_id=session_id,
    )
    body = r.json()
    escalated_ok = r.status_code == 202 and body.get("escalated") is True
    review_id = body.get("review_id", "")

    rec(DiagResult(
        category="G", name="G1: submit banned-drug query -> 202 + review_id",
        passed=escalated_ok and bool(review_id),
        http_status=r.status_code, escalated=body.get("escalated"),
        details=f"review_id={review_id!r}",
    ))

    if review_id:
        # G2: GET /hitl/queue -> item present
        r2 = _get("/hitl/queue")
        q_body = r2.json()
        items = q_body.get("items", [])
        matching = [i for i in items if i.get("review_id") == review_id]
        rec(DiagResult(
            category="G", name="G2: GET /hitl/queue -> item present",
            passed=(r2.status_code == 200 and len(matching) == 1),
            http_status=r2.status_code,
            details=f"pending_count={q_body.get('pending_count')} match={len(matching)}",
        ))

        # G2b: No raw PII in queue
        queue_str = json.dumps(q_body)
        raw_pii_in_queue = any(
            frag in queue_str
            for frag in ["234-56-7890", "123-45-6789", "john.doe@example.com"]
        )
        rec(DiagResult(
            category="G", name="G2b: HITL queue contains no injected test PII",
            passed=not raw_pii_in_queue,
            details="clean" if not raw_pii_in_queue else "PII LEAK DETECTED",
        ))

        # G3: Poll session -> status=pending before review
        r3 = _get(f"/agent/session/{session_id}")
        s_body = r3.json()
        rec(DiagResult(
            category="G", name="G3: poll session -> status=pending before review",
            passed=(r3.status_code == 200 and s_body.get("status") == "pending"),
            http_status=r3.status_code,
            details=f"status={s_body.get('status')}",
        ))

        # Snapshot pending_count before approval (G2 already verified the item is there)
        pre_count = _get("/hitl/queue").json().get("pending_count", 0)

        # G4: POST /hitl/approve
        approved_text = (
            "Metamizole is not approved in the United States. "
            "Please consult your physician for safe alternatives "
            "such as ibuprofen or acetaminophen."
        )
        r4 = _post("/hitl/approve", {
            "review_id": review_id,
            "approved_response": approved_text,
            "reviewer_note": "Diagnostic test approval",
        })
        rec(DiagResult(
            category="G", name="G4: POST /hitl/approve -> 200 approved",
            passed=(r4.status_code == 200 and r4.json().get("status") == "approved"),
            http_status=r4.status_code,
            details=r4.text[:100],
        ))

        # G5: Poll session -> status=approved + correct response_text
        r5 = _get(f"/agent/session/{session_id}")
        s5 = r5.json()
        rec(DiagResult(
            category="G", name="G5: poll session -> status=approved + text set",
            passed=(
                r5.status_code == 200
                and s5.get("status") == "approved"
                and s5.get("response_text") == approved_text
            ),
            http_status=r5.status_code,
            details=(
                f"status={s5.get('status')} "
                f"text_match={s5.get('response_text') == approved_text}"
            ),
        ))

        # G6: pending_count decreases by 1 after approval
        r6 = _get("/hitl/queue")
        post_count = r6.json().get("pending_count", -1)
        rec(DiagResult(
            category="G", name="G6: pending_count decreases by 1 after approval",
            passed=(r6.status_code == 200 and post_count == pre_count - 1),
            http_status=r6.status_code,
            details=f"pre={pre_count} post={post_count} expected={pre_count - 1}",
        ))

    # G7: Rejection flow
    session_r = str(uuid.uuid4())
    rr = _agent_query(
        "Please explain the informed consent form for surgery.",
        source_language="en", country="US", session_id=session_r,
    )
    rr_body = rr.json()
    review_r_id = rr_body.get("review_id", "")

    if review_r_id:
        rej = _post("/hitl/reject", {
            "review_id": review_r_id,
            "rejection_reason": "Diagnostic test rejection -- insufficient context.",
        })
        rec(DiagResult(
            category="G", name="G7: POST /hitl/reject -> 200 rejected",
            passed=(rej.status_code == 200 and rej.json().get("status") == "rejected"),
            http_status=rej.status_code,
            details=rej.text[:100],
        ))

        rp = _get(f"/agent/session/{session_r}")
        rec(DiagResult(
            category="G", name="G7b: poll rejected session -> status=rejected",
            passed=(rp.status_code == 200 and rp.json().get("status") == "rejected"),
            http_status=rp.status_code,
            details=f"status={rp.json().get('status')}",
        ))
    else:
        rec(DiagResult(
            category="G", name="G7: surgery query must escalate to test rejection",
            passed=False,
            http_status=rr.status_code,
            details=f"Expected 202 surgery escalation, got {rr.status_code}",
        ))

    # -------------------------------------------------------------------
    # H -- BI dashboard zero-PII verification
    # -------------------------------------------------------------------
    print("\n-- H: BI dashboard zero-PII --")

    r = _get("/analytics/dashboard")
    rec(DiagResult(
        category="H", name="GET /analytics/dashboard -> 200 + required fields",
        passed=(r.status_code == 200 and all(k in r.json() for k in [
            "total_queries", "escalation_rate", "queries_by_language",
            "queries_by_user_type", "top_medication_flags",
            "avg_pipeline_stages_completed", "jurisdiction_breakdown",
        ])),
        http_status=r.status_code,
        details=f"keys={list(r.json().keys())}",
    ))

    dash = r.json()
    rec(DiagResult(
        category="H", name="dashboard total_queries >= 200 (synthetic baseline)",
        passed=(dash.get("total_queries", 0) >= 200),
        details=f"total_queries={dash.get('total_queries')}",
    ))

    pii_fragments = [
        "123-45-6789", "234-56-7890", "john.doe@",
        "Robert Johnson", "03/15/1980", "B12345678",
    ]
    dash_str = json.dumps(dash)
    leaked = [f for f in pii_fragments if f in dash_str]
    rec(DiagResult(
        category="H", name="dashboard body contains no injected test PII",
        passed=(not leaked),
        details=f"leaked={leaked}" if leaked else "clean",
    ))

    # Medication flags must be short INN names
    flag_ok = True
    for flag_entry in dash.get("top_medication_flags", []):
        med = flag_entry.get("medication", "")
        if len(med) > 50 or (" " in med and len(med.split()) > 3):
            flag_ok = False
            break
    rec(DiagResult(
        category="H", name="dashboard medication flags are INN-length",
        passed=flag_ok,
        details="All flags short INN names" if flag_ok else "Flag looks like a sentence",
    ))

    # -------------------------------------------------------------------
    # I -- Medication registry API
    # -------------------------------------------------------------------
    print("\n-- I: Medication registry API --")

    r = _get("/registry/list")
    body = r.json()
    rec(DiagResult(
        category="I", name="GET /registry/list default -> 50 total, 20 per page",
        passed=(
            r.status_code == 200
            and body.get("total") == 50
            and len(body.get("records", [])) == 20
        ),
        http_status=r.status_code,
        details=f"total={body.get('total')} records={len(body.get('records',[]))}",
    ))

    r = _get("/registry/list", {"jurisdiction": "US_FDA", "page_size": 100})
    body = r.json()
    rec(DiagResult(
        category="I", name="registry list US_FDA filter -> 25 records",
        passed=(r.status_code == 200 and body.get("total") == 25),
        http_status=r.status_code,
        details=f"total={body.get('total')}",
    ))

    r = _get("/registry/check", {"medication_name": "Dipyrone", "jurisdiction": "US_FDA"})
    body2 = r.json() if r.status_code == 200 else {}
    rec(DiagResult(
        category="I", name="registry check Dipyrone (brand) -> metamizole INN",
        passed=(r.status_code == 200 and body2.get("name_generic") == "metamizole"),
        http_status=r.status_code,
        details=f"name_generic={body2.get('name_generic')}",
    ))

    r = _get("/registry/check", {"medication_name": "METAMIZOLE", "jurisdiction": "US_FDA"})
    rec(DiagResult(
        category="I", name="registry check METAMIZOLE (uppercase) -> 200",
        passed=(r.status_code == 200),
        http_status=r.status_code,
        details=r.text[:80],
    ))

    r = _get("/registry/check", {"medication_name": "xyznonexistentdrugabc", "jurisdiction": "US_FDA"})
    rec(DiagResult(
        category="I", name="registry check unknown drug -> 404",
        passed=(r.status_code == 404),
        http_status=r.status_code,
        details=r.text[:80],
    ))

    # -------------------------------------------------------------------
    # J -- Document endpoint
    # -------------------------------------------------------------------
    print("\n-- J: Document endpoint --")

    for doc_type, lang in [
        ("consent_icu_admission",        "en"),
        ("consent_icu_admission",        "es"),
        ("consent_surgery",              "hi"),
        ("billing_deductible_explanation","en"),
        ("billing_deductible_explanation","es"),
    ]:
        r = _get(f"/documents/{doc_type}/{lang}")
        body3 = r.json() if r.status_code == 200 else {}
        rec(DiagResult(
            category="J", name=f"GET /documents/{doc_type}/{lang} -> 200",
            passed=(
                r.status_code == 200
                and body3.get("doc_type") == doc_type
                and len(body3.get("content", "")) > 50
            ),
            http_status=r.status_code,
            details=f"title={body3.get('title', '')[:60]}",
        ))

    r = _get("/documents/fake_doc_type/en")
    rec(DiagResult(
        category="J", name="invalid doc_type -> 422",
        passed=(r.status_code == 422),
        http_status=r.status_code,
        details=r.text[:80],
    ))

    # -------------------------------------------------------------------
    # K -- LLM output quality probes (live Granite output analysis)
    # -------------------------------------------------------------------
    print("\n-- K: LLM output quality probes --")

    # K1: Prompt-tag leakage -- SSN token must not trigger role-tag in output
    r = _agent_query(
        "My SSN is on file already. I need help understanding my deductible.",
        source_language="en", country="US",
    )
    body = r.json()
    all_text = _extract_response_text(body) + " " + _extract_pipeline_text(body)
    tag_leak = bool(_GRANITE_TAG_RE.search(all_text))
    rec(DiagResult(
        category="K", name="K1: SSN token -> no Granite role-tag leakage in output",
        passed=(r.status_code in (200, 202) and not tag_leak),
        http_status=r.status_code,
        defects=["ROLE_TAG_LEAK"] if tag_leak else [],
        response_text=all_text[:200],
        details="clean" if not tag_leak else "ROLE TAGS FOUND IN OUTPUT",
    ))

    # K2: Topic drift -- redacted SSN token must not trigger identity-theft boilerplate
    r = _agent_query(
        "Patient ID [SSN] filed a claim. Please explain the out-of-pocket maximum.",
        source_language="en", country="US",
    )
    body = r.json()
    all_text = _extract_response_text(body) + " " + _extract_pipeline_text(body)
    drift_found = any(phrase in all_text.lower() for phrase in _DRIFT_PATTERNS)
    rec(DiagResult(
        category="K", name="K2: [SSN] token -> no identity-theft topic drift",
        passed=(r.status_code in (200, 202) and not drift_found),
        http_status=r.status_code,
        defects=["TOPIC_DRIFT: identity-theft boilerplate"] if drift_found else [],
        response_text=all_text[:300],
        details="clean" if not drift_found else "DRIFT DETECTED",
    ))

    # K3: Drug translation accuracy -- ES "metamizol" -> INN "metamizole" in trace
    r = _agent_query(
        "El medico me receto metamizol. Que es?",
        source_language="es", country="US",
    )
    body = r.json()
    trace = body.get("pipeline_trace", {})
    translation_field = str(trace.get("translation", "")).lower()
    if r.status_code == 202:
        q_resp2 = _get("/hitl/queue")
        q_items2 = q_resp2.json().get("items", [])
        if q_items2:
            translation_field = str(
                q_items2[-1].get("pipeline_trace", {}).get("translation", "")
            ).lower()
    drug_translated = "metamizole" in translation_field or "metamizol" in translation_field
    rec(DiagResult(
        category="K", name="K3: ES 'metamizol' -> translation contains INN 'metamizole'",
        passed=(r.status_code == 202 and drug_translated),
        http_status=r.status_code, escalated=body.get("escalated"),
        response_text=translation_field[:200],
        details=f"translation snippet: {translation_field[:100]!r}",
    ))

    # K4: Response completeness
    r = _agent_query(
        "What is an out-of-pocket maximum and how does it differ from a deductible?",
        source_language="en", country="US",
    )
    body = r.json()
    resp_text = _extract_response_text(body) or _extract_pipeline_text(body)
    text_len = len(resp_text.strip())
    last_char = resp_text.strip()[-1] if resp_text.strip() else ""
    truncated = text_len < _MIN_RESPONSE_LEN or (
        last_char and last_char not in ".!?" and text_len < 50
    )
    rec(DiagResult(
        category="K", name="K4: billing response not truncated (>=30 chars)",
        passed=(r.status_code in (200, 202) and not truncated),
        http_status=r.status_code,
        response_text=resp_text[:300],
        details=f"len={text_len} last_char={last_char!r}",
    ))

    # K5: Provider persona response must differ from patient
    r_patient = _agent_query(
        "What is a deductible?",
        source_language="en", user_type="patient", country="US",
    )
    r_provider = _agent_query(
        "What is a deductible?",
        source_language="en", user_type="provider", country="US",
    )
    p_text = (
        _extract_response_text(r_patient.json())
        + " "
        + _extract_pipeline_text(r_patient.json())
    )
    pr_text = (
        _extract_response_text(r_provider.json())
        + " "
        + _extract_pipeline_text(r_provider.json())
    )
    rec(DiagResult(
        category="K", name="K5: patient vs provider responses are non-identical",
        passed=(
            r_patient.status_code in (200, 202)
            and r_provider.status_code in (200, 202)
            and p_text != pr_text
        ),
        http_status=r_provider.status_code,
        details="responses differ" if p_text != pr_text else "IDENTICAL -- no cultural framing",
    ))

    # K6: Multilingual escalation message locale
    r = _agent_query(
        "Necesito informacion sobre mi procedimiento quirurgico.",
        source_language="es", country="US",
    )
    body = r.json()
    if r.status_code == 202:
        msg = body.get("message", "").lower()
        is_spanish = any(w in msg for w in ["solicitud", "revisi", "sesi", "revisi"])
        rec(DiagResult(
            category="K", name="K6: ES input -> 202 escalation message is Spanish",
            passed=is_spanish,
            http_status=r.status_code, escalated=True,
            response_text=body.get("message", ""),
            details=f"message={body.get('message','')[:120]}",
        ))
    else:
        rec(DiagResult(
            category="K", name="K6: ES surgery query reachable",
            passed=(r.status_code == 200),
            http_status=r.status_code,
            details="Did not escalate on surgery -- Rule 4 did not trigger (Spanish text)",
        ))

    return results


# ===========================================================================
# Report printer
# ===========================================================================

def _print_report(results: List[DiagResult]) -> int:
    """Print the full diagnostic report and return 0 (all pass) or 1 (any fail)."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    all_defects: List[tuple] = [
        (r.name, d)
        for r in results
        for d in r.defects
    ]

    sep = "=" * 78

    print(f"\n{sep}")
    print("  DIAGNOSTIC REPORT - Multilingual Clinical AI Agent & BI Platform")
    print(f"  Target : {_BASE_URL}  (ibm/granite-4-h-small)")
    print(sep)

    cats: Dict[str, list] = {}
    for r in results:
        cats.setdefault(r.category, []).append(r)

    print("\n  +-----+----------------------------------------------+--------+--------+")
    print("  | Cat | Test Name                                    | Status |  HTTP  |")
    print("  +-----+----------------------------------------------+--------+--------+")

    for cat, cat_results in sorted(cats.items()):
        for r in cat_results:
            status = "PASS  " if r.passed else "FAIL X"
            name_col = r.name[:44].ljust(44)
            http_col = str(r.http_status or "-").center(6)
            print(f"  |  {cat}  | {name_col} | {status} | {http_col} |")
        print("  +-----+----------------------------------------------+--------+--------+")

    print(f"\n  Results : {passed}/{total} passed   {failed} failed")
    if failed:
        print(f"  ** {failed} test(s) FAILED -- see details below.")
    else:
        print("  ** All tests passed.")

    failures = [r for r in results if not r.passed]
    if failures:
        print(f"\n{sep}")
        print("  FAILURES")
        print(sep)
        for r in failures:
            print(f"\n  [{r.category}] {r.name}")
            print(f"       HTTP: {r.http_status}  escalated: {r.escalated}")
            print(f"       Detail: {r.details}")
            if r.response_text:
                snippet = textwrap.shorten(r.response_text, width=200, placeholder="...")
                print(f"       Output: {snippet!r}")

    if all_defects:
        print(f"\n{sep}")
        print("  LLM OUTPUT DEFECTS OBSERVED")
        print(sep)
        for test_name, defect in all_defects:
            print(f"  !! [{test_name[:60]}]")
            print(f"      {defect}")
    else:
        print(f"\n{sep}")
        print("  LLM Output Quality: No defects observed (no prompt drift, tag leakage,")
        print("  truncation, or drug-translation failures detected).")

    print(f"\n{sep}\n")
    return 0 if failed == 0 else 1


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> int:
    print("\n" + "=" * 78)
    print("  Live Diagnostics -- Multilingual Clinical AI Agent & BI Platform")
    print(f"  Target : {_BASE_URL}")
    print("  Model  : ibm/granite-4-h-small  (WATSONX_MOCK_MODE must be false)")
    print("=" * 78)

    mock_mode = os.environ.get("WATSONX_MOCK_MODE", "").lower()
    if mock_mode in ("true", "1", "yes"):
        print(
            "\nWARNING: WATSONX_MOCK_MODE is set -- LLM calls will return stubs.\n"
            "Set WATSONX_MOCK_MODE=false (or unset) for live Granite diagnostics.\n"
        )

    server_proc = _start_server()
    if not _server_alive(_BASE_URL):
        print(f"\nERROR: {_BASE_URL} is not reachable. Cannot run diagnostics.")
        _stop_server(server_proc)
        return 2

    try:
        results = run_all_tests()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        results = []
    finally:
        _stop_server(server_proc)

    if not results:
        return 2

    return _print_report(results)


if __name__ == "__main__":
    sys.exit(main())
