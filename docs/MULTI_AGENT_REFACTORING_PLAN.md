# Multi-Agent Refactoring Plan

**Status:** Stage 1 in progress  
**Source:** `MULTI_AGENT_ARCHITECTURE_CHANGE_REQUEST.md` (revision 2)  
**Date:** 2026-07-13

---

## 1. Current architecture assessment

Commodity Agent is a monolithic FastAPI backend with a Next.js frontend. Business logic lives in `backend/app/services/`. AI calls go through `get_ai_provider()` and are logged via `log_ai_usage()` → `AIUsageLog`.

### What works today

| Area | Implementation |
|------|----------------|
| Deal lifecycle | Opportunity → Deal → RFQ → FulfilmentConfiguration → EconomicsSnapshot → Offer |
| Evidence (deal stage) | `Requirement` → `Evidence` with `user_confirmed` |
| AI budget | `AIBudgetSettings`, monthly limits, `AIUsageLog` |
| Tender search (new path) | `InternetSourceSearchRun` → `InternetSourceSearchHit` → manual promote |
| Tender search (legacy) | `MonitoringRule` → `MonitoringRun` → auto Opportunity |
| Research | `ResearchCampaign` → `ResearchLead` (mock search, separate from tender pipeline) |
| Product matching | `product_resolution.py` with catalog context |
| RFQ drafting | `rfq.py` + Communication workflow |
| Economics | Deterministic `economics.py` (not AI-generated totals) |

### Main architectural problems

1. **One-shot promotion** — `tender_promotion.py` runs qualification, supplier suggestion, price/margin estimates, and Opportunity creation in a single AI call (`TenderFeasibilityOutput`).
2. **Mixed search pipeline** — `internet_source_search.py` combines discovery, fetch, AI extraction, enrichment, and deterministic qualification in one service.
3. **Dual discovery paths** — RSS monitoring auto-creates Opportunities; internet search requires manual promote. Different semantics, same product surface.
4. **No persisted qualification entity** — `TenderHitEvaluation` is a dataclass; results live in `extracted_fields` JSONB on hits.
5. **AI usage not run-scoped** — `AIUsageLog` has no link to search runs, hits, or agent type. Cost attribution per function is impossible.
6. **Evidence gap in discovery** — Tender evidence is `evidence_excerpt` on hits, not the deal-centric `Evidence` model.
7. **Name collision risk** — existing `Task` model is user workflow tasks; new `AgentTask` is machine-orchestrated work units.

---

## 2. Target architecture

```text
User UI (Opportunity / Deal card)
        ↓
Deal Coordinator (workflow, next action, AgentTask scheduling)
        ↓
┌───────────────────┬────────────────────┬─────────────────────┐
│ Tender Discovery  │ Tender Qualification│ Supply / Logistics  │
│ (ingestion only)  │ (analysis only)     │ Discovery           │
└───────────────────┴────────────────────┴─────────────────────┘
        ↓                       ↓                    ↓
   TenderCandidate      QualifiedRequirement    SupplierLead / LogisticsRoute
        ↓
Communication Service (drafts, send after approval)
Economics Service (deterministic, STALE propagation)
Evidence layer (ESTIMATED → CONFIRMED, no silent overwrite)
AgentRun / AgentResult / AIUsageLog (single cost truth)
```

Logical agents are **domain services + prompt pipelines** in one backend (no microservices in MVP).

---

## 3. Mapping current services → target agents

| Current service / module | Target role | Action |
|--------------------------|-------------|--------|
| `internet_source_search.py` | Tender Discovery | **Extend** — split ingestion vs qualification in Stage 2 |
| `internet_source_discovery.py` | Tender Discovery (catalog) | **Reuse** |
| `integrations/ted/`, World Bank | Tender Discovery connectors | **Reuse** |
| `tender_hit_evaluation.py` | Tender Qualification (deterministic) | **Reuse** |
| `tender_hit_enrichment.py` | Tender Qualification (AI extract) | **Extend** — track via AgentRun |
| `tender_promotion.py` | Mixed (anti-pattern) | **Decompose** in Stage 2 — see §23 |
| `monitoring.py` | Tender Discovery trigger | **Extend** — align with TenderCandidate |
| `product_resolution.py` | Product matching (pre-qualification) | **Reuse** — AgentType `PRODUCT_MATCHING` |
| `product_assistant.py` | Catalog assistant | **Reuse** |
| `counterparty_enrichment.py` | Supply Discovery (partial) | **Extend** in Stage 3 |
| `supplier_lead.py` | Supply Discovery | **Extend** → `SupplierLead` entity |
| `research.py` | Research campaigns (parallel track) | **Reuse** |
| `rfq.py`, `inbox.py`, `email_loop.py` | Communication Service | **Reuse** |
| `economics.py`, `configurations.py` | Economics Service | **Reuse** — no AI for totals |
| `automation.py` | Deal Coordinator (RFQ follow-up) | **Extend** in Stage 4 |
| `opportunity_status.py` | Deal Coordinator (status) | **Reuse** |

