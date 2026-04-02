# Content Automation Pipeline V2.0 PRD

Date: 2026-04-02
Owner: Workspace PM reset draft
Scope: `getdaytrends`, `DailyNews`, `packages/shared`, `content-intelligence`, publishing/analytics loop

## 1. Product One-Liner

Build an operational AI content automation pipeline that turns validated trend inputs into high-quality, policy-safe, performance-tracked published content with a closed feedback loop.

## 2. Why We Are Resetting

The project has accumulated strong local fixes, smoke coverage, and module hardening, but the center of gravity drifted from end-to-end product flow to local issue resolution.

Current drift symptoms:

- smoke, lint, cache, schema, and monitoring fixes advanced faster than the canonical business workflow
- module boundaries are still implementation-driven rather than product-contract-driven
- success is often measured as "tests pass" instead of "trend to published learning loop completes"
- sidecar app work and platform plumbing dilute focus from the core content pipeline

## 3. North Star

Deliver a repeatable weekly/daily operating loop:

1. collect trend signals
2. validate and enrich them
3. generate channel-specific drafts
4. run QA, fact-check, and policy gates
5. publish only approved content
6. collect performance outcomes
7. feed those outcomes back into scoring, prompts, timing, and persona decisions

## 4. Target Users

Primary:

- solo operator running AI-first content programs
- PM/founder who needs dependable content operations, not just draft generation

Secondary:

- analyst/editor reviewing final publish candidates
- operator monitoring failures, low-quality drafts, and platform auth issues

## 5. Problem Statement

Today the workspace can generate and validate many pieces of the system, but it does not yet expose a single, authoritative pipeline contract that guarantees:

- stable handoff between collection, generation, QA, publishing, and analytics
- clear failure semantics
- versioned data contracts across modules
- reliable platform-auth assumptions
- a measurable feedback loop that improves content quality over time

## 6. Success Metrics

| Metric | Definition | Initial Target |
|---|---|---|
| Publishable Yield | `% of collected trend batches that produce at least 1 publish-safe content item` | >= 40% |
| QA Pass Rate | `% of generated items that pass quality/policy gate without manual rewrite` | >= 60% |
| Publish Reliability | `% of approved publish jobs that complete without auth/runtime failure` | >= 95% |
| Feedback Completion | `% of published items with performance events collected within 48h` | >= 90% |
| Learning Loop Latency | time from publish to attribution-ready analytics | <= 48h |

## 7. Non-Goals for This Milestone

- building unrelated product verticals into the same milestone path
- expanding channel count before X/Notion/core analytics are stable
- adding new model/provider complexity before contract compatibility is locked
- treating direct DB reach-through as a long-term integration mechanism

## 8. Canonical Workflow

| Stage | Name | Purpose | Primary Owner Module | Output |
|---|---|---|---|---|
| 1 | Trend Intake | Collect trend candidates and source evidence | `getdaytrends` | `TrendCandidate[]` |
| 2 | Validation & Enrichment | Remove bad/duplicate data, attach evidence/confidence | `getdaytrends` + `packages/shared` | `ValidatedTrend[]` |
| 3 | Insight & Drafting | Convert trends into platform-ready draft candidates | `DailyNews` + `shared.llm` + `content-intelligence` | `ContentDraft[]` |
| 4 | Safety Gate | QA, policy, fact-check, persona/tone, format validation | `content-intelligence` | `ApprovedContent[]` / `RejectedContent[]` |
| 5 | Publishing | Deliver approved content to channels with audit trail | publisher adapters | `PublishReceipt[]` |
| 6 | Performance Capture | Collect post-publication metrics and failures | analytics/collectors | `PerformanceEvent[]` |
| 7 | Feedback Loop | Update scoring, prompts, timing, and persona strategy | analytics + review layer | `LearningUpdate` |

## 9. Required Product Gates

| Gate | What Must Be True | If Failed |
|---|---|---|
| Intake Gate | source exists, freshness OK, schema valid, duplicate state known | quarantine input and log reason |
| Draft Gate | draft has required metadata, platform length/format valid | reject draft before QA |
| Safety Gate | fact/policy/QA threshold passed | block publish and store diagnostics |
| Publish Gate | auth valid, adapter available, idempotency key assigned | mark as publish-failed, do not silently drop |
| Feedback Gate | metrics collected or marked unavailable with reason | surface gap in ops dashboard |

## 10. V2.0 Phases

| Phase | Goal | Concrete Work | Output | Exit Criteria |
|---|---|---|---|---|
| Phase 1 | North Star Reset | freeze scope, define KPI, separate core pipeline from side tracks | scope memo | team aligned on one product path |
| Phase 2 | Canonical Flow | define official stage map with owners and boundaries | workflow spec | one authoritative flow exists |
| Phase 3 | Contract Lock | define DTO/event/version rules | module contract doc | modules can integrate without DB reach-through |
| Phase 4 | Intake Reliability | validate freshness, dedup, schema, trust score | intake validation layer | bad input no longer leaks forward |
| Phase 5 | Generation Reliability | lock LLM contracts, prompt versions, fallback policy | generation contract | signature drift becomes visible in CI |
| Phase 6 | Safety Gate | unify QA/fact/policy gate before publish | approval pipeline | only approved content enters publish queue |
| Phase 7 | Publisher Hardening | formalize auth, retry, async IO, audit logs, dry-run | adapter layer | publish status is operationally trustworthy |
| Phase 8 | Feedback Loop | performance attribution and strategy update | analytics loop | publish outcomes change future decisions |
| Phase 9 | E2E Release Gate | test full happy/degraded/failure paths | golden E2E suite | release is judged by workflow success |

## 11. Immediate Decisions

These rules should become active immediately:

1. The core product is the content automation pipeline, not the broader workspace.
2. Direct DB reads across apps are tolerated only as transition debt, not as a target design.
3. Provider fallback is allowed only when the contract is compatible and observable.
4. "Publish-ready" means auth contract, adapter behavior, and audit logging are all satisfied.
5. A green smoke suite is necessary but not sufficient for milestone completion.

## 12. Milestone Deliverables

V2.0 milestone is considered complete only when all of the following exist:

- a canonical workflow doc
- a module contract doc with versioned DTOs/events
- deterministic safety gate behavior
- stable publisher adapters for the chosen channels
- feedback metrics tied back to content generation decisions
- at least one golden end-to-end scenario passing consistently

## 13. Open Risks

- lingering `sys.path` coupling can keep hiding broken integration boundaries
- direct SQLite coupling may block safe refactors in `getdaytrends`
- silent provider fallback can mask content quality regressions
- channel auth contracts may drift faster than local smoke checks reveal

## 14. Recommended Next PM Step

Do not reopen feature coding broadly yet.

First approve:

1. the canonical workflow
2. the module contracts
3. the milestone scope boundary

Only after that should implementation restart against a fixed V2.0 path.
