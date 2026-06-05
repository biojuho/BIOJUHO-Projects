# DailyNews NotebookLM Audio Artifact Guard

Generated at: `2026-06-05T12:25:03+09:00`

## Source Signal

- Repository: `vercel/ai`
- Source commit: `https://github.com/vercel/ai/commit/2ce3c65448f36eb3629c50095888a64326167d0d`
- Upstream signal: `feat(provider/google-vertex): add Gemini text-to-speech (speech) model support (#15779)`
- Local mapping: DailyNews already exposes NotebookLM artifact generation for
  weekly digests and upload exports. The audio branch should be treated as a
  first-class speech artifact route with explicit wiring and regression tests,
  instead of relying on generic artifact handling.

## A/B Contract

- Baseline: `--content-types audio` could select the audio path, but the upload
  script passed an extra date argument into `_generate_artifact()`. The adapter
  also assumed `client.artifacts` existed and had no audio-specific regression
  test proving `generate_audio()` receives the weekly briefing instructions.
- Variant: keep the public return shape as artifact IDs, add a shared artifact
  identifier helper, guard missing artifact APIs, route `audio` only through
  `generate_audio(..., instructions=WEEKLY_AUDIO_INSTRUCTIONS)`, and fix the
  upload caller to match the adapter signature.
- Primary KPI: mocked NotebookLM tests prove audio generation is called with the
  right instructions and that missing audio support degrades to `None` without
  calling another artifact method.
- Guardrails: report, mind-map, and slide-deck artifact IDs keep the existing
  string return contract; no live NotebookLM or Gemini credentials are required.
- Decision: adopted.

## Changed Files

- `automation/DailyNews/src/antigravity_mcp/integrations/notebooklm_adapter.py`
  - Adds `_artifact_identifier()` and guards missing artifact APIs before
    routing content types.
  - Locks the audio route to `generate_audio()` with
    `WEEKLY_AUDIO_INSTRUCTIONS`.
- `automation/DailyNews/scripts/export_to_notebooklm.py`
  - Fixes the upload artifact call to pass only `client`, `notebook_id`, and
    `content_type`.
- `automation/DailyNews/tests/test_notebooklm_adapter.py`
  - Adds audio artifact routing, missing audio support, missing artifact API,
    and upload-caller regression coverage.

## Verification

- `python -m pytest automation\DailyNews\tests\test_notebooklm_adapter.py -q --tb=line`
  - `19 passed`
- `python -m py_compile automation\DailyNews\src\antigravity_mcp\integrations\notebooklm_adapter.py automation\DailyNews\scripts\export_to_notebooklm.py automation\DailyNews\tests\test_notebooklm_adapter.py`
  - passed
- `git diff --check`
  - passed
- `python -m pytest automation\DailyNews\tests\test_notebooklm_adapter.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `38 passed`
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid `66` criteria, `cycle_evidence_ready=true`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - valid `7` requirements, `cycle_prompt_covered=true`, `global_objective_complete=false`
- Product pre-push gate for commit `5caa8d4`
  - Python smoke: `237 passed`
  - Dashboard UI tests: `9 passed`
  - Dashboard production build and bundle budget: passed
  - Canva MCP typecheck and production build: passed
  - MCP/runtime/audit gates: passed
  - Completion audit before this proof refresh: valid `64` criteria

## Remaining Boundary

This cycle hardens the local DailyNews NotebookLM audio artifact contract. It
does not execute live NotebookLM audio generation or add Gemini/Vertex
credentials.

- Product proof baseline for this commit: `5caa8d4`.
- Active current-tip freshness proof after rebase: `0b0515b`.
- `global_objective_complete=false`
