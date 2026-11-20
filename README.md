# Delabyrix — Multilingual Clinical AI Agent & BI Platform

> **IBM Smart Healthcare Challenge submission**
>
> A multilingual, compliance-aware clinical AI agent and business-intelligence
> platform that bridges medical communication, cross-border health regulations,
> and predictive health intelligence — built with human-in-the-loop oversight
> and data minimisation as first-class design principles.

---

## Problem & Solution Statement

### The Problem

Foreign patients, international travelers, and the clinicians and administrators
who serve them face a critical gap: existing translation tools interpret words
but cannot navigate the healthcare *process*. A tourist in New York cannot
understand an ICU admission consent form written in US legal English. A German
patient arriving with a prescription for metamizole does not know the drug is
banned in the US. A care coordinator managing a multilingual caseload has no
dashboard view of where communication failures are emerging.

Rule-based scripts cannot handle this problem. The questions are open-ended,
vary by language, culture, and jurisdiction, and depend on regulations that
change continuously. Manual interpretation is slow, expensive, and unavailable
at 3 AM.

### The Solution

Delabyrix is a **multi-stage agentic pipeline** (not a chatbot) that:

1. **Strips PII inline** before any text touches an LLM.
2. **Translates** the user's query into English using IBM Granite 4.
3. **Interprets clinical meaning** — extracts medical concepts and cross-checks
   the cross-border medication registry for banned or restricted drugs.
4. **Adds cultural and jurisdictional context** — adapts the framing to the
   user's regulatory regime (FDA / EU EMA) and cultural background.
5. **Generates role-appropriate next steps** — different guidance for a patient,
   a provider, and a care coordinator.

**Human-in-the-Loop (HITL)** sits between the agent output and the end user for
any high-stakes output: low-confidence responses, banned medications, ICU or
surgery topics, residual PII, and ambiguous jurisdictions all route to a
coordinator review queue before the patient sees anything.

The BI dashboard gives care coordinators aggregate metrics — language
distribution, escalation rates, top-flagged medications, jurisdiction breakdown
— with a hard architectural guarantee that raw query text and patient identifiers
never enter the analytics pipeline.

---

## IBM Technology Stack & Architecture

