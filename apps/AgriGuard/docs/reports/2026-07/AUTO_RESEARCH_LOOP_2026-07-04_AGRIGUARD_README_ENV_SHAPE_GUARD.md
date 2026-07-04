# AutoResearch Loop 2026-07-04 AgriGuard README Env Shape Guard

## Objective

Document the validator-first operator retry sequence in `apps/AgriGuard/README.md` so filled env files are checked before strict preflight and compose launch.

## Scope And Owned Paths

- `apps/AgriGuard/README.md`
- `apps/AgriGuard/docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-04_AGRIGUARD_README_ENV_SHAPE_GUARD.md`

`README.md` already had unrelated unstaged edits. Only the new `Operator env retry flow` hunk is staged for this cycle.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` observed HEAD: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Prior cycle radar basis: `var/github-modernization-radar-auto-research-2026-07-04-template-validation.json`, `8 sources, adopted=8, partially_adopted=0, watch=0`

## A/B Hypothesis

- Baseline: README documented strict preflight and compose launch, but not the validator-first retry order for generated operator env templates.
- Variant: add an `Operator env retry flow` section with the shape validator command, the guarded compose command, and the boundary that shape pass does not replace strict preflight.
- Primary KPI: operator can discover the correct command order from README without reading reports or code.
- Guardrails: do not stage unrelated README edits; keep launch code unchanged.

## Variant Evidence

- README command discovery:
  - `rg -n "Operator env retry flow|validate-env-file-shape|validate_launch_env_template.py" apps/AgriGuard/README.md`
  - Result: section and both validator/guarded compose commands found.
- Fast launch-adjacent tests:
  - `python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py -q`
  - Result: `18 passed in 0.66s`
- Staged diff guard:
  - `git diff --cached --check`
  - Result: pass.

## Decision

Adopt the README variant. The operator docs now match the implemented fail-closed sequence: fill env file, run shape validation, then run guarded compose launch.

## Remaining Launch Blocker

Real compose/browser launch remains externally blocked until an operator supplies the production Firebase service-account JSON and production-strength secret, pepper, URL, origins, and database credentials.

## Next Cycle

Add a compact launch-readiness summary command that reads the latest launch report, env validation report, and operator packet report and prints the current blocker class without exposing values.
