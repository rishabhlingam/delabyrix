# Delabyrix — Multilingual Clinical AI Agent & Zero-PII BI Platform

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

1. **Stage 0 — Zero-PII Scrubbing**: strips names, international IDs, phone
   numbers, and addresses into typed `[REDACTED_*]` tokens **before** any text
   touches an LLM or the SQLite persistence layer.
2. **Stage 1 — Translation**: renders the user's query into English using
   IBM Granite 4 (`ibm/granite-4-h-small`) via `/ml/v1/text/chat`.
3. **Stage 2 — Medical Interpretation**: extracts medical concepts and
   cross-checks the cross-border medication registry for banned or restricted
   drugs (`US_FDA` vs. `EU_EMA`).
4. **Stage 3 — Cultural Context**: adapts framing to the user's regulatory
   regime and cultural background.
5. **Stage 4 — Next Steps Guide**: generates role-appropriate guidance for a
   patient, provider, or care coordinator.

**Human-in-the-Loop (HITL)** sits between agent output and the end user for any
high-stakes output: low-confidence responses, banned medications, ICU/surgery
topics, residual PII, and ambiguous jurisdictions all route to a SQLite-backed
coordinator review queue before the patient sees anything.

The BI dashboard gives care coordinators aggregate metrics — language
distribution, escalation rates, top-flagged medications, jurisdiction breakdown,
and proactive care recommendations — with a hard architectural guarantee that raw
query text and patient identifiers never enter the analytics pipeline.

---

## IBM Technology Stack & Architecture

