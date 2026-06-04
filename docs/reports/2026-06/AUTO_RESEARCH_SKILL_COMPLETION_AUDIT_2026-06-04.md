# AutoResearch: Skill Completion Audit Gate

Date: 2026-06-04

## Objective

Harden the local AutoResearch skill so self-improvement cycles do not treat
tests, manifests, pushed commits, or partial evidence as completion by
themselves.

## A/B Contract

- Baseline: the skill required a prompt-to-artifact checklist, but the skill
  validator and example cycle did not enforce a completion-audit section.
- Variant: require completion-audit language in `SKILL.md`, add
  `completion_audit` to the example cycle, and make `validate_skill.py` fail if
  the audit terms or example keys are removed.
- KPI: the skill validator remains green while enforcing completion-audit
  coverage.

## Adopted Variant

The variant was adopted.

Changed paths:

- `.agents/skills/auto-research-karpathy/SKILL.md`
- `.agents/skills/auto-research-karpathy/examples/self-improvement-cycle.yaml`
- `.agents/skills/auto-research-karpathy/references/workspace-loop.md`
- `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`

## Verification

- `python .agents\skills\auto-research-karpathy\scripts\validate_skill.py`
  -> `ok=true`
- `python -m py_compile .agents\skills\auto-research-karpathy\scripts\validate_skill.py`
  -> PASS
- Post-rebase focused check for the remote DeSci auth/CORS slice:
  `python -m pytest apps\desci-platform\backend\tests\test_api_endpoints.py -q -p no:cacheprovider`
  -> `21 passed`

Validator now checks:

- `completion audit`
- `success criteria`
- `uncovered requirements`
- `proxy-verified`
- `completion_audit:`
- `success_criteria:`
- `evidence:`
- `uncovered_requirements:`
- `continue_if_missing:`

## Decision

Future AutoResearch cycles must distinguish a completed cycle from the whole
open-ended objective. If any requirement is missing, uncovered, or only
proxy-verified, the loop should record the gap and continue rather than claim
global completion.
