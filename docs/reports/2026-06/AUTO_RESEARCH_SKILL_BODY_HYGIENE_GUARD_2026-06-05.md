# AutoResearch Skill Body Hygiene Guard

- Date: 2026-06-05
- Source repo: `microsoft/agent-framework`
- Source commit: `bb9ed63a347b3e437106b27ff7547bd388fd5bbe`
- Source signal: `.NET: Restructure skill script schemas XML and remove resources from body (#6343)`
- Source URL: https://github.com/microsoft/agent-framework/commit/bb9ed63a347b3e437106b27ff7547bd388fd5bbe
- Local status: adopted
- Global objective complete: `false`

## Source Signal

Microsoft Agent Framework split skill script parameter schemas into a dedicated `script_schemas` body section and clarified that resources are not automatically included in the skill body; resources and scripts should be referenced for discovery instead of embedded wholesale.

## A/B Contract

- A: Keep the AutoResearch skill validator focused on required files, trigger terms, and destructive-command checks while allowing future `SKILL.md` edits to embed XML-style script/resource body blocks.
- B: Add a body-hygiene validator rule that keeps scripts and resources external: `SKILL.md` can reference `scripts/`, `references/`, and `examples/`, but cannot embed `<scripts>...</scripts>` or `<resources>...</resources>` blocks.

Decision: adopted B. It preserves the existing skill package layout, keeps large operational assets outside the prompt body, and gives exact validator errors if future edits reintroduce embedded script/resource body content.

## Local Changes

- `.agents/skills/auto-research-karpathy/scripts/validate_skill.py`
  - Validates the requested `skill_dir` instead of always reading the default global `SKILL_PATH`.
  - Adds `FORBIDDEN_BODY_BLOCKS` for embedded script and resource body blocks.
  - Emits `body_hygiene:*` checks and actionable errors.
- `tests/test_auto_research_karpathy_skill.py`
  - Adds a regression that copies the skill package, injects `<scripts>` and `<resources>` body blocks, and expects validation to fail.

## Verification

- `python -m pytest tests\test_auto_research_karpathy_skill.py -q` -> `5 passed`
- `python .agents\skills\auto-research-karpathy\scripts\validate_skill.py` -> `ok=true`
- `python -m py_compile .agents\skills\auto-research-karpathy\scripts\validate_skill.py` -> passed
- `python -m pytest tests\test_auto_research_karpathy_skill.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q` -> `24 passed`
- `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-autoresearch-skill-body-hygiene-guard-2026-06-05.json` -> `6/6 passed`

## Completion State

- `global_objective_complete=false`
