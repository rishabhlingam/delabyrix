# Plan Mode Rules

This file provides guidance to agents when working with code in this repository.

## Architectural Constraints to Carry Into Planning

- **Agentic pipeline, not a chatbot**: the core flow is translate → interpret medical meaning → add cultural context → guide next steps. Plan components around these distinct stages, not a single LLM call.
- **Registry update mechanism is a first-class concern** — the FDA/EU Union Register sync must be a scheduled, versioned process; plan for it from day one, not as a later add-on.
- **Human-in-the-loop is an architectural layer**, not a UI feature — plan a dedicated review/approval service between the agent output and the end-user response.
- **BI dashboards are for care coordinators only** — keep their data pipeline separate from the patient-facing agent to avoid leaking PII into aggregate analytics.
- **Privacy law varies by jurisdiction** — plan a jurisdiction-resolution step early in the pipeline so downstream components always know which privacy regime applies before touching patient data.
- Monorepo structure is preferred (see `AGENTS.md` in repo root) — plan package boundaries before writing any code.
