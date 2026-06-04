# AutoResearch External Credential Handoff Drift Guard

## Decision

Adopted a handoff drift guard so checked-in credential handoff artifacts cannot
silently fall behind `ops/references/external_credential_boundaries.json`.

## Adopted Variant

- `ops/scripts/external_credential_handoff.py` now supports:
  - `--check-json`
  - `--check-markdown`
  - `--check-env-template`
- Check mode builds a deterministic template handoff with env values ignored,
  compares checked-in JSON/Markdown/env-template artifacts, and ignores only
  generated timestamps.
- `ops/hooks/pre-push` now runs the check before runtime smoke probes.

## Verification

- `python ops\scripts\external_credential_handoff.py --check-json docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --check-markdown docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --check-env-template docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`
  - external credential handoff check valid
  - `5` boundaries
  - `missing_required_env=5`
- Focused handoff/boundary/completion tests include stale Markdown rejection and
  checked-in artifact sync:
  - `21 passed`
- Pre-push-equivalent pytest suite:
  - `99 passed`
- `python -m py_compile ops\scripts\external_credential_handoff.py ops\scripts\external_credential_boundary_audit.py ops\scripts\autoresearch_completion_audit.py`
  - passed
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_HANDOFF_DRIFT_GUARD_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_EXTERNAL_CREDENTIAL_HANDOFF_DRIFT_GUARD_2026-06-05.md`
  - valid `23` criteria
  - `global_objective_complete=false`

## Remaining Blocker

This is a drift-prevention guard only. It does not provide Canva, Telegram,
OTLP collector, GitHub, or hosted-agent credentials, and the global launch
objective remains `global_objective_complete=false`.