---

## 4. Existing-to-target entity mapping

| Existing entity | Target responsibility | Decision |
|-----------------|----------------------|----------|
| `AIUsageLog` | Financial journal: tokens, cost, operation | **Reuse as-is** — add optional `agent_run_id` FK |
| `AgentRun` | Execution unit: model, prompt version, status, link to task | **New** — one run per AI invocation (or tool batch) |
| `AgentTask` | Orchestration unit: what to do, for which Opportunity/hit | **New** — distinct from user `Task` |
| `AgentResult` | Structured output of a run | **New** |
| `ResearchCampaign` | Business process container for market research | **Reuse** — campaigns may spawn `AgentTask` rows |
| `InternetSourceSearchRun` | Batch discovery execution record | **Reuse** — maps to Tender Discovery batch, not duplicate of AgentRun |
| `InternetSourceSearchHit` | Discovered tender publication | **Extend** → interim `TenderCandidate` (Stage 2) |
| `MonitoringRun` | Scheduled connector execution | **Reuse** — triggers Tender Discovery AgentTask |
| `MonitoredPublication` | RSS/HTML item | **Extend** → align with TenderCandidate |
| `SupplierLeadContext` / `SupplierLeadMatch` | Supplier matching on Opportunity | **Extend** → `SupplierLead` in Stage 3 |
| `ExtractionResult` | Document AI extraction | **Reuse** — link via AgentRun |
| `CommercialFact` (research) | Research facts with status | **Reuse** as evidence pattern reference |
| User `Task` | Human to-do on Opportunity/Deal | **Reuse** — do not merge with AgentTask |

### Single source of truth decisions

| Concern | Source of truth | Notes |
|---------|-----------------|-------|
| AI cost / tokens | `AIUsageLog` | Budget sums stay here; `AgentRun` holds copy + link via `ai_usage_log_id` |
| Run status / errors | `AgentRun` | `InternetSourceSearchRun.status` remains for batch discovery only |
| Structured agent output | `AgentResult` | JSON payload + summary + confidence |
| Work queue | `AgentTask` | Coordinator creates tasks; workers update status |
| Discovered tender (pre-opp) | `InternetSourceSearchHit` → `TenderCandidate` | Stage 2 rename/extend, not parallel table |
| Promotion decision | `QualifiedRequirement` | Stage 2 — new table or hit sub-record |

**Rule:** No second parallel billing system. Every new AI path must call `log_ai_usage()` with `agent_run_id`.

---

## 5. Required new entities (phased)

### Stage 1 (implemented in this change)

- `AgentType` enum
- `AgentTask`, `AgentRun`, `AgentResult` tables
- `agent_runtime.py` service
- `app/agents/` interfaces
- Agent Activity API + UI tab

### Stage 2 (requires product decision)

- `TenderCandidate` (extend `InternetSourceSearchHit` or alias view)
- `QualifiedRequirement`
- Promotion mode feature flag
- Decompose `tender_promotion.py`

### Stage 3

- `SupplierLead` (extend existing supplier models)
- `LogisticsRoute`

### Stage 4

- Deal Coordinator state machine
- Next-best-action service

---

## 6. Database migration plan

| Migration | Content | Reversible |
|-----------|---------|------------|
| `019_agent_runtime.py` | `agent_tasks`, `agent_runs`, `agent_results`; `ai_usage_logs.agent_run_id` | Yes — drop tables + column |
| `020_tender_candidate.py` (Stage 2) | Qualification fields on hits or new table | TBD |
| `021_qualified_requirement.py` (Stage 2) | Qualification persistence | TBD |

---

## 7. API changes

