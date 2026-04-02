# Content Automation V2.0 Module Contract Draft

Date: 2026-04-02
Status: Draft for approval before implementation restart

## 1. Purpose

This document defines the integration contracts for the core content automation pipeline so that modules stop depending on each other's private file paths, ad-hoc imports, and internal database schemas.

## 2. Contract Rules

1. Every inter-module handoff must use a versioned DTO or event.
2. A module may read another module's storage only through an explicitly approved compatibility layer.
3. Silent contract downgrade is not allowed for schema or signature mismatches.
4. Fallback is allowed only when:
   - the same DTO/event shape is preserved
   - the reason is logged
   - the caller can observe degraded mode
5. Publisher adapters are responsible for platform-auth semantics; upstream modules are not.

## 3. Module Responsibilities

| Module | Responsibility | Owns | Must Not Own |
|---|---|---|---|
| `getdaytrends` | collect, dedup, score, enrich trend inputs | trend intake records, evidence, source freshness | final publish decisions |
| `packages/shared` | reusable utilities and common contracts | shared DTO helpers, cache, LLM contracts, observability helpers | app-specific workflow orchestration |
| `DailyNews` | insight extraction and structured generation helpers | content reasoning transforms, provider orchestration | platform publishing |
| `content-intelligence` | editorial orchestration, QA, approval, publishing coordination | content drafts, QA reports, publish jobs, performance linkage | raw trend collection internals |
| publisher adapters | channel-specific delivery and receipts | auth-aware publish jobs and receipts | upstream scoring or QA policy |
| analytics loop | performance collection and strategy updates | performance events, attribution summaries | raw trend collection |

## 4. Canonical DTOs

### 4.1 TrendCandidate v1

Produced by: `getdaytrends`

Consumed by: validation/enrichment stage

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `trend_candidate.v1` |
| `trend_id` | `str` | yes | immutable identifier |
| `keyword` | `str` | yes | normalized trend keyword |
| `collected_at` | `datetime` | yes | UTC |
| `source_platform` | `str` | yes | `x`, `threads`, `news`, etc |
| `source_ref` | `str` | no | source URL or platform ref |
| `raw_volume` | `int` | no | raw source signal |
| `raw_payload_hash` | `str` | yes | dedup/idempotency aid |
| `country` | `str` | no | source market |

### 4.2 ValidatedTrend v1

Produced by: intake validation layer

Consumed by: generation

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `validated_trend.v1` |
| `trend_id` | `str` | yes | inherited stable id |
| `keyword` | `str` | yes | normalized |
| `confidence_score` | `float` | yes | 0.0 to 1.0 |
| `source_count` | `int` | yes | evidence breadth |
| `evidence_refs` | `list[str]` | yes | source references |
| `freshness_minutes` | `int` | yes | time since source capture |
| `dedup_fingerprint` | `str` | yes | dedup contract |
| `rejection_flags` | `list[str]` | yes | empty when valid |

### 4.3 ContentDraft v1

Produced by: generation/orchestration stage

Consumed by: QA/safety gate

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `content_draft.v1` |
| `draft_id` | `str` | yes | immutable draft id |
| `trend_id` | `str` | yes | upstream linkage |
| `platform` | `str` | yes | publish target |
| `content_type` | `str` | yes | `post`, `thread`, `blog`, etc |
| `body` | `str` | yes | main content |
| `title` | `str` | no | required for long form where applicable |
| `hashtags` | `list[str]` | yes | can be empty |
| `persona_id` | `str` | no | generation strategy id |
| `prompt_version` | `str` | yes | traceability |
| `generator_provider` | `str` | yes | shared.llm / fallback provider name |
| `generator_model` | `str` | no | model id |
| `draft_metadata` | `dict` | yes | structured extras |

### 4.4 QAReport v1

Produced by: safety gate

Consumed by: publish decision layer

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `qa_report.v1` |
| `draft_id` | `str` | yes | linked draft |
| `total_score` | `int` | yes | normalized total |
| `passed` | `bool` | yes | publish gate decision |
| `fact_score` | `int` | yes | component score |
| `policy_score` | `int` | yes | component score |
| `format_score` | `int` | yes | component score |
| `warnings` | `list[str]` | yes | diagnostics |
| `blocking_reasons` | `list[str]` | yes | empty when passed |
| `review_notes` | `str` | no | optional human note |

### 4.5 PublishJob v1

Produced by: orchestration layer

Consumed by: publisher adapter

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `publish_job.v1` |
| `publish_job_id` | `str` | yes | immutable job id |
| `draft_id` | `str` | yes | approved content linkage |
| `platform` | `str` | yes | adapter selector |
| `body` | `str` | yes | final content body |
| `auth_profile` | `str` | yes | token/profile selector |
| `idempotency_key` | `str` | yes | required for retries |
| `requested_at` | `datetime` | yes | UTC |
| `dry_run` | `bool` | yes | release safety |