| Component | Technology |
|---|---|
| AI development partner | **IBM Bob IDE** (architecture design, code generation, test writing, compliance review) |
| LLM inference | **IBM watsonx.ai** · model `ibm/granite-4-h-small` · endpoint `/ml/v1/text/chat` |
| Skill orchestration | **IBM watsonx Orchestrate** · OpenAPI 3.0 skill export (`orchestrate/openapi_spec.yaml`) |
| Backend API | **FastAPI** (Python) · served via Uvicorn on port 8000 |
| Frontend | **Streamlit** multi-page application (5 pages) |
| Data layer | Synthetic datasets (zero real PII) · SQLite-backed HITL persistence (`HITL_DB_PATH`) |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend                           │
│  Home · Patient Assistant · Provider Support · HITL Review          │
│  BI Dashboard · Registry Explorer                                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP (localhost:8000)
┌──────────────────────────▼──────────────────────────────────────────┐
│                        FastAPI Backend                              │
│                                                                     │
│  POST /agent/query  →  Agentic Pipeline (5 stages)                  │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Stage 0   │→ │Stage 1     │→ │Stage 2       │→ │Stage 3       │  │
│  │PII       │  │Translate   │  │Medical       │  │Cultural      │  │
│  │Redaction │  │(Granite 4) │  │Interpret +   │  │Context       │  │
│  │          │  │            │  │Registry Chk  │  │(Granite 4)   │  │
│  └──────────┘  └────────────┘  └──────────────┘  └──────────────┘  │
│                                                   ┌──────────────┐  │
│                                                   │Stage 4       │  │
│                                                   │Next Steps    │  │
│                                                   │(Granite 4)   │  │
│                                                   └──────┬───────┘  │
│                                                          │          │
│                                               ┌──────────▼───────┐  │
│                                               │ HITL Escalator   │  │
│                                               │ (5 rules)        │  │
│                                               └──────────┬───────┘  │
│                                                          │ escalate │
│                                               ┌──────────▼───────┐  │
│                                               │ HITL Queue       │  │
│                                               │ (SQLite-backed)  │  │
│                                               └──────────────────┘  │
│                                                                     │
│  GET  /registry/check · /registry/list                              │
│  POST /registry/sync · GET /registry/changelog                      │
│  GET  /documents/{doc_type}/{language}                              │
│  POST /documents/analyze   (custom .txt/.pdf upload)                │
│  GET  /hitl/queue  POST /hitl/approve  POST /hitl/reject            │
│  GET  /analytics/dashboard  (incl. proactive_recommendations)       │
│  POST /synthetic/generate                                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ IBM watsonx.ai REST API
┌──────────────────────────▼──────────────────────────────────────────┐
│   IBM watsonx.ai  ·  ibm/granite-4-h-small  ·  /ml/v1/text/chat    │
└─────────────────────────────────────────────────────────────────────┘
```

### HITL Escalation Rules

| # | Condition | Rationale |
|---|---|---|
| 1 | Granite confidence score below 0.70 | Uncertain outputs must not reach patients |
| 2 | Medication is `banned` or `restricted` in user's jurisdiction | High clinical risk |
| 3 | Input contains PII patterns that could not be fully redacted | Privacy compliance |
| 4 | Query involves ICU admission, surgery consent, or end-of-life topics | High-stakes clinical context |
| 5 | Jurisdiction resolution is ambiguous | Cannot guarantee regulatory compliance |

### Jurisdiction & Registry Support

| Code | Regulatory Regime | Privacy Law |
|---|---|---|
| `US_FDA` | FDA Orange Book | HIPAA |
| `EU_EMA` | EU Union Register | GDPR |

### watsonx Orchestrate Skills (OpenAPI 3.0)

| Skill | Method | Endpoint |
|---|---|---|
| `clinical_query` | POST | `/agent/query` |
| `medication_check` | GET | `/registry/check` |
| `get_consent_document` | GET | `/documents/{doc_type}/{language}` |
| `analyze_document` | POST | `/documents/analyze` |
| `get_dashboard_metrics` | GET | `/analytics/dashboard` |
| `sync_registry_bulletin` | POST | `/registry/sync` |
| `get_registry_changelog` | GET | `/registry/changelog` |
| `get_registry_list` | GET | `/registry/list` |

Each operation carries an `x-ibm-nl-intent` annotation for natural-language
invocation inside Orchestrate. The API key is an `X-API-Key` header whose value
lives exclusively in `.env` and is never committed.

---

## Local Setup & Run

### Prerequisites

- Python 3.11+ (developed and tested on 3.13)
- An IBM Cloud account with an active watsonx.ai project
  (or run entirely in mock mode — no cloud account required for local dev)

### 1 · Clone and install dependencies

```bash
git clone https://github.com/your-org/delabyrix.git
cd delabyrix
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2 · Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```dotenv
# Required for real watsonx.ai calls:
WATSONX_API_KEY=your_ibm_cloud_api_key_here
WATSONX_PROJECT_ID=your_watsonx_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-4-h-small

# Set to true to run fully offline (mock LLM responses):
WATSONX_MOCK_MODE=false

# API key for watsonx Orchestrate authentication:
API_KEY=your_api_key_for_orchestrate_here

# Application defaults (safe to leave as-is):
LOG_LEVEL=INFO
HITL_CONFIDENCE_THRESHOLD=0.70
SYNTHETIC_DATA_DIR=synthetic_data

# SQLite persistence for the HITL review queue (directory created automatically):
HITL_DB_PATH=data/hitl_queue.db
```

> **Offline / demo mode**: set `WATSONX_MOCK_MODE=true` to skip all real API
> calls. The pipeline returns deterministic stub responses — suitable for
> local demos and CI.

### 3 · Generate synthetic data

```bash
python scripts/generate_synthetic_data.py
```

This creates the `synthetic_data/` directory (gitignored) with:

- `synthetic_data/medication_registry.json` — 50 cross-border medication records
- `synthetic_data/patient_logs.json` — 200 anonymized patient log records
- `synthetic_data/consent_docs/{en,es,hi}/*.txt` — 9 multilingual consent & billing documents

> The FastAPI server also runs this automatically at startup if the files are
> missing, so this step is optional.

