# AutoResearch getdaytrends Prompt Injection Normalization

## Objective

Make keyword prompt-injection filtering catch confusable Unicode and explicit
backslash-newline phrase splits before keywords are placed into LLM prompts.

## Source Signal

- Source: `FlowiseAI/Flowise`
- Commit: `42d593f8ca854471059051a7fdd89bf8d8ab7c12`
- URL: `https://github.com/FlowiseAI/Flowise/commit/42d593f8ca854471059051a7fdd89bf8d8ab7c12`
- Relevant signal: `Fix Flowise 591 (#6476)`.
- Local interpretation: Flowise hardened a validator by normalizing with NFKC
  and removing backslash-newline continuations before denylist matching. Locally,
  `getdaytrends.sanitize_keyword()` had the same class of text-pattern risk for
  prompt-control phrases embedded in trend keywords.

## A/B Contract

- Baseline: `sanitize_keyword()` removed control characters and matched prompt
  injection phrases only against the raw keyword text.
- Variant: normalize a scan copy with `unicodedata.normalize("NFKC", ...)`,
  remove explicit backslash-newline continuations, and apply the existing
  injection patterns to that scan text before returning the sanitized keyword.
- Primary KPI: homoglyph prompt verbs, fullwidth role markers, and
  backslash-newline split prompt-control phrases are replaced with `***`.
- Guardrails: normal keywords, Korean text, control-character stripping, and
  length limiting keep their existing behavior.
- Decision: adopted.

## Implementation

- `automation/getdaytrends/utils.py`
  - Adds `_normalize_for_injection_scan()`.
  - Uses NFKC normalization and explicit line-join removal before pattern
    matching.
  - Preserves the previous raw-text replacement path when the normalized scan
    does not contain an injection phrase.
- `automation/getdaytrends/tests/test_utils.py`
  - Adds regressions for `\u1d62gnore previous`, fullwidth `system:`, and
    `ignore \\\nprevious`.

## Verification

- `python -m pytest automation\getdaytrends\tests\test_utils.py -q`
  - `22 passed`
- `python -m py_compile automation\getdaytrends\utils.py`
  - passed
- `python ops\scripts\run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-prompt-injection-normalization-2026-06-05.json`
  - `2/2 passed`

## Remaining Boundary

This cycle hardens keyword sanitization before prompt use. It does not claim
full adversarial prompt-injection resistance for all downstream content fields
or external model behavior.

global_objective_complete=false
