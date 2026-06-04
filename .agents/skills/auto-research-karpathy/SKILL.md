---
name: AutoResearch Karpathy Loop
description: This skill should be used when the user asks to "AutoResearch", "오토리서치", "Karpathy concept", "self-improving skill", "continuous A/B testing", "find related GitHub projects", "launch-ready product hardening", or asks for autonomous research, app-click testing, commit, and push loops.
version: 0.1.0
---

# AutoResearch Karpathy Loop

## Purpose

Run source-backed, product-focused improvement loops for a workspace. Treat the
agent as a software director: translate natural-language intent into scoped
experiments, collect current external evidence, implement only the strongest
candidate, verify the real product path, and preserve the learning as repo-owned
evidence.

Use this skill for launch hardening, self-improvement cycles, GitHub comparison
work, app-click QA, and A/B testing requests. Prefer durable local automation
over chat-only plans.

## Operating Contract

Convert broad "keep going until stopped" requests into resumable cycles. Keep
working while the current session can make concrete progress. Stop only for an
explicit user stop request, a higher-priority safety rule, an unavailable
credential or external service that blocks the next required proof, or a
workspace state that makes safe ownership impossible. Record the next cycle so
another run can continue without restarting discovery.

Preserve unrelated worktree changes. Stage, commit, or push only files owned by
the current cycle. Never hide failing evidence behind a successful summary. Do
not treat a passing unit test, manifest, or validator as completion unless it
covers the explicit objective.

Prefer "Karpathy-style" partial autonomy: let natural-language goals steer the
system, but keep deterministic checks, human-readable evidence, and explicit
adoption rules in the loop. Use agents, tools, browser automation, and GitHub
research as accelerators, not replacements for verification.

## Workflow

### 1. Build the Objective Contract

Restate the user request as concrete deliverables:

- product or app surfaces to harden
- GitHub or external projects to compare against
- A/B hypotheses to test
- files, commands, reports, and commit/push expectations
- manual or credential-gated steps that cannot be completed locally

Create a prompt-to-artifact checklist before claiming completion. Map each
requirement to a file path, command output, test result, browser evidence,
source citation, report, commit, or explicit blocker.

### 2. Refresh External and GitHub Evidence

Browse or search live sources when the request mentions latest, current,
GitHub, external research, or product recommendations. Prefer primary sources:
official GitHub repositories, official docs, release notes, papers, or vendor
docs.

For this workspace, start with the local modernization radar:

```powershell
python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research.json --markdown-out docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md
```

If the manifest is stale or the product scope changes, update the manifest only
after verifying each source is a GitHub HTTPS URL and each local evidence path
exists.

### 3. Choose the Next High-Value Experiment

Select one experiment per cycle unless independent work can be safely
parallelized. Rank candidates by expected product impact, verification clarity,
blast radius, and reversibility.

Use a strict A/B contract:

- baseline: current behavior or report
- variant: specific change or implementation candidate
- primary KPI: one measurable product metric
- secondary checks: quality, security, latency, cost, accessibility, or
  maintainability
- decision rule: adopt only if the variant beats the baseline and no guardrail
  regresses
- evidence: commands, artifacts, screenshots, traces, or measured outputs

Reject a variant when it improves a proxy metric but degrades the real product
path.

### 4. Implement with Scoped Ownership

Inspect the relevant code before editing. Use the workspace's existing helpers,
tests, design system, smoke runners, and scripts. Keep the patch as narrow as
the experiment allows.

For frontend or app work, run the app through the actual user path. Start the
local dev server when required. Use Playwright, browser smoke scripts, or
computer-use tools to click primary flows, capture errors, inspect screenshots,
and confirm that UI text does not overlap. Prefer existing scripts such as
`apps/desci-platform/scripts/browser_smoke.py` and the dashboard/app smoke
paths before inventing a new browser runner.

### 5. Verify Before Adopting

Run targeted tests first, then the smallest canonical smoke scope that covers
the change:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope desci --json-out var/workspace-smoke-desci-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope mcp --json-out var/workspace-smoke-mcp-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope getdaytrends --json-out var/workspace-smoke-getdaytrends-auto-research.json
python ops/scripts/run_workspace_smoke.py --scope cie --json-out var/workspace-smoke-cie-auto-research.json
```

Use the release approval overlay only when preparing an actual release
candidate. Do not substitute it for product smoke or browser evidence.

### 6. Record, Commit, and Push Safely

Write cycle evidence to `docs/reports/<year-month>/` or the project's own
`QC_LOG.md`/`devlog.md` when the project already uses those surfaces. Include:

- objective and scope
- external sources checked
- A/B hypothesis and decision rule
- changed paths
- verification commands and results
- accepted variant or rejected candidates
- next cycle recommendation

Commit and push only after verification is sufficient for the owned paths. Stage
explicit files, review the staged diff, run `git diff --cached --check`, then
commit. Push the current branch only when the user requested push and the remote
is configured. If authentication, branch policy, or remote state blocks the
push, record the exact blocker and leave the local commit intact.

## Adoption Rules

Adopt a variant only when all of these are true:

- the primary KPI improves or the blocking defect is fixed
- no canonical guardrail relevant to the changed paths regresses
- source-backed research supports the direction or shows no better local fit
- browser/app smoke confirms the real workflow when the change is user-facing
- repo evidence records the result

When evidence is weak, mark the result as a candidate, not a launch-ready
improvement.

## Additional Resources

- `references/source-backed-patterns.md` - current external patterns from
  Karpathy-style Software 3.0, MCP eval, agent workflow, and dev-server systems.
- `references/workspace-loop.md` - workspace-specific commands, project
  surfaces, and commit/push procedure.
- `examples/self-improvement-cycle.yaml` - machine-readable cycle template.
- `scripts/validate_skill.py` - deterministic validator for this skill package.