### 4 · Start the FastAPI backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- API root: <http://localhost:8000>
- Interactive docs (Swagger UI): <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health check: <http://localhost:8000/health>

### 5 · Start the Streamlit frontend

Open a second terminal (with the same `.venv` active):

```bash
streamlit run frontend/Home.py
```

Streamlit opens at <http://localhost:8501> by default.

### 6 · Run the test suite

```bash
pytest tests/ -v
```

All tests run fully offline (mock mode is forced by the test fixtures):

| Test file | Coverage |
|---|---|
| `tests/test_synthetic.py` | Synthetic data generators |
| `tests/test_registry.py` | Medication registry query & sync |
| `tests/test_registry_changelog.py` | Versioned registry sync & changelog API |
| `tests/test_pipeline.py` | All 5 pipeline stages + HITL escalator |
| `tests/test_hitl.py` | HITL queue, router, and agent router |
| `tests/test_hitl_sqlite.py` | SQLite HITL persistence, thread safety, restart survival |
| `tests/test_document_upload.py` | Custom .txt/.pdf upload & PII-safe clause breakdown |
| `tests/test_proactive_analytics.py` | Zero-PII proactive care pattern analytics |
| `tests/test_api_and_e2e.py` | Registry/document/analytics routers, OpenAPI spec, E2E flows |
| `tests/test_openapi_validation.py` | OpenAPI 3.0 structural validation, unique operationIds, descriptions |

---

## New Capabilities

### 1 · Custom Document Upload & PII-Safe Clause Breakdown (`POST /documents/analyze`)

Patients and providers can upload their own `.txt` or `.pdf` clinical documents
(consent forms, billing statements, insurance letters) for a plain-language,
clause-by-clause explanation.

- **PII redaction first**: the uploaded text passes through Stage 0 before any
  LLM call — SSNs, emails, phone numbers, and DOBs are replaced with typed
  placeholders (e.g. `[SSN]`).
- **Supported formats**: `.txt` and `.pdf` (≤ 5 MB). `.docx` and other formats
  return HTTP 400.
- **Model**: `ibm/granite-4-h-small` via `/ml/v1/text/chat`.
- **Response fields**: `filename`, `detected_language`, `jurisdiction`,
  `pii_redacted` (bool), `redacted_preview`, `analysis`.

### 2 · SQLite HITL Persistence (`HITL_DB_PATH`)

The HITL review queue is now backed by SQLite instead of an in-memory list.

- Review items survive server restarts.
- Thread-safe concurrent writes (WAL mode).
- Configured via `HITL_DB_PATH` in `.env` (default: `data/hitl_queue.db`).
  The parent directory is created automatically.
- In-memory mode (`HITLQueue(db_path=":memory:")`) is still used in tests for
  full isolation.

### 3 · Dynamic Registry Sync & Changelog (`POST /registry/sync`, `GET /registry/changelog`)

Regulatory bulletins from the FDA Orange Book or EU Union Register can be
applied to the live in-memory medication registry without restarting the server.

- Each `POST /registry/sync` call applies a field-level diff to a single
  medication record and records the before/after change in the versioned changelog.
- Changelog entries are monotonically versioned (`v1`, `v2`, …) and ordered
  newest-first.
- Only mutable fields (`status`, `restriction_reason`, `therapeutic_alternatives`,
  `last_updated`) are accepted; `name_generic` and `name_brand` are immutable.
- `GET /registry/changelog?limit=N` returns the audit trail.

### 4 · Zero-PII Proactive Care Pattern Analytics

The `GET /analytics/dashboard` response now includes a `proactive_recommendations`
array derived from aggregated, anonymized patient logs.

- Three pattern categories: `dietary` (e.g. halal/kosher requirements),
  `icd10_cluster` (recurring condition groups), `medication_conflict`
  (cross-jurisdiction drug conflicts).
- Results are sorted by `magnitude` (patient count) descending.
- **Privacy guarantee**: no patient IDs, raw query text, SSNs, or DOBs are
  present. Only statistical aggregates over anonymized synthetic logs.

---

## 3-Minute Demo Walkthrough

> **Setup**: start the FastAPI server and Streamlit app as above, with
> `WATSONX_MOCK_MODE=false` (or `true` for a fully offline demo).
> The walkthrough covers all three user groups.