### Stage 1

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agent-activity` | List tasks/runs (filters: opportunity_id, deal_id, agent_type) |
| GET | `/opportunities/{id}/agent-activity` | Activity for one Opportunity |

Existing endpoints unchanged.

### Stage 2+

- `POST /tender-candidates/{id}/qualify`
- `POST /qualified-requirements/{id}/promote` (replaces direct hit promote depending on mode)

---

## 8. Frontend changes

### Stage 1

- `AgentActivityPanel` on Opportunity detail — journal tab, not primary UI

### Stage 5

- Overview cards: Tender / Requirement / Suppliers / Logistics / Economics status
- Next action banner
- Evidence tab for discovery pipeline

---

## 9. Prompt changes

| Stage | Change |
|-------|--------|
| 1 | None — only instrumentation |
| 2 | Split `TenderFeasibilityOutput` into qualification-only schema; remove supplier/price/margin from qualification prompt |
| 2 | Tender search extraction prompt — ingestion fields only |
| 3 | Supplier discovery prompt — separate from qualification |
| 3 | Logistics prompt — separate from supplier |

---

## 10. Agent permissions

| Agent | Autonomous | Requires approval |
|-------|------------|-------------------|
| Tender Discovery | Search, ingest, dedupe | — |
| Tender Qualification | Analyze, score, propose reject | Create Opportunity (mode-dependent) |
| Supply Discovery | Search, rank, draft RFQ | Send RFQ |
| Logistics Discovery | Estimate routes | Confirm freight quote |
| Communication | Draft messages | Send binding messages |
| Economics | — | User confirms snapshot |
| Deal Coordinator | Create AgentTask, recommend action | Stage transitions with gates |

---

## 11. Evidence rules

Align with change request §8:

1. AI cannot overwrite `CONFIRMED` facts.
2. Conflicting values stored separately; dependents → `STALE`.
3. Tender hit `evidence_excerpt` migrates to structured evidence references on `QualifiedRequirement`.
4. `OpportunitySpecValue.user_confirmed` remains user gate for requirement specs.

---

## 12. Approval rules

Unchanged from current: RFQ send, offer send, automation binding class, AI budget override.

Stage 2 adds: Opportunity creation from tender per promotion mode.

---

## 13. Backward compatibility

- All existing endpoints remain.
- `InternetSourceSearchHit` promote flow unchanged until Stage 2 + product mode selected.
- `monitoring.py` auto-promotion unchanged until Stage 2.
- `AIUsageLog` queries without `agent_run_id` continue to work.
- Tests: 129 unit tests must pass; integration test excluded by default.

---

## 14. Testing strategy

| Layer | Approach |
|-------|----------|
| Agent runtime | Unit tests for task/run/result lifecycle |
| Service wiring | Assert `agent_run_id` on `log_ai_usage` for wired services |
| Promotion modes (Stage 2) | Parametrized tests per mode A/B/C |
| Integration | `pytest -m integration` for live TED/API |
| Regression | Full `pytest` on every PR |

---

## 15. Risks

| Risk | Mitigation |
|------|------------|
| AgentTask vs Task confusion | Clear naming in API/UI: «Agent Activity» vs «Tasks» |
| Over-instrumentation overhead | One AgentRun per AI call, not per HTTP request |
| Stage 2 breaks promote UX | Feature flag `LEGACY_AUTO_PROMOTION` |
| Dual monitoring paths | Document; unify in Stage 2 |
| Migration scope creep | Strict phase gates; product sign-off before Stage 2 |

---

## 16. Phased implementation plan

### Stage 1 — Architectural separation ✅ (this PR)

- [x] AgentType, AgentTask, AgentRun, AgentResult
- [x] Agent interfaces in `app/agents/`
- [x] `agent_runtime.py` + `AIUsageLog.agent_run_id`
- [x] Wire: `product_resolution`, `tender_hit_enrichment`, `tender_promotion`
- [x] Agent Activity API + UI
- [ ] All AI call sites wired (remaining: extraction, rfq, internet_source_search, discovery)

**Acceptance:** existing tests pass; AI calls in wired services create AgentRun; cost in AIUsageLog.

### Stage 2 — Tender Discovery vs Qualification

**Blocked on product decision** — choose promotion mode (§23).

### Stage 3 — Supply + Logistics separation

### Stage 4 — Deal Coordinator

### Stage 5 — UI optimization

---

## 17. Acceptance criteria (Stage 1)

- [x] `pytest` passes (excluding integration)
- [x] No user workflow changes
- [x] Agent Activity visible on Opportunity card
- [x] Each wired AI call has AgentRun + AIUsageLog link
- [x] Structured AgentResult stored for wired calls

---

## 18. Open questions (product owner)

1. **Promotion mode for Stage 2:** A (manual), B (auto with gates), or C (legacy flag)? **Recommend B for pilot, C as default until UI ready.**
2. **Unify monitoring auto-promote with internet search hits?** Recommend yes, behind flag.
3. **Rename InternetSourceSearchHit → TenderCandidate in UI?** Recommend gradual alias.
4. **Research campaigns vs tender discovery — merge or keep parallel?** Recommend keep parallel; shared AgentRun layer only.

---

## 19. Product behavior changes (require explicit approval)

| Change | Current | Proposed | Stage |
|--------|---------|----------|-------|
| Opportunity from tender | One AI call → Opportunity with indicative economics | Qualification → optional promote | 2 |
| Monitoring RSS | Auto Opportunity | TenderCandidate first | 2 |
| Hit promote button | Direct promote + feasibility AI | Qualify then promote | 2 |
| Supplier/price on promote | Shown as feasibility | Moved to Supply Discovery; ESTIMATED only | 2 |

**Do not implement Stage 2 behavior until mode is chosen.**

---

## 20. `tender_promotion.py` decomposition map

| Current function / output | Target owner | Stage |
|---------------------------|--------------|-------|
| `evaluate_tender_hit()` re-run | Tender Qualification (deterministic) | 2 |
| `TenderFeasibilityOutput` product/route fit | Tender Qualification | 2 |
| `proposed_supplier` | Supply Discovery | 3 |
| `estimated_purchase_price`, `estimated_sale_price` | Supply Discovery / Economics (ESTIMATED) | 3 |
| `estimated_freight`, `preliminary_margin` | Logistics Discovery + Economics Service | 3 |
| `feasible` boolean → promotion gate | Tender Qualification decision | 2 |
| `Opportunity` creation | Deal Coordinator + promotion mode | 2 |
| `indicative_economics` on Opportunity | Economics Service snapshot (ESTIMATED) | 3 |
| `attach_tender_link` | Tender Discovery (metadata) | 2 |

---

## 21. Files touched in Stage 1

| File | Change |
|------|--------|
| `backend/app/domain/enums.py` | Agent enums |
| `backend/app/domain/models.py` | Agent models |
| `backend/alembic/versions/019_agent_runtime.py` | Migration |
| `backend/app/agents/base.py` | Agent interface |
| `backend/app/agents/registry.py` | Agent metadata |
| `backend/app/services/agent_runtime.py` | Runtime |
| `backend/app/services/ai_budget.py` | `agent_run_id` param |
| `backend/app/services/product_resolution.py` | Wire runtime |
| `backend/app/services/tender_hit_enrichment.py` | Wire runtime |
| `backend/app/services/tender_promotion.py` | Wire runtime (legacy) |
| `backend/app/api/routes/agent_activity.py` | API |
| `backend/app/api/schemas_agent_activity.py` | Schemas |
| `frontend/src/components/AgentActivityPanel.tsx` | UI |
| `frontend/src/app/opportunities/[id]/page.tsx` | Tab |

---

## 22. Recommended promotion modes (Stage 2 preview)

### A. MANUAL_APPROVAL

- TenderCandidate auto-created from search
- User reviews qualification → clicks «Create Opportunity»
- **Pros:** lowest false-positive risk  
- **Cons:** slower deal flow  
- **AI cost:** qualification on demand only

### B. AUTO_QUALIFY_WITH_GATES (recommended pilot)

- Qualification runs automatically on new hits
- Opportunity only if `QUALIFIED`, score ≥ threshold, mandatory fields present, no critical gaps
- **Pros:** balance of speed and control  
- **Cons:** requires threshold tuning  
- **AI cost:** one qualification per hit

### C. LEGACY_AUTO_PROMOTION

- Current `tender_promotion.py` behavior behind `FEATURE_LEGACY_TENDER_PROMOTION=true`
- **Pros:** zero regression during migration  
- **Cons:** keeps anti-pattern  
- **Migration:** default on until B is validated

---

*End of plan. Stage 2 implementation requires product owner sign-off on §18 and §19.*
