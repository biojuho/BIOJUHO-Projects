# Vibe Coding Architecture Review

Date: 2026-04-02
Scope: `AgriGuard`, `getdaytrends`, `DailyNews`, `content-intelligence`, `packages/shared`

## Assumed Flow

This review was based on the current repository structure and runtime paths:

1. `getdaytrends` collects and scores trend candidates, then stores them in SQLite/Postgres and exposes summaries through dashboards.
2. `DailyNews` consumes shared LLM and fact-check helpers to generate and evaluate content.
3. `content-intelligence` reads `getdaytrends` outputs, stores its own local state, and publishes approved content to Notion and X.
4. `AgriGuard` exposes FastAPI endpoints, WebSocket streams, IoT ingestion, Redis-backed rate limiting, and a React frontend.

## Findings

### 1. Broken cache fallback in AgriGuard

- File: `apps/AgriGuard/backend/main.py`
- Risk: when `shared.cache` import fails, the local fallback does not implement `incr()`, but the rate limiter always calls it.
- Impact: a packaging or path issue can turn "cache unavailable" into request failures.

Action:

- Reuse the shared no-op cache contract instead of defining a partial local fallback.
- Keep one cache interface for both normal and degraded modes.

### 2. Invalid X publish contract in content-intelligence

- File: `automation/content-intelligence/storage/x_publisher.py`
- Risk: the current flow tries to import a non-existent `XClient`, then falls back to a blocking `requests.post()` call inside an async function.
- Risk: configuration currently treats any `X_ACCESS_TOKEN` as enough for posting, even though X post creation requires user-context auth.
- Impact: the code can appear "publish-ready" while failing at runtime because the token or client contract is wrong.

Action:

- Require a user-context token explicitly in config validation and error messages.
- Use `httpx.AsyncClient` for the publish call.
- Keep the publish path behind a small adapter boundary instead of an implicit fallback chain.

### 3. Cross-project coupling remains high

- Files:
  - `automation/content-intelligence/main.py`
  - `automation/content-intelligence/collectors/gdt_bridge.py`
  - `automation/getdaytrends/analyzer.py`
  - `automation/DailyNews/src/antigravity_mcp/integrations/shared_llm_resolver.py`
- Risk: `sys.path` mutation and direct DB/schema reads make internal implementation details act like public APIs.

Action:

- Move app-to-app access behind package or service boundaries.
- Replace direct SQLite bridge reads with a typed client or service layer.

### 4. Shared LLM contract drift is being masked

- Files:
  - `automation/DailyNews/src/antigravity_mcp/integrations/llm_adapter.py`
  - `automation/DailyNews/output/frozen_eval/direct_eval.md`
- Risk: signature mismatches already show up as runtime `TypeError`, but the system silently downgrades to fallback providers.

Action:

- Add a compatibility contract test for `shared.llm`.
- Treat signature drift as a CI failure, not as a silent runtime downgrade.

### 5. Shared package metadata is incomplete

- File: `packages/shared/pyproject.toml`
- Risk: runtime imports for observability and metrics are broader than the declared install dependencies.

Action:

- Declare extras for observability and telemetry dependencies.
- Consider splitting `shared` into smaller installable units when the boundary becomes stable.

### 6. SQLAlchemy query style is still legacy in AgriGuard

- File: `apps/AgriGuard/backend/main.py`
- Risk: the app is still on `Session.query(...)` style even though the project has already moved onto modern dependencies elsewhere.

Action:

- Migrate gradually to `select()` + `Session.execute()/scalar()`.

## Execution Order

1. Fix the AgriGuard cache fallback so degraded mode is safe.
2. Fix the `content-intelligence` X publishing contract and async path.
3. Add tests that lock both fixes in place.
4. Record the changes in `HANDOFF.md`, `TASKS.md`, and `CONTEXT.md`.
5. Schedule the broader `sys.path` and DB-boundary cleanup as a follow-up slice.

## Immediate Done Criteria

- AgriGuard can rate-limit safely even when shared cache import falls back.
- `content-intelligence` no longer depends on an imaginary `XClient`.
- X publishing uses async I/O and clearly states that user-context auth is required.
- Relevant smoke and targeted tests pass.