---

### 0:00–1:00 — Patient Assistant: Cross-Border Banned Drug Escalation

**What to show:**

1. Open the Streamlit app at `http://localhost:8501`. The **Home** page
   shows the three user-group cards. Click **Patient Assistant** in the sidebar.

2. In the **Patient Assistant** page, set:
   - **Language**: Spanish (`es`)
   - **Country**: United States (`US`)
   - **User type**: Patient

3. Enter the query:
   ```
   Tomo metamizol en casa. ¿Está permitido en los Estados Unidos?
   ```
   *(I take metamizole at home. Is it allowed in the United States?)*

4. Submit. Walk through what happens inside the pipeline (visible in the
   pipeline trace accordion):
   - **Stage 0** — PII redaction: no PII detected, text passes clean.
   - **Stage 1** — Translation: Granite 4 (`ibm/granite-4-h-small`) renders the Spanish query in English.
   - **Stage 2** — Medical interpretation: the registry lookup finds
     `metamizole` with status `banned` in `US_FDA`; `has_banned_medication = true`.
   - **Stage 3** — Cultural context: Granite 4 adapts the response for a US
     patient under HIPAA.
   - **Stage 4** — Next steps: Granite 4 recommends therapeutic alternatives
     (ibuprofen, acetaminophen) with a culturally appropriate explanation.
   - **HITL escalator** — Rule 2 fires (banned medication).
     ➜ The API returns **HTTP 202**. The patient sees a localised notice:
     *"Your query has been referred to a care coordinator for review."*

**Key point**: the patient never receives a direct "this is banned" answer —
human oversight is non-negotiable for high-stakes clinical outputs.

---

### 1:00–1:40 — Document Upload & Dynamic Registry Sync

**What to show:**

1. Click **Patient Assistant** and use the **Upload Document** tab.

2. Upload a `.txt` or `.pdf` consent form from your local disk.
   The API calls `POST /documents/analyze`:
   - Stage 0 redacts any PII in the uploaded file.
   - Granite 4 returns a clause-by-clause plain-language breakdown.
   - The `pii_redacted` flag and `redacted_preview` are visible in the response.

3. Switch to **Registry Explorer** in the sidebar.

4. Apply a live bulletin: enter a `medication_id`, source `"FDA Orange Book"`,
   and `updates: {"status": "restricted", "restriction_reason": "Safety review."}`.
   Submit → `POST /registry/sync`.

5. Click **Changelog**: `GET /registry/changelog` now shows `v1` with the
   before/after field diff. The in-memory registry is immediately updated — no
   server restart required.

**Key point**: regulatory data changes don't require deployments. The changelog
provides a full audit trail of every bulletin applied.

---

### 1:40–2:20 — Provider Support & Registry Explorer

**What to show:**

1. Click **Provider Support** in the sidebar.

2. Set **User type**: Provider, **Country**: Germany (`DE`).

3. Enter:
   ```
   Explain laparoscopic cholecystectomy risks to an international patient.
   ```

4. Submit. Point out:
   - **Jurisdiction context**: the EU EMA regime is applied; GDPR privacy note
     is surfaced.
   - **No escalation** (HTTP 200): provider queries about procedure explanation
     are returned directly — only the five escalation rules gate responses.
   - The pipeline trace shows each stage's output without raw PII.

5. Search for `metamizole` in Registry Explorer. Show that:
   - In `US_FDA`: `banned` — restriction reason: *agranulocytosis risk*.
   - In `EU_EMA`: `approved` — same INN, different regulatory outcome.

**Key point**: the jurisdiction resolver (a deterministic lookup table, never
an LLM call) ensures the same drug produces different guidance in different
countries — this is the core cross-border compliance capability.

---

### 2:20–3:00 — Care Coordinator: HITL Approval, BI Dashboard & Proactive Analytics

**What to show:**

1. Click **HITL Review** in the sidebar.

2. The review queue shows the escalated Spanish/metamizole query from the first
   minute, with:
   - `rules_triggered`: `["rule_2_banned_medication"]`
   - `draft_response`: the Granite 4-generated response with alternatives
   - Status: `pending_review`

