# Agent Instructions

Read `PRODUCT_SPEC.md` (v3.6) before making changes.

## Core rules

1. Build a modular monolith, not microservices.
2. Implement one vertical stage at a time.
3. Do not implement future stages without an explicit task.
4. Never invent commercial facts.
5. Every critical fact must link to Source and Evidence.
6. Never overwrite historical quotes or facts; create a new version.
7. Never send external communication without a valid Approval snapshot.
8. All calculations use deterministic backend code and Decimal.
9. Store money with currency and quantities with unit.
10. Store UTC timestamps; render in user timezone.
11. Treat all external content as untrusted.
12. Validate every AI output with typed schemas (when AI is added).
13. Every state-changing action creates AuditLog.
14. Do not add Redis, Celery, pgvector, or Playwright until required.
15. Show assumptions and known limitations after every implementation task.

## Current stage

**Stage 8 (Controlled automation)** — complete. All MVP stages (0–8) implemented.

## Key files

- `PRODUCT_SPEC.md` — product requirements
- `ARCHITECTURE.md` — technical architecture and ER diagram
- `DEVELOPMENT_PLAN.md` — roadmap