| Component | Technology |
|---|---|
| AI development partner | **IBM Bob IDE** (architecture design, code generation, test writing, compliance review) |
| LLM inference | **IBM watsonx.ai** · model `ibm/granite-4-h-small` · endpoint `/ml/v1/text/chat` |
| Skill orchestration | **IBM watsonx Orchestrate** · OpenAPI 3.0 `v0.2.0` skill export (`orchestrate/openapi_spec.yaml`) · 8 skills |
| Backend API | **FastAPI** (Python 3.11+) · served via Uvicorn on port 8000 · version `0.1.0` |
| Primary frontend | **React 19 + TypeScript + Vite** · IBM Carbon Design System tokens · port 5173 |
| Legacy frontend | **Streamlit** multi-page prototype (`frontend/`) |
| Data layer | Synthetic datasets (zero real PII) · SQLite-backed HITL persistence (`HITL_DB_PATH`) |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│          React + TypeScript + IBM Carbon (http://localhost:5173)     │
│  /assistant · /hitl · /registry · /provider · /analytics            │
│  EN / ES / HI locale toggle · clinical safety disclaimer footer     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP (localhost:8000)
┌──────────────────────────▼──────────────────────────────────────────┐
│                        FastAPI Backend (v0.1.0)                     │
│                                                                     │
│  POST /agent/query  →  Agentic Pipeline (5 stages + HITL)           │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │Stage 0   │→ │Stage 1     │→ │Stage 2       │→ │Stage 3       │  │
│  │Zero-PII  │  │Translate   │  │Medical       │  │Cultural      │  │
│  │Scrubbing │  │(Granite 4) │  │Interpret +   │  │Context       │  │
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
│  POST /agent/query  GET /agent/session/{id}  POST /agent/translate  │
│  GET  /registry/check · /registry/list                              │
│  POST /registry/sync · GET /registry/changelog                      │
│  GET  /documents/{doc_type}/{language}                              │
│  POST /documents/analyze   (.txt / .pdf upload, ≤ 5 MB)            │
│  GET  /hitl/queue  POST /hitl/approve  POST /hitl/reject            │
│  GET  /analytics/dashboard  (incl. proactive_recommendations)       │
│  POST /synthetic/generate  GET /health                              │
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

### watsonx Orchestrate Skills (OpenAPI `v0.2.0` — 8 skills)

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

## Key Features & Modules

### React + IBM Carbon UI (`frontend-react/`)

The primary production UI is a **React 19 + TypeScript + Vite** single-page
application styled with IBM Carbon Design System tokens:

- **Light-mode clinical interface**: Carbon Gray 10 (`#f4f4f4`) page, Blue 60
  (`#0f62fe`) primary, sharp `0px` geometry throughout.
- **Typography**: `IBM Plex Sans` for prose/titles, `IBM Plex Mono` for IDs,
  timestamps, and `[REDACTED_*]` tokens.
- **Icons**: `@carbon/icons-react` (`CheckmarkFilled`, `CloseFilled`,
  `WarningAltFilled`, `Security`, `Translate`, `Time`, `DocumentView`).
- **Live UI localization**: `EN` / `ES` / `HI` locale toggle in the header
  via `LocaleProvider` + `useLocale` hook (`src/lib/i18n.ts`).
- **Persistent clinical safety disclaimer** footer on every page.

### Patient & Document Assistant (`/`)

| Feature | Detail |
|---|---|
| Clinical queries | `POST /agent/query` with language, country, user-type |
| One-click presets | Pre-built clinical scenario buttons |
| Synthetic hospital documents | Load ICU consent, surgical consent, billing explanation |
| Custom document upload | `.txt` / `.pdf` via `POST /documents/analyze` with inline `[REDACTED_*]` pills |
| Non-blocking HITL `202` | Polls `GET /agent/session/{id}` and shows **Approved** / **Rejected** badge |
| Rejection reason display | Bidirectional translation toggle (native ↔ English) via `POST /agent/translate` |
| Pipeline trace | Collapsible 5-stage trace sheet (`PipelineTraceSheet`) |

### HITL Clinical Review Queue (`/hitl`)

| Feature | Detail |
|---|---|
| SQLite-backed queue | Survives server restarts, WAL-mode thread-safe |
| Queue API | `GET /hitl/queue`, `POST /hitl/approve`, `POST /hitl/reject` |
| Bilingual display | Inquiries and draft responses shown in the **patient's original language** by default |
| Translation toggles | Bidirectional `Original Language ↔ English` toggles via `POST /agent/translate` |
| Reviewer rejection notes | Stored with optional `rejection_reason_english` translation |
| Session polling | Clients poll `GET /agent/session/{id}` to retrieve approved text or rejection reason |

### Cross-Border Registry Explorer & Live Bulletin Sync (`/registry`)

| Feature | Detail |
|---|---|
| Side-by-side comparison | `US_FDA` vs. `EU_EMA` status for the same medication |
| Medication check | `GET /registry/check?medication_name=…&jurisdiction=…` |
| Full paginated listing | `GET /registry/list?page=…&page_size=…&jurisdiction=…` |
| Therapeutic alternatives | Surfaced on the registry card for banned/restricted drugs |
| Live Bulletin Sync drawer | Medication selector + source label input → `POST /registry/sync` |
| Versioned audit changelog | Expandable `GET /registry/changelog` with before/after field diffs |

### Provider Clinical Support (`/provider`)

Clinician-mode intake (`user_type: "provider"`) for:
- Culturally framed procedure explanations.
- Local policy checklists.
- Cross-border drug conflict alerts.
- Drug Alert Checker tab for direct registry lookups.

### Zero-PII BI & Proactive Care Dashboard (`/analytics`)

| Feature | Detail |
|---|---|
| Recharts visualizations | Jurisdiction breakdown, top language distribution, user persona split, flagged medications, escalation gauge |
| Date and jurisdiction filters | Optional `date_from`, `date_to`, `jurisdiction` query params on `GET /analytics/dashboard` |
| Proactive Care Recommendations | Dietary Accommodations, ICD-10 Clinical Clusters, Cross-Border Drug Conflict Hotspots |
| Privacy guarantee | No patient IDs, raw query text, SSNs, or DOBs — only statistical aggregates over anonymized synthetic logs |

---

## Local Setup & Run

### Prerequisites

- Python 3.11+ (developed and tested on 3.13)
- Node.js 18+ and npm 9+ (for the React frontend)
- An IBM Cloud account with an active watsonx.ai project
  (or run entirely in mock mode — no cloud account required for local dev)

### 1 · Clone and install Python dependencies

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

### 3 · Generate synthetic data (optional)

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

### 5 · Start the React frontend (primary UI)

Open a second terminal:

```bash
cd frontend-react
npm install
npm run dev
```

The React app opens at <http://localhost:5173> by default.

**All five pages are fully implemented:**

| Route | Page |
|---|---|
| `/` | Patient & Document Assistant |
| `/hitl` | HITL Clinical Review Queue |
| `/registry` | Cross-Border Registry Explorer + Live Bulletin Sync |
| `/provider` | Provider Clinical Support |
| `/analytics` | Zero-PII BI Dashboard + Proactive Care |

Switch UI language (EN / ES / HI) using the locale toggle in the top header bar.

### 5b · Start the Streamlit frontend (legacy / reference)

```bash
streamlit run frontend/Home.py
```

Streamlit opens at <http://localhost:8501> by default.

---

## API Reference

All endpoints are served by the FastAPI backend at `http://localhost:8000`.
Full interactive documentation is available at `/docs` (Swagger UI) and `/redoc`.

### Agent Router (`/agent`)

| Method | Path | Returns | Description |
|---|---|---|---|
| POST | `/agent/query` | 200 or 202 | Full 5-stage pipeline. Returns direct response (`200`) or escalates to HITL (`202 Accepted`) |
| GET | `/agent/session/{session_id}` | 200 | Poll for HITL review status: `pending` / `approved` / `rejected` |
| POST | `/agent/translate` | 200 | Translate text between any supported language pair (EN / ES / HI) |

### Registry Router (`/registry`)

| Method | Path | Description |
|---|---|---|
| GET | `/registry/check` | Look up a medication by INN or brand name in `US_FDA` or `EU_EMA` |
| GET | `/registry/list` | Paginated full registry listing (`page`, `page_size`, optional `jurisdiction` filter) |
| POST | `/registry/sync` | Apply a live regulatory bulletin (field-level diff + changelog entry) |
| GET | `/registry/changelog` | Versioned sync audit trail, newest-first (default limit 50, max 200) |

### Documents Router (`/documents`)

| Method | Path | Description |
|---|---|---|
| GET | `/documents/{doc_type}/{language}` | Retrieve a synthetic consent or billing document |
| POST | `/documents/analyze` | Upload `.txt` / `.pdf` (≤ 5 MB), apply Stage 0 PII redaction, return clause breakdown |

**Valid `doc_type` values**: `consent_icu_admission` · `consent_surgery` · `billing_deductible_explanation`  
**Valid `language` values**: `en` · `es` · `hi`

### HITL Router (`/hitl`)

| Method | Path | Description |
|---|---|---|
| GET | `/hitl/queue` | List all pending review items (oldest first) |
| POST | `/hitl/approve` | Approve a draft response and release it |
| POST | `/hitl/reject` | Reject a draft response with optional reviewer note |

### Analytics Router (`/analytics`)

| Method | Path | Description |
|---|---|---|
| GET | `/analytics/dashboard` | Aggregated BI metrics + proactive care recommendations (zero PII) |

### Synthetic & Health

| Method | Path | Description |
|---|---|---|
| POST | `/synthetic/generate` | Regenerate all synthetic data files and reload registry |
| GET | `/health` | Readiness probe — returns `{"status": "ok", "version": "0.1.0"}` |

---

## Automated Testing

### Python test suite (pytest)

Run fully offline — `WATSONX_MOCK_MODE` is forced by test fixtures:

```bash
pytest tests/ -v
```

**382 tests passing** across 11 files:

| Test file | Tests | Coverage |
|---|---|---|
| `tests/test_api_and_e2e.py` | 58 | Registry / document / analytics routers, OpenAPI spec, full E2E pipeline flows |
| `tests/test_bilingual_hitl.py` | 14 | Bilingual HITL payload fields, `POST /agent/translate`, Spanish escalation flow |
| `tests/test_document_upload.py` | 18 | Custom `.txt` / `.pdf` upload, PII-safe clause breakdown, file type validation |
| `tests/test_hitl.py` | 42 | HITL queue, router, agent router, approve/reject flows |
| `tests/test_hitl_sqlite.py` | 32 | SQLite HITL persistence, WAL thread safety, server-restart survival |
| `tests/test_openapi_validation.py` | 14 | OpenAPI 3.0 structural validation, unique `operationId`s, `x-ibm-nl-intent` annotations |
| `tests/test_pipeline.py` | 82 | All 5 pipeline stages, HITL escalator rules, PII redaction patterns |
| `tests/test_proactive_analytics.py` | 23 | Zero-PII proactive care pattern analytics (dietary, ICD-10, medication conflict) |
| `tests/test_registry.py` | 48 | Medication registry query, sync, changelog, paginated listing |
| `tests/test_registry_changelog.py` | 19 | Versioned registry sync, field-level diffs, changelog ordering |
| `tests/test_synthetic.py` | 32 | Synthetic data generators, zero-PII marker verification |

### TypeScript / React test suite (Vitest)

```bash
cd frontend-react
npm test
```

**59 tests passing** across 5 test files (Vitest + Testing Library + jsdom):

| Test file | Tests | Coverage |
|---|---|---|
| `src/__tests__/PatientAssistantPage.test.tsx` | 13 | Clinical queries, `202` HITL polling, approved/rejected badge transitions, `[REDACTED_*]` pill rendering, bilingual rejection reason toggles |
| `src/__tests__/HITLReviewPage.test.tsx` | 12 | HITL queue rendering, approve/reject actions, draft editing, translation toggles |
| `src/__tests__/AnalyticsDashboardPage.test.tsx` | 18 | Dashboard charts, proactive care recommendations, date/jurisdiction filters |
| `src/__tests__/RegistryExplorerPage.test.tsx` | 8 | Medication search, side-by-side comparison, bulletin sync, changelog expansion |
| `src/__tests__/ProviderSupportPage.test.tsx` | 8 | Provider query submission, `202` escalation badge, Drug Alert Checker tab |

**Total: 441 tests passing (382 Python + 59 TypeScript)**

---

## Repository Structure

```
delabyrix/
├── backend/                       # FastAPI application (v0.1.0)
│   ├── main.py                    # App entrypoint, router registration, lifespan
│   ├── config.py                  # pydantic-settings — all secrets from .env
│   ├── seed_demo_data.py          # Optional demo data seeder
│   ├── pipeline/                  # 5 agentic pipeline stages + HITL escalator
│   │   ├── pii_redactor.py        # Stage 0: Zero-PII scrubbing
│   │   ├── translator.py          # Stage 1: Granite 4 translation
│   │   ├── medical_interpreter.py # Stage 2: Medical interpretation + registry check
│   │   ├── cultural_context.py    # Stage 3: Cultural context adaptation
│   │   ├── next_steps_guide.py    # Stage 4: Role-appropriate next steps
│   │   └── hitl_escalator.py      # HITL escalation evaluation (5 rules)
│   ├── watsonx/                   # Granite 4 client + Orchestrate adapter
│   │   ├── client.py              # WatsonxClient (real + mock modes)
│   │   └── orchestrate_adapter.py # Orchestrate-compatible response shaping
│   ├── registry/                  # Cross-border medication registry
│   │   ├── models.py              # Pydantic models
│   │   ├── query.py               # Medication lookup (INN / brand)
│   │   └── sync.py                # Bulletin sync, changelog, in-memory reload
│   ├── jurisdiction/              # Deterministic jurisdiction resolver
│   │   ├── resolver.py            # Country → US_FDA / EU_EMA
│   │   └── rules.py               # Jurisdiction rule definitions
│   ├── hitl/                      # SQLite-backed HITL review queue
│   │   ├── models.py              # ReviewItem, Approve/RejectRequest models
│   │   ├── queue.py               # HITLQueue (SQLite WAL, in-memory test mode)
│   │   └── router.py              # GET /hitl/queue, POST /hitl/approve|reject
│   ├── analytics/                 # Zero-PII BI aggregator
│   │   ├── aggregator.py          # Builds dashboard metrics + proactive recs
│   │   └── router.py              # GET /analytics/dashboard
│   ├── synthetic/                 # Synthetic data generators (zero real PII)
│   │   ├── medication_registry.py # 50 cross-border medication records
│   │   ├── patient_logs.py        # 200 anonymized patient log records
│   │   └── consent_billing_docs.py# 9 multilingual consent & billing docs
│   └── routers/                   # FastAPI route modules
│       ├── agent.py               # POST /agent/query|translate, GET /agent/session/{id}
│       ├── documents.py           # GET /documents/{type}/{lang}, POST /documents/analyze
│       ├── registry.py            # GET /registry/check|list|changelog, POST /registry/sync
│       └── synthetic.py           # POST /synthetic/generate
├── frontend-react/                # React 19 + Vite primary UI (http://localhost:5173)
│   └── src/
│       ├── api/client.ts          # Typed API client for all backend endpoints
│       ├── pages/                 # 6 page components
│       │   ├── HomePage.tsx
│       │   ├── PatientAssistantPage.tsx
│       │   ├── HITLReviewPage.tsx
│       │   ├── RegistryExplorerPage.tsx
│       │   ├── ProviderSupportPage.tsx
│       │   └── AnalyticsDashboardPage.tsx
│       ├── components/
│       │   ├── layout/            # AppShell, LocaleSwitcher, PipelineTraceSheet
│       │   ├── registry/          # RegistryStatusCard, RegulatorySyncDrawer
│       │   └── ui/                # shadcn/ui primitives (IBM Carbon tokens)
│       ├── lib/
│       │   ├── i18n.ts            # LocaleProvider + useLocale hook (EN/ES/HI)
│       │   └── utils.ts           # cn() utility
│       └── __tests__/             # 5 Vitest + Testing Library test suites (59 tests)
├── frontend/                      # Streamlit multi-page app (legacy / reference)
│   ├── Home.py
│   └── pages/
│       ├── 1_Patient_Assistant.py
│       ├── 2_Provider_Support.py
│       ├── 3_HITL_Review.py
│       ├── 4_BI_Dashboard.py
│       └── 5_Registry_Explorer.py
├── orchestrate/
│   └── openapi_spec.yaml          # OpenAPI 3.0 v0.2.0 — 8 watsonx Orchestrate skills
├── tests/                         # Python test suite — 382 tests, fully offline
├── scripts/
│   └── generate_synthetic_data.py # Optional standalone data generator
├── data/                          # Runtime SQLite DB (HITL_DB_PATH, gitignored)
├── synthetic_data/                # Generated data directory (gitignored)
├── bob_sessions/                  # IBM Bob session storage
├── requirements.txt
├── .env.example                   # Template — commit this; never commit .env
├── .gitignore                     # Excludes .env, synthetic_data/, secrets/, data/
└── architecture.md                # Full architecture specification
```

---

## Security & Privacy Guarantees

| Property | How It Is Enforced |
|---|---|
| Zero hardcoded secrets | All credentials loaded via `pydantic-settings` from `.env`; no defaults for credentials |
| `.env` excluded from VCS | `.gitignore` and `.bobignore` both exclude `.env`, `secrets/`, `*.key` |
| `synthetic_data/` excluded | Gitignored — generated output never committed |
| `data/` excluded | Gitignored — SQLite HITL DB never committed |
| Zero real PII in codebase | All dev/test data is synthetically generated; verified by `tests/test_synthetic.py::test_no_real_pii_markers` |
| PII stripped before LLM | Stage 0 (`pii_redactor.py`) runs before any text reaches watsonx.ai — including uploaded documents |
| Second-pass PII redaction | For non-English queries, Stage 0 runs again on the translated English text to catch romanised names |
| Analytics isolation | Raw query text structurally cannot enter the analytics aggregator; proactive recommendations contain only statistical aggregates |
| HITL mandatory for high-risk outputs | Five escalation rules enforced server-side, not in the UI |
| HITL queue persisted safely | SQLite WAL mode; no raw patient text stored — only pipeline traces and draft responses |
| Mock mode for offline use | `WATSONX_MOCK_MODE=true` skips all cloud calls; deterministic stubs used in all 382 pytest tests |

---

*Built with IBM Bob IDE · IBM watsonx.ai (`ibm/granite-4-h-small` · `/ml/v1/text/chat`) · IBM watsonx Orchestrate (`openapi_spec.yaml v0.2.0` · 8 skills)*