3. Click **Approve** (or **Reject** with an optional reviewer note).
   The item moves out of the pending queue; its status updates to `approved`.
   Because the queue is SQLite-backed, this approval survives a server restart.

4. Click **BI Dashboard** in the sidebar. Walk through the charts:
   - Total queries processed, escalation rate.
   - Queries by language (Spanish, English, Hindi).
   - Top medication flags (metamizole leading).
   - Jurisdiction breakdown (US FDA vs EU EMA).
   - **Proactive Recommendations** section — shows zero-PII care pattern
     insights from the patient-log baseline:
     - Dietary requirements by nationality (e.g. halal × 5 patients from SA).
     - ICD-10 condition clusters (e.g. Endocrine & Metabolic × 4 patients).
     - Cross-jurisdiction medication conflicts (e.g. domperidone × 3 patients).

5. Confirm the **privacy guarantee** live: inspect the `/analytics/dashboard`
   response body — no raw query text, no patient names, no session IDs, no
   patient IDs. Only language codes, counts, INN drug names, and anonymous
   pattern aggregates appear.

**Key point**: The BI pipeline and the agent pipeline are architecturally
separate. Raw query text *cannot* enter analytics — it is a structural property
of the codebase, not just a policy.

---

## Repository Structure

```
delabyrix/
├── backend/                # FastAPI application
│   ├── main.py             # App entrypoint, router registration, lifespan
│   ├── config.py           # pydantic-settings — all secrets from .env
│   ├── pipeline/           # 5 agentic pipeline stages + HITL escalator
│   ├── watsonx/            # Granite 4 client + Orchestrate adapter (8 skills)
│   ├── registry/           # Cross-border medication registry + sync/changelog
│   ├── jurisdiction/       # Deterministic jurisdiction resolver
│   ├── hitl/               # SQLite-backed HITL review queue + router
│   ├── analytics/          # BI aggregator (incl. proactive analytics) + router
│   ├── synthetic/          # Synthetic data generators (zero PII)
│   └── routers/            # FastAPI route definitions
├── data/                   # Runtime SQLite DB (HITL_DB_PATH, gitignored)
├── frontend/               # Streamlit multi-page app
│   ├── Home.py             # Landing page — user group selector
│   └── pages/
│       ├── 1_Patient_Assistant.py
│       ├── 2_Provider_Support.py
│       ├── 3_HITL_Review.py
│       ├── 4_BI_Dashboard.py
│       └── 5_Registry_Explorer.py
├── orchestrate/
│   └── openapi_spec.yaml   # OpenAPI 3.0 spec — 8 watsonx Orchestrate skills
├── tests/                  # All tests, fully offline (mock mode)
├── scripts/
│   └── generate_synthetic_data.py
├── requirements.txt
├── .env.example            # Template — commit this; never commit .env
├── .gitignore              # Excludes .env, synthetic_data/, secrets/, data/
└── architecture.md         # Full architecture specification
```

## Security & Privacy Guarantees

| Property | How It Is Enforced |
|---|---|
| Zero hardcoded secrets | All credentials loaded via `pydantic-settings` from `.env`; no defaults for credentials |
| `.env` excluded from VCS | `.gitignore` and `.bobignore` both exclude `.env`, `secrets/`, `*.key` |
| `synthetic_data/` excluded | Gitignored — generated output never committed |
| `data/` excluded | Gitignored — SQLite HITL DB never committed |
| Zero real PII in codebase | All dev/test data is synthetically generated; verified by `tests/test_synthetic.py::test_no_real_pii_markers` |
| PII stripped before LLM | Stage 0 (`pii_redactor.py`) runs before any text reaches watsonx.ai — including uploaded documents |
| Analytics isolation | Raw query text structurally cannot enter the analytics aggregator; proactive recommendations contain only statistical aggregates |
| HITL mandatory for high-risk outputs | Five escalation rules are enforced server-side, not in the UI |
| HITL queue persisted safely | SQLite WAL mode; no raw patient text stored — only pipeline traces and draft responses |
| Mock mode for offline use | `WATSONX_MOCK_MODE=true` skips all cloud calls; deterministic stubs |

---

*Built with IBM Bob IDE · IBM watsonx.ai (`ibm/granite-4-h-small` · `/ml/v1/text/chat`) · IBM watsonx Orchestrate*
