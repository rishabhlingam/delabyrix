# Agent Mode Rules

This file provides guidance to agents when working with code in this repository.

## Greenfield Scaffolding Guidance

No source code exists yet. When creating the first files:

- **Never commit secrets** — `.env`, `secrets/`, `*.key`, and `config/credentials.json` are in `.bobignore` and must stay out of the repo.
- **Human-in-the-loop hooks are non-negotiable** — any code path that produces a clinical recommendation, medication flag, or consent explanation must route through a review/approval step before returning output to the user.
- **Multi-jurisdiction logic must be data-driven**, not hardcoded — medication ban rules differ per country and change over time; model them as configurable rules loaded from an updatable registry, not as `if/else` chains.
- **Data minimization**: do not cache or log full patient profiles; pass only the minimum fields needed for each agent step.
- **Monorepo preferred**: keep agent backend, BI dashboard, and shared types as separate packages within one repo to avoid circular dependency pitfalls later.
