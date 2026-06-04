# Canva MCP Pre-Push Typecheck Build Guard

- Date: 2026-06-05
- Scope: `mcp/canva-mcp` package verification and the shared pre-push gate
- Baseline: Canva widget click-smoke tests were in pre-push, but package-level TypeScript and production widget build checks were not.
- Variant: Add `npm.cmd --prefix mcp/canva-mcp run typecheck` and `npm.cmd --prefix mcp/canva-mcp run build` to `ops/hooks/pre-push`, with visible stage markers.
- Decision: Adopted.

## A/B Contract

- Primary KPI: package type/build regressions fail before push instead of relying only on click-smoke coverage.
- Guardrails: existing pytest smoke bundle, dashboard UI/build/bundle checks, credential dry-runs, MCP runtime smokes, objective coverage, and completion audit remain in the hook.
- Reversibility: remove the two Canva MCP npm blocks from `ops/hooks/pre-push` if runtime cost becomes unacceptable.

## Implementation

- `ops/hooks/pre-push` now prints `==> Running Canva MCP typecheck...` and runs `npm.cmd --prefix mcp/canva-mcp run typecheck`.
- `ops/hooks/pre-push` now prints `==> Running Canva MCP production build...` and runs `npm.cmd --prefix mcp/canva-mcp run build`.
- `tests/test_pre_push_hook.py` asserts both markers and both `npm.cmd --prefix` commands stay wired.
- `.gitattributes` pins generated Canva MCP asset and HTML/config line endings to LF so `npm.cmd --prefix mcp/canva-mcp run build` does not leave tracked widget assets dirty on Windows.

## Protected Path Freshness

- Product/config proof commit: `06feb55` (`fix(canva-mcp): normalize generated html line endings`).
- `protected_path_freshness`: the completion contract now uses `06feb55` as the proof commit.
- Result after proof: no changed protected paths after proof; follow-up changes are limited to `.gitattributes`, pre-push hook wiring, tests, reports, and completion contract evidence.

## Verification

- `npm.cmd --prefix mcp/canva-mcp run typecheck` under Git `sh.exe`: passed.
- `npm.cmd --prefix mcp/canva-mcp run build` under Git `sh.exe`: passed.
- Build cleanliness with `.gitattributes`: passed; `git status --short --branch` showed only `.gitattributes` before hook/evidence edits.
- Product/config push for `06feb55`: pre-push passed with `198` pytest checks, dashboard Vitest `9` tests, dashboard production build, dashboard bundle check, credential dry-runs, MCP smokes, workflow gates, objective coverage, and completion audit `39` criteria.

## Remaining Blockers

- `global_objective_complete=false` because the AutoResearch loop is open-ended until user stop.
- Canva OAuth/OpenAPI live execution, GitHub high-volume live refresh, Telegram delivery, OTLP collector shipping, and hosted runtime/tracing still require operator-owned credentials or runtime choices.
