# Auto Research Loop - AgriGuard Evidence Validation Blocker Classes

Date: 2026-07-05

## Objective

Close the operator-packet evidence metadata gap in guarded launch outputs:
`guarded_launch_evidence.validation.status` and
`guarded_launch_evidence.markdown_table_validation.status` had no explicit
`blocker_class`.

## Source Baseline

- Veritas autoresearch source refreshed with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- HEAD/main resolved to `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## Change

- Added `blocker_class` to guarded-launch evidence output validation.
- Added `blocker_class` to guarded-launch Markdown evidence-table validation.
- Classified passing validations as `ready`.
- Classified failed evidence output validation as
  `guarded_launch_evidence_blocked`.
- Classified failed Markdown table validation as
  `guarded_launch_markdown_table_blocked`.
- Mirrored both blocker classes through the guarded handoff packet validation,
  handoff consumer view, artifact index JSON, and Markdown summaries.

## Evidence

Focused evidence, handoff, consumer, and artifact-index suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py -q
```

Result: `41 passed`.

Launch contract suite:

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_launch_compose_script.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_summarize_launch_readiness.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -q
```

Result: `165 passed`.

Real guarded wrapper evidence:

```powershell
$prefix = 'agriguard-evidence-validation-blocker-classes'
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix $prefix --emit-handoff --status-json-out "var\$prefix-status.json" *> "var\$prefix-wrapper.log"
```

Result: exit code `1`, expected fail-closed state due to the missing Firebase
Admin service-account file.

Regenerated artifact proof:

```json
{
  "consumerEvidenceBlockerClass": "ready",
  "consumerMarkdownBlockerClass": "ready",
  "handoffEvidenceBlockerClass": "ready",
  "handoffMarkdownBlockerClass": "ready",
  "indexConsumerEvidenceBlockerClass": "ready",
  "indexConsumerMarkdownBlockerClass": "ready",
  "markdownEvidenceClassStatus": "pass",
  "markdownTableClassStatus": "pass",
  "operatorEvidenceBlockerClass": "ready",
  "operatorEvidenceStatus": "pass",
  "operatorMarkdownBlockerClass": "ready",
  "operatorMarkdownStatus": "pass"
}
```

Handoff validation:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-evidence-validation-blocker-classes-handoff.json --json-out var\agriguard-evidence-validation-blocker-classes-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

Workspace gates:

```powershell
python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-evidence-validation-blocker-classes.json
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-evidence-validation-blocker-classes.json
python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-evidence-validation-blocker-classes.json --output-dir var\agriguard-browser-smoke-suite-evidence-validation-blocker-classes --timeout-ms 30000
```

Results:

- Workspace smoke: `9/9` passed; elapsed `3m02s`.
- AgriGuard smoke: `5/5` passed; elapsed `5m56s`.
- Browser smoke: `6/6` flows, `135/135` checks, `18/18` screenshot artifacts passed.

## Remaining External Blocker

Strict launch remains externally blocked until the operator supplies a real
outside-repo Firebase Admin service-account JSON for
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` and the remaining production operator
values.
