# AutoResearch Karpathy Skill Cycle - 2026-06-04

## Objective

Create a launch-hardening AutoResearch skill that applies a Karpathy-style
Software 3.0 loop: current external research, GitHub-related project discovery,
scoped implementation, A/B testing, real app/browser validation, and safe
commit/push handling.

## Prompt-to-Artifact Checklist

| Requirement | Evidence | Status |
| --- | --- | --- |
| Create an AutoResearch/Karpathy concept skill | `.agents/skills/auto-research-karpathy/SKILL.md` | PASS |
| Include trigger support for `AutoResearch` and `오토리서치` | `scripts/validate_skill.py` trigger checks | PASS |
| Make the skill self-improving through repeated A/B cycles | `examples/self-improvement-cycle.yaml`, `SKILL.md` adoption rules | PASS |
| Find and use related GitHub projects | `references/source-backed-patterns.md`, `ops/scripts/github_modernization_radar.py` | PASS |
| Connect to local product gates and smoke evidence | `references/workspace-loop.md` canonical smoke matrix | PASS |
| Include app-click/browser validation workflow | `SKILL.md`, `references/workspace-loop.md`, Playwright dashboard pass below | PASS |
| Include commit/push guardrails | `SKILL.md`, `references/workspace-loop.md` explicit stage-only flow | PASS |
| Validate the skill package | `python .agents\skills\auto-research-karpathy\scripts\validate_skill.py` -> `ok: true` | PASS |
| Regression-cover the skill | `python -m pytest tests\test_auto_research_karpathy_skill.py -q -p no:cacheprovider` -> `4 passed` | PASS |

## External and GitHub Sources

Live source pass used:

- Andrej Karpathy, "Software Is Changing (Again)".
- `PrefectHQ/fastmcp`.
- `lastmile-ai/mcp-eval`.
- `evalstate/fast-agent`.
- `Uninen/devserver-mcp`.

Local GitHub modernization radar was re-run:

```powershell
python ops\scripts\github_modernization_radar.py --json-out var\github-modernization-radar-auto-research.json --markdown-out docs\reports\2026-06\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md
```

Result: `6 sources`, `adopted=1`, `partially_adopted=4`, `watch=1`.

## App Click Evidence

Dashboard was checked through the actual browser path:

1. Started dashboard Vite dev server at `http://127.0.0.1:5173`.
2. Initial Vite-only load showed `502` API proxy errors because the Python API
   server was not running.
3. Started `apps/dashboard/api.py --port 8080`.
4. Verified `GET http://127.0.0.1:8080/api/overview` returned live project data.
5. Opened a fresh dashboard tab through Playwright.
6. Confirmed no fresh console errors beyond the React DevTools development
   info line.
7. Clicked the theme toggle and data refresh buttons through accessible names.
8. Saved loaded accessibility evidence to `dashboard-loaded-5173.md`.

Important finding: Korean text was not broken in the browser. The apparent
mojibake was caused by reading UTF-8 snapshot files through PowerShell without
`-Encoding UTF8`.

## Files Added

- `.agents/skills/auto-research-karpathy/SKILL.md`
- `.agents/skills/auto-research-karpathy/references/source-backed-patterns.md`
- `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
- `.agents/skills/auto-research-karpathy/examples/self-improvement-cycle.yaml`
- `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
- `tests/test_auto_research_karpathy_skill.py`
- `docs/reports/2026-06/AUTO_RESEARCH_KARPATHY_SKILL_2026-06-04.md`

## Remaining Scope

This cycle does not claim the entire broad product-launch objective is complete.
Remaining AutoResearch cycles should continue with:

- DeSci frontend/browser smoke click pass.
- AgriGuard frontend/QR flow click pass.
- Canva widget preview click pass.
- A/B candidate execution for one launch-critical workflow.
- Optional commit/push only after targeted staging and diff checks.
