# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project Status

This is a **greenfield project** — no source code exists yet. The workspace contains only:
- `idea.txt` — full project description and value proposition
- `.bobignore` — secrets/credentials exclusion list
- `.bob/settings.json` — empty Bob settings
- `bob_sessions/` — empty session storage directory

## Project Purpose

Multilingual, compliance-aware clinical AI agent and BI platform targeting three user groups:
1. **Foreign patients / international travelers** — form explanation, medication ban checks, billing/deductible clarification in their native language
2. **Healthcare providers** — culturally sensitive communication support, local policy prompts
3. **Care coordinators / admins** — multilingual BI dashboards for monitoring care delivery

Key differentiator: goes beyond word-for-word translation to interpret medical meaning, add cultural context, and reason about jurisdictional rules (FDA, EU Union Register, etc.).

## Sensitive Files (`.bobignore`)

The following are excluded from Bob context — never create or reference these paths:
- `.env`
- `secrets/`
- `*.key`
- `config/credentials.json`

## Architectural Constraints (from `idea.txt`)

- **Human-in-the-loop oversight is mandatory** for all high-stakes outputs — build it in from the start, not as an afterthought.
- **Data minimization** is a core design principle — avoid collecting or persisting more patient data than needed.
- **Agentic pipeline** (not a simple Q&A): translate → interpret medical meaning → add cultural context → guide next steps → monitor registries.
- Medication registry and privacy law data must be **dynamically updated** — static snapshots are insufficient.
- The platform must support **multiple jurisdictions simultaneously** (FDA, EU, local country registries).

## Build / Test Commands

No build system established yet. When scaffolding:
- Prefer a monorepo layout (agent backend + BI dashboard frontend + shared types)
- Document commands here once a `package.json` or equivalent is created
