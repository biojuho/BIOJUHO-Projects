# AutoResearch Hook Install Sync Guard - 2026-06-05

## Objective

Prevent a stale installed Git hook from silently diverging from the tracked
`ops/hooks/pre-push` hook during repeated AutoResearch commit/push loops.

## A/B Contract

- Baseline: push can fail late when the common hook directory contains an older
  `pre-push` file. This was observed when the installed hook referenced the
  absent `tests/test_autoresearch_objective_coverage.py` even though the
  tracked hook did not.
- Variant: add `python ops/hooks/install_hooks.py --check` to the start of the
  tracked pre-push hook and add an installer check mode that compares installed
  hooks against LF-normalized tracked hook content. The installer now also
  honors configured `core.hooksPath`, allowing a worktree-local hook path to
  avoid shared common-hook drift across linked worktrees.
- Primary KPI: `python ops\hooks\install_hooks.py --check` fails before
  reinstall when the common hook is stale and passes after
  `python ops\hooks\install_hooks.py`.
- Guardrails: pre-push hook tests, completion-audit tests, script compile, and
  completion audit must pass.
- Decision: adopted. The guard catches tracked-vs-installed hook drift before
  the smoke suite runs, while preserving the existing LF-normalized install
  behavior.

## Changed Paths

- `ops/hooks/install_hooks.py`
- `ops/hooks/pre-push`
- `tests/test_pre_push_hook.py`
- `ops/references/autoresearch_completion_contract.json`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_HOOK_INSTALL_SYNC_GUARD_2026-06-05.json`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_HOOK_INSTALL_SYNC_GUARD_2026-06-05.md`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json`
- `docs/reports/2026-06/AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
- `docs/reports/2026-06/AUTO_RESEARCH_REMAINING_GAP_AUDIT_2026-06-04.md`
- `next-actions.md`

## Verification

- `python -m pytest tests\test_pre_push_hook.py -q -p no:cacheprovider`
  - `3` passed
- `python -m py_compile ops\hooks\install_hooks.py`
  - passed
- `python ops\hooks\install_hooks.py --check`
  - before reinstall: failed with stale installed hook
- `python ops\hooks\install_hooks.py`
  - installed `pre-push` into `D:\AI project\.git\hooks\pre-push`
- `python ops\hooks\install_hooks.py --check`
  - after reinstall: current
- `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=ops/hooks python ops\hooks\install_hooks.py --check`
  - current for the tracked worktree hook path
- Installed hook line endings:
  - `crlf_pairs=0`
- `python -m pytest tests\test_pre_push_hook.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q -p no:cacheprovider`
  - `20` passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_HOOK_INSTALL_SYNC_GUARD_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_HOOK_INSTALL_SYNC_GUARD_2026-06-05.md`
  - valid
  - `25` criteria
  - `cycle_evidence_ready=true`
  - `global_objective_complete=false`

## Next Cycle

Continue improving launch readiness with deterministic evidence. Credentialed
external execution remains blocked until the required operator-owned
environment values are supplied.
