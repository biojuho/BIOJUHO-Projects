# AutoResearch Loop: AgriGuard Status Artifact Index Markdown

Date: 2026-07-05

## Objective

Expose the generated artifact-index Markdown path in compact guarded-launch
status JSON.

## Source Evidence

- Veritas AutoResearch source checked with `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`.
- Latest observed `main` commit: `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local radar evidence remains `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md` with 8 adopted source-backed patterns.

## A/B Contract

Baseline: compact status `artifacts` exposed `artifact_index_json` but not the
generated `artifact_index_markdown` path, even though the wrapper already knew
the exact Markdown output location.

Variant: pass `artifact_index_markdown` into the compact status builder and
allow that key in the guarded-launch handoff schema.

Primary KPI: a real guarded-wrapper run leaves compact status with
`artifacts.artifact_index_markdown` pointing to an existing Markdown file, while
handoff schema validation still passes.

Decision rule: adopt only if focused wrapper/schema tests, expanded
launch-readiness tests, real guarded wrapper evidence, workspace smoke, browser
smoke, and AgriGuard smoke pass while strict launch remains fail-closed on the
missing external Firebase service-account file.

Decision: adopted.

## Owned Paths

- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
- `docs/reports/2026-07/AUTO_RESEARCH_LOOP_2026-07-05_AGRIGUARD_STATUS_ARTIFACT_INDEX_MARKDOWN.md`

## Variant Evidence

- `_build_status_view` now accepts and emits `artifact_index_markdown`.
- Every status-view call in `run_guarded_launch.py` passes the exact artifact-index Markdown path.
- Handoff schema allows `status_view.artifacts.artifact_index_markdown`.

Real guarded wrapper:

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --app-root apps/AgriGuard --env-file var\agriguard-launch-operator.missing-firebase.env --output-dir var --output-prefix agriguard-status-artifact-index-markdown --emit-handoff --status-json-out var\agriguard-status-artifact-index-markdown-status.json
```

Result: exited `1` as expected because strict launch remains blocked by the
missing real Firebase Admin service-account JSON.

JSON proof:

```json
{"blockerErrors":["AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist."],"statusBlocker":"preflight_blocked","artifactIndexJson":"D:\\AI project\\var\\agriguard-status-artifact-index-markdown-artifact-index.json","artifactIndexMarkdown":"D:\\AI project\\var\\agriguard-status-artifact-index-markdown-artifact-index.md","artifactIndexMarkdownExists":true,"handoffJson":"D:\\AI project\\var\\agriguard-status-artifact-index-markdown-handoff.json","artifactIndexStatus":"pass"}
```

Schema proof:

```powershell
python apps/AgriGuard/scripts/validate_guarded_launch_handoff.py var\agriguard-status-artifact-index-markdown-handoff.json --json-out var\agriguard-status-artifact-index-markdown-handoff.validation.rerun.json
```

Result: `AgriGuard guarded-launch handoff valid`.

## Verification

- `python -m py_compile apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` passed.
- `python -m ruff check apps/AgriGuard/scripts/run_guarded_launch.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py` passed.
- `python -m json.tool apps/AgriGuard/scripts/guarded_launch_handoff.schema.json` passed.
- Focused wrapper and handoff validation tests passed: 26 tests.
- Expanded launch-readiness suite passed: 164 tests.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-status-artifact-index-markdown.json` passed: 9/9.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-status-artifact-index-markdown.json --output-dir var\agriguard-browser-smoke-suite-status-artifact-index-markdown --timeout-ms 30000` passed: 6/6 suites, 135/135 checks, 18/18 screenshot artifacts.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-status-artifact-index-markdown.json` passed: 5/5.

## External Blocker

Compact status artifact-index Markdown exposure is locally green. Full strict
launch remains blocked until an operator supplies a real outside-repo Firebase
Admin service-account JSON for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`.

## Next Cycle

Continue checking generated artifact path indexes for missing operator-facing
references.
