# AutoResearch Loop - DeSci Launch Click Suite

Date: 2026-07-04
App: apps/desci-platform
Branch: feat/shared-llm-modernization-2026-06-19

## Objective

Move the DeSci product closer to launch by making the real browser-click release path repeatable as a first-class smoke preset.

## Scope and Owned Paths

- `apps/desci-platform/scripts/browser_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`

Frontend source files were intentionally not edited because the current worktree already contains many unrelated DeSci frontend changes.

## External Sources Checked

- Playwright trace viewer: traces are useful for debugging CI failures and include actions, DOM snapshots, console logs, and network requests.
- Playwright screenshots: page and full-page screenshots are supported for visual evidence when needed.
- Uninen/devserver-mcp: combines dev server control and Playwright-style browser automation for LLM-assisted workflows.
- karpathy/autoresearch: reinforces iterating on versioned "research org code" with measurable feedback loops.
- Veritas-7/autoresearch-skill-system: source-backed self-improvement should use A/B checks, durable archives, explicit staging, commit/push gates, and stop controls.
- lastmile-ai/mcp-eval: supports real environment evaluation over mock-only assertions for tool and agent workflows.

Latest observed source commits:

- `karpathy/autoresearch`: `228791fb499afffb54b46200aca536f79142f117`
- `lastmile-ai/mcp-eval`: `7c0f4d1072d0deb6a36a178312c83023cdd96b69`
- `Veritas-7/autoresearch-skill-system`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

Radar evidence:

- `var/github-modernization-radar-auto-research-2026-07-04.json`
- `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04.md`

## A/B Hypothesis

- A: Keep using repeated `--only-check` invocations for release-critical browser clicks.
- B: Add a reusable `--launch-click-suite` preset that selects the release-critical public CTA, dashboard, pricing, upload, and asset action checks and records a suite-level JSON summary.

Decision: Adopt B. It improves launch verification ergonomics without changing UI code and without weakening any existing browser smoke check.

## Implementation

- Added `LAUNCH_CLICK_SUITE_CHECKS`.
- Added `--launch-click-suite`, requiring `--expect-dev-auth` because the suite covers authenticated dashboard, checkout, upload, and asset paths.
- Reused the existing check registry instead of adding duplicate Playwright logic.
- Added `launch_click_suite` and `launch_click_suite_report` to JSON evidence when the preset is used.
- Added tests for argument parsing, dev-auth requirement, selected check names, and JSON summary.

## Verification

- `python -m py_compile apps/desci-platform/scripts/browser_smoke.py` -> passed.
- `python -m pytest backend/tests/test_browser_smoke.py -q` -> 42 passed.
- `python -m pytest backend/tests/test_browser_smoke.py backend/tests/test_deploy_readiness.py backend/tests/test_product_smoke.py -q` -> 97 passed.
- `python scripts/browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --timeout 15 --json-out var/browser-smoke-launch-click-suite-2026-07-04.json --trace-on-failure-dir var/traces/launch-click-suite-2026-07-04` -> 9/9 launch click checks passed.
- `python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-launch-click-suite-2026-07-04.json` -> 8/8 passed.

Observed launch-click suite:

- expected: 9
- executed: 9
- passed: 9
- failed: 0

## Current Launch State

The local click-path evidence is stronger, but production launch remains blocked by external provider configuration already captured in the release handoff:

- Railway runtime secrets and managed services.
- Vercel frontend environment variables.
- GitHub `GITLEAKS_LICENSE` secret.

Next cycle should either add provider-specific apply/check commands for those external blockers or continue expanding high-risk browser click presets around wallet, governance, and BioLinker flows.