### 4.6 PublishReceipt v1

Produced by: publisher adapter

Consumed by: analytics + audit

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `publish_receipt.v1` |
| `publish_job_id` | `str` | yes | originating job |
| `success` | `bool` | yes | publish result |
| `platform_post_id` | `str` | no | external id when success |
| `platform_post_url` | `str` | no | canonical link |
| `published_at` | `datetime` | no | success timestamp |
| `failure_code` | `str` | no | machine-readable failure class |
| `failure_reason` | `str` | no | human-readable detail |
| `provider_response_excerpt` | `str` | no | bounded debug text |

### 4.7 PerformanceEvent v1

Produced by: analytics collectors

Consumed by: feedback loop

| Field | Type | Required | Notes |
|---|---|---|---|
| `contract_version` | `str` | yes | `performance_event.v1` |
| `publish_job_id` | `str` | yes | primary linkage |
| `platform_post_id` | `str` | yes | external linkage |
| `captured_at` | `datetime` | yes | UTC |
| `metric_window` | `str` | yes | `1h`, `24h`, `7d` |
| `impressions` | `int` | no | metric payload |
| `engagements` | `int` | no | metric payload |
| `clicks` | `int` | no | metric payload |
| `conversions` | `int` | no | optional business metric |
| `collector_status` | `str` | yes | `complete`, `partial`, `unavailable` |

## 5. Canonical Events

| Event | Producer | Consumer | Purpose |
|---|---|---|---|
| `trend.intake.completed.v1` | intake | validation | new candidates ready |
| `trend.validation.completed.v1` | validation | generation | only validated trends proceed |
| `content.draft.created.v1` | generation | safety gate | content candidate available |
| `content.qa.completed.v1` | safety gate | publish coordinator | gate result available |
| `publish.job.created.v1` | coordinator | adapter | publish requested |
| `publish.job.completed.v1` | adapter | analytics/audit | final publish result |
| `performance.capture.completed.v1` | analytics | learning loop | attribution input ready |
| `learning.update.created.v1` | analytics/review | strategy owners | prompt/persona/scoring updates |

## 6. Allowed Fallback Patterns

| Area | Allowed | Not Allowed |
|---|---|---|
| LLM provider | switch provider while preserving request/response contract and logging degraded mode | swallowing signature mismatch and silently changing semantics |
| Cache | no-op cache preserving interface | partial fallback object missing called methods |
| Publisher auth | dry-run or explicit auth failure receipt | pretending publish is enabled with an incompatible token type |
| Data source | quarantine invalid input and continue batch | passing malformed trend records to generation |

## 7. Explicitly Forbidden Integration Patterns

These are transition debt only and should not be expanded:

1. `sys.path.insert(...)` as a long-term module integration mechanism
2. direct reads of another app's private SQLite schema as a primary contract
3. "publish-ready" checks that only validate token presence but not token type
4. runtime fallback that hides provider signature drift from CI
5. cross-module assumptions without `contract_version`

## 8. Error Contract

All machine-facing failures should map to a stable code family:

| Code Family | Meaning |
|---|---|
| `INGEST_*` | collection/input failure |
| `VALIDATION_*` | freshness/schema/dedup/evidence failure |
| `GENERATION_*` | provider/prompt/format generation failure |
| `QA_*` | quality/policy/fact gate failure |
| `PUBLISH_*` | auth/adapter/platform delivery failure |
| `METRICS_*` | post-publication collection failure |

Every failure object should include:

- `code`
- `message`
- `stage`
- `entity_id`
- `retryable`
- `observed_at`

## 9. Ownership Boundaries to Enforce Next

1. `getdaytrends` should emit validated trend data, not expose raw DB internals to consumers.
2. `DailyNews` should consume a stable LLM contract, not dynamically negotiate unknown signatures at runtime.
3. `content-intelligence` should orchestrate publish jobs, not own channel-specific auth semantics.
4. publisher adapters should be the only place that knows platform API quirks.
5. analytics should attach outcomes back to `publish_job_id` and `draft_id`, not ad-hoc text matching.

## 10. Approval Questions

Before implementation restart, these must be confirmed:

1. Is `content-intelligence` the permanent orchestration layer, or only the current one?
2. Do we bless event-based handoff, DTO-based library calls, or both?
3. Which channels are in-scope for V2.0 release: X only, X + Notion, or more?
4. What is the single publish gate threshold for V2.0?
5. What is the first golden E2E scenario we will certify?

## 11. Immediate Next Deliverables After Approval

1. DTO definitions as code-level schemas
2. a compatibility test suite for `shared.llm`
3. a publish adapter interface with auth-profile typing
4. a deprecation plan for direct DB reach-through integrations
