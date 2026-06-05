# AutoResearch DailyNews NotebookLM Speech Alias Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Source signal: the live GitHub commit digest surfaced `vercel/ai`
  `feat(provider/google-vertex): add Gemini text-to-speech (speech) mode support (#15779)`.
- Source link: https://github.com/vercel/ai/commit/2ce3c65448f36eb3629c50095888a64326167d0d

## A/B Contract

- Baseline: DailyNews NotebookLM exports accepted `audio`, but operator-facing
  artifact requests using `speech`, `text-to-speech`, or `tts` were treated as
  unknown content types and silently produced no audio artifact.
- Variant: normalize weekly NotebookLM content types through a shared adapter
  helper, map speech aliases to the canonical `audio` artifact, and deduplicate
  equivalent aliases before invoking NotebookLM artifact generation.
- Primary KPI: `speech`, `audio`, and `tts` together generate one `audio`
  artifact request and one canonical `audio` result key.
- Guardrails: the underlying NotebookLM API call remains `generate_audio`; no
  external credentials or live NotebookLM calls are required for the regression.
- Decision rule: adopt only if adapter/export tests pass and both touched modules
  compile.

## Result

- Adopted variant: yes.
- Added `normalize_weekly_content_type()` and `normalize_weekly_content_types()`.
- `create_weekly_digest()` now canonicalizes requested weekly artifact types.
- `export_to_notebooklm --content-types speech ...` now normalizes upload
  artifact requests before generation.

## Changed Paths

- `automation/DailyNews/src/antigravity_mcp/integrations/notebooklm_adapter.py`
- `automation/DailyNews/scripts/export_to_notebooklm.py`
- `automation/DailyNews/tests/test_notebooklm_adapter.py`

## Verification

- `python -m pytest automation\DailyNews\tests\test_notebooklm_adapter.py -q`
  - Passed: `21`.
- `python -m py_compile automation\DailyNews\src\antigravity_mcp\integrations\notebooklm_adapter.py automation\DailyNews\scripts\export_to_notebooklm.py`
  - Passed.

## Next Cycle

- Continue selecting source-backed hardening targets from the live GitHub digest.

## Audit Marker

- `global_objective_complete=false`
