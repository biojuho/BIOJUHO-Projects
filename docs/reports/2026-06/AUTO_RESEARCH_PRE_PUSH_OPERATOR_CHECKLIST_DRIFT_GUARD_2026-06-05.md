# AutoResearch Pre-Push Operator Checklist Drift Guard

## Decision

Extended the real `ops/hooks/pre-push` external credential handoff check so it
directly validates the generated operator checklist artifacts, not only the base
handoff JSON, Markdown, and env template.

## Adopted Variant

- Variant A: rely on `tests/test_external_credential_handoff.py` to catch
  checklist drift during the pre-push pytest bundle.
- Variant B: add `--check-operator-checklist-json` and
  `--check-operator-checklist-markdown` to the direct hook command as a second
  explicit guard. Adopted because operator checklist drift is completion
  critical and the direct hook error message now names the exact remediation
  command.

## Current Result

- `ops/hooks/pre-push` validates:
  - `EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json`
  - `EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md`
  - `EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example`
  - `EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json`
  - `EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md`
- `tests/test_pre_push_hook.py` now asserts both operator checklist flags and
  paths.
- This protects operator checklist drift before a push can complete.
- `global_objective_complete=false`

## Verification

- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - valid `37` criteria
  - `global_objective_complete=false`
- `python ops\hooks\install_hooks.py`
  - installed `pre-push` to `D:\AI project\.git\hooks\pre-push`
- `python ops\hooks\install_hooks.py --check`
  - hook is current
- `python -m pytest tests\test_pre_push_hook.py tests\test_external_credential_handoff.py tests\test_autoresearch_completion_audit.py -q --tb=line`
  - `27 passed`
- `python ops\scripts\external_credential_handoff.py --registry ops\references\external_credential_boundaries.json --check-json docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.json --check-markdown docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.md --check-env-template docs\reports\2026-06\EXTERNAL_CREDENTIAL_HANDOFF_2026-06-05.env.example --check-operator-checklist-json docs\reports\2026-06\EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.json --check-operator-checklist-markdown docs\reports\2026-06\EXTERNAL_CREDENTIAL_OPERATOR_CHECKLIST_2026-06-05.md`
  - valid `5` boundaries with `status=operator_action_required`
- `python -m pytest tests\test_workspace_smoke.py tests\test_pre_push_hook.py tests\test_external_credential_handoff.py tests\test_external_credential_live_verify.py tests\test_telegram_notification_live_verify.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q --tb=line`
  - `79 passed`
- `python -m py_compile ops\scripts\external_credential_handoff.py ops\scripts\autoresearch_completion_audit.py`
  - passed

## Remaining Blocker

The guard only protects generated artifact freshness. It does not supply Canva,
GitHub, Telegram, OTLP collector, or hosted runtime credentials.
