# Shared LLM Grok Seed Settings Guard

Generated at: `2026-06-05T11:44:48+09:00`

## Source Signal

- Repository: `pydantic/pydantic-ai`
- Source commit: `https://github.com/pydantic/pydantic-ai/commit/70cb782fdc39c26a2b2123a6eb7e338c0d8f0654`
- Upstream signal: `Map base seed setting to xAI (#5741)`
- Local mapping: shared LLM calls must preserve deterministic seed settings and
  provider-specific Grok/xAI model settings across direct OpenAI-compatible,
  LiteLLM sync, LiteLLM async, and proxy-gateway paths.

## A/B Contract

- Baseline: `LLMPolicy` had no seed field, cache keys could not distinguish
  seeded requests, and `BackendManager.call()` discarded model-patch
  `extra_params` except for `max_tokens`.
- Variant: `LLMPolicy.seed` is included in cache keys and forwarded only when
  present. Grok JSON model patches now survive as `extra_body` alongside seed
  for direct xAI/OpenAI-compatible calls and LiteLLM sync/async calls.
- Primary KPI: tests prove Grok JSON mode sends `reasoning=false` plus
  `seed=123` through direct, LiteLLM sync, and LiteLLM async paths.
- Guardrails: default calls do not add seed, `seed=0` is preserved through the
  proxy gateway, and non-Grok provider behavior remains unchanged.
- Decision: adopted.

## Changed Files

- `packages/shared/llm/models.py`
  - Adds optional `LLMPolicy.seed`.
- `packages/shared/llm/client.py`
  - Includes seed in cache keys and conditionally forwards it to native/proxy
    dispatch.
- `packages/shared/llm/backends.py`
  - Preserves selected provider settings and model-patch `extra_params` through
    `extra_body` for OpenAI-compatible and LiteLLM calls.
- `packages/shared/llm/proxy_adapter.py`
  - Preserves optional seed, including falsy `0`, for LiteLLM proxy gateway
    calls.
- `packages/shared/llm/test_backends_b017.py`
  - Adds direct, LiteLLM sync, and LiteLLM async Grok settings regression tests.
- `packages/shared/llm/tests/test_proxy_adapter.py`
  - Proves `seed=0` reaches the gateway and `LLMClient` proxy dispatch.
- `packages/shared/llm/tests/test_client_cache_and_dispatch.py`
  - Proves different seeds produce different cache keys.

## Verification

- `python -m pytest packages\shared\llm\test_backends_b017.py packages\shared\llm\tests\test_proxy_adapter.py packages\shared\llm\tests\test_client_cache_and_dispatch.py -q --tb=line`
  - `65 passed`
- `python -m pytest tests\test_shared_llm.py tests\test_llm_enhancements.py packages\shared\llm\tests -q --tb=line`
  - `152 passed`
- `python -m pytest packages\shared\llm\test_backends_b017.py packages\shared\llm\tests\test_proxy_adapter.py packages\shared\llm\tests\test_client_cache_and_dispatch.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `84 passed`
- `python -m py_compile packages\shared\llm\backends.py packages\shared\llm\client.py packages\shared\llm\proxy_adapter.py packages\shared\llm\models.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - `60 criteria`, `cycle_evidence_ready=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - `7 requirements`, `cycle_prompt_covered=true`, `global_objective_complete=false`
- `git diff --check`
  - passed

## Remaining Boundary

This cycle hardens the local shared LLM adapter. It does not add a full
Pydantic AI runtime or require live xAI credentials.

- Product proof baseline for this commit: `4401cb2`.
- `global_objective_complete=false`
