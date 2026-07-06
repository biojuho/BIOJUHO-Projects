# AutoResearch Loop: Skill AgriGuard Launch Loop Contract

- Date: 2026-07-07 KST
- Scope: AutoResearch Karpathy Loop skill guidance for AgriGuard launch work
- Owned code paths:
  - `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
  - `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
  - `tests/test_auto_research_karpathy_skill.py`
- Report paths:
  - `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-07_SKILL_AGRIGUARD_LAUNCH_LOOP.md`
  - `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AUTO_RESEARCH_SKILL_AGRIGUARD_LAUNCH_LOOP_2026-07-07.md`

## Objective

The AutoResearch skill already validated generic source-backed A/B loops and DeSci launch click guidance. After the AgriGuard launch hardening passes, the skill did not yet encode the AgriGuard-specific browser suite, evidence classes, child verdict rows, or Firebase-gated compose replacement boundary. That made future resumes more likely to rediscover the same launch contract.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` latest observed `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Refreshed `ops/scripts/github_modernization_radar.py` with latest GitHub commit checks.
- Radar result: 8 sources reviewed, adopted=8, partially_adopted=0, watch=0.
- Relevant adopted pattern: continuous loops need durable machine-readable status, fail-closed launch gates, and explicit blocker boundaries.

## A/B Hypothesis

- Baseline: skill validator passed, but workspace-loop guidance did not name AgriGuard `run_browser_smoke_suite.py`, strict/skipped evidence classes, child `child_status`, guarded handoff scripts, or `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.
- Variant: add AgriGuard launch-browser and guarded-handoff guidance to the skill reference, then make the validator and tests enforce those terms.
- Primary KPI: skill validator remains `ok=true` while enforcing AgriGuard launch terms.
- Guardrails: focused skill tests pass, workspace smoke passes, and no unrelated dirty worktree paths are staged.

## Variant Evidence

Implemented:

- Added AgriGuard launch section to `references/workspace-loop.md`.
- Documented strict launch browser gate:
  - default `run_browser_smoke_suite.py`
  - `evidence_class`
  - `launch_gate_enforced`
  - `launch_precheck_blocked`
  - `ui_click_coverage_only`
  - child `child_status`
- Documented optional unavailable browser path via `--include-unavailable-check`.
- Documented guarded launch handoff helpers:
  - `render_guarded_launch_handoff.py`
  - `consume_guarded_launch_handoff.py`
  - `validate_guarded_launch_handoff.py`
- Documented that stale Docker backend replacement must stay blocked until the configured outside-repo `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` exists and strict preflight passes.
- Extended `validate_skill.py` and `test_auto_research_karpathy_skill.py` to pin the new AgriGuard launch terms.

## Verification Commands

- `python -m py_compile .agents\skills\auto-research-karpathy\scripts\validate_skill.py tests\test_auto_research_karpathy_skill.py`
  - Result: pass
- `python .agents\skills\auto-research-karpathy\scripts\validate_skill.py`
  - Result: `ok=true`
- `python -m pytest tests\test_auto_research_karpathy_skill.py -q`
  - Result: 5 passed
- `$env:WORKSPACE_SMOKE_CHECK_TIMEOUT_SECONDS='600'; python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-auto-research-skill-agriguard-launch-loop.json`
  - Result: `status=complete`, passed=9, failed=0, total=9
- `python ops\scripts\github_modernization_radar.py --refresh-latest-commits --json-out var\github-modernization-radar-auto-research-2026-07-07-skill-agriguard-launch-loop.json --markdown-out docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AUTO_RESEARCH_SKILL_AGRIGUARD_LAUNCH_LOOP_2026-07-07.md`
  - Result: valid, 8 sources, adopted=8

## Decision

Adopted. The AutoResearch skill now preserves the AgriGuard launch-browser and guarded-handoff contract for future self-improvement cycles.

## Next Cycle

Continue product hardening from the current runtime truth: strict AgriGuard launch remains blocked by stale backend/proxy runtime and missing outside-repo Firebase Admin credentials, while local source tests and browser child-evidence contracts are green.
