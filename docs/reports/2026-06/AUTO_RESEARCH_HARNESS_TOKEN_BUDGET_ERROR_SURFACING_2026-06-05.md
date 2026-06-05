# AutoResearch Harness Token Budget Error Surfacing

## Objective

Adopt the current `strands-agents/harness-sdk` error-surfacing signal in the
local shared harness so token-budget denials leave structured operational
evidence instead of only a string reason.

## Source Signal

- Repository: `strands-agents/harness-sdk`
- Source page: `https://github.com/strands-agents/harness-sdk/commits/main/`
- Source commit: `https://github.com/strands-agents/harness-sdk/commit/a2f1425`
- Upstream signal: `fix: surface MaxTokensError when max_tokens truncates tool input JSON (#2620)`
- Local mapping: keep the existing `TokenBudgetExceededError` behavior, but make
  the harness audit record expose the concrete token-budget denial fields.

## A/B Contract

- Baseline: `HarnessWrapper.execute_tool()` caught any token-budget gate failure
  as `Exception`, logged a denial reason string, and re-raised the original
  exception. Operators could see that a token budget failed, but not the exact
  used/requested/projected/max token values in structured metadata.
- Variant: catch `TokenBudgetExceededError` specifically, keep re-raising it,
  and add `error_type`, `token_budget_exceeded`, `used_tokens`,
  `requested_tokens`, `projected_tokens`, `max_tokens`, and `remaining_tokens`
  to the audit record metadata.
- Primary KPI: token-budget failures are queryable as structured audit data.
- Guardrails: permission/risk/cost/HITL behavior is unchanged, the exception type
  still reaches callers, and token usage is not recorded for denied calls.
- Decision: adopted. The variant makes token truncation and budget pressure
  diagnosable without changing the harness execution contract.

## Changed Files

- `packages/shared/harness/core.py`
  - Imports and catches `TokenBudgetExceededError` at the token budget gate.
  - Adds structured token-budget denial metadata to `AuditLogger.log_denied()`.
- `packages/shared/harness/tests/test_token_tracker.py`
  - Extends `test_execute_token_gate_blocks` to assert the denial metadata.

## Verification

- `python -m pytest packages\shared\harness\tests\test_token_tracker.py -q --tb=line`
  - `32 passed`
- `python -m pytest packages\shared\harness\tests -q --tb=line`
  - `208 passed`
- `current_tip_freshness_gate`
  - proof baseline: `c5f76d4`
  - allowed post-proof paths include `packages/shared/harness/core.py` and
    `packages/shared/harness/tests/test_token_tracker.py`
- `protected_path_freshness`
  - proof baseline: `c5f76d4`
  - no changed protected paths after proof
- `global_objective_complete=false`

## Remaining Boundary

This cycle improves local harness observability only. It does not complete the
credential-gated Canva/GitHub/Telegram/OTLP/hosted-runtime launch blockers, and
the broader AutoResearch loop remains open until the user explicitly stops it.
