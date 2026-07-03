# Workspace Quality Gate

This document defines the deterministic quality gate for the active workspace.

## Active scope

Included units:

- `apps/desci-platform`
- `apps/AgriGuard`
- `apps/dashboard`
- `automation/DailyNews`
- `automation/getdaytrends`
- `automation/content-intelligence`
- `mcp/notebooklm-mcp`
- `mcp/github-mcp`
- `mcp/canva-mcp`
- `mcp/desci-research-mcp`
- `mcp/telegram-mcp`
- DailyNews X ops suite, browser-click smoke, and action-log roundtrip smoke
- `packages/shared`

Excluded by default:

- `archive/**`
- `var/**`
- inactive legacy projects

## Root commands

Canonical commands:

```bash
python ops/scripts/run_workspace_smoke.py --scope all
python ops/scripts/run_workspace_smoke.py --scope workspace
python ops/scripts/run_workspace_smoke.py --scope desci
python ops/scripts/run_workspace_smoke.py --scope agriguard
python ops/scripts/run_workspace_smoke.py --scope mcp
python ops/scripts/run_workspace_smoke.py --scope dailynews
python ops/scripts/run_workspace_smoke.py --scope getdaytrends
python ops/scripts/run_workspace_smoke.py --scope cie
python ops/scripts/run_workspace_smoke.py --scope all --json-out smoke-all.json
```

`--scope dailynews` is a selection alias for the DailyNews checks that are still
reported under the historical `mcp` result scope for report compatibility.

For live browser QA and local dev-server lifecycle evidence, use
`docs/guides/dev-server-control.md`.

When `--json-out` is provided, the runner refreshes the JSON report after each
completed check. Long `--scope all` runs therefore leave partial evidence even
if the interactive shell times out before the final summary.
Each refresh writes through a same-directory temporary file and atomically
replaces the report, so an interrupted write should not corrupt the previous
valid JSON evidence.
AgriGuard smoke selections run a low-disk preflight before the lint/build,
contracts, and backend checks. The preflight checks the workspace drive, Python
temporary directory, npm cache, uv cache, and the `--json-out` parent path when
provided. The default threshold is `256 MiB`, configurable with
`WORKSPACE_SMOKE_MIN_FREE_MB` or `--min-free-mb`; `--skip-disk-preflight` is
only for explicit diagnostics. A preflight failure writes a schema v1 partial
report with an `agriguard disk preflight` result and should be treated as a
local environment blocker rather than a product-code failure.
The QR KPI release evidence driver passes these controls through with
`--smoke-min-free-mb` and `--skip-smoke-disk-preflight`, records
`steps.smoke.command` and `steps.smoke.disk_preflight` in the release-driver
JSON, and must stop before bundle generation when the smoke preflight fails.
The QR KPI release preflight also records `checks.environment` before release
evidence starts. That check reports the system drive, workspace drive, planned
output directory, Python temporary directory, npm cache, uv cache, D-backed
cache environment flags, and inaccessible `.pytest-tmp` entries; an
`environment` failure is a local readiness blocker that operators should clear
before loading the signing key.
Smoke JSON reports use `schema_version: 1`, include `status` as `partial` or
`complete`, and expose summary counts plus per-check `results`. The summary
also carries `expected_external_failures` and `unexpected_failures` arrays so a
raw smoke JSON report can be interpreted without a separate reader-side
classification pass. Each executed check should include nonnegative
`elapsed_ms` timing, and summaries with timed results should include
`elapsed_ms_total` plus `slowest_results`, so operators can distinguish slow
dependency/bootstrap work from stuck checks using the JSON artifact alone.
The smoke CLI's final terminal summary should also print compact elapsed and
slowest-check timing when result timing is available.
Smoke report consumers such as `session_bootstrap.py` and
`generate_context_snapshot.py` must accept both the schema v1 object payload and
legacy array reports, and should scan current `var/workspace-smoke*.json`
evidence as well as legacy `var/smoke/*.json` reports. If the newest candidate
is unreadable, consumers should skip it and report the newest valid smoke
evidence instead of marking the whole workspace snapshot corrupt. The newest
valid selection must be based on file modification time inside the shared
reader, not on filesystem glob order or caller-provided candidate order. The
shared reader is also responsible for collecting current and legacy report
files and ignoring matching directories or other non-file candidates.
Session bootstrap and context snapshot surfaces should prefer canonical
`workspace-smoke-workspace*.json` reports over newer focused app-scope smoke
proofs, falling back to the newest valid focused smoke only when no valid
workspace-scope report exists.
`session_bootstrap.py` keeps the backward-compatible `latest_smoke` display
string and also writes structured `latest_smoke_evidence` metadata for machine
consumers: `status` (`valid`, `corrupt`, or `missing`), `display`, report `path`/`name`, `passed`, `total`, `failed`, `expected_external_failures`, `unexpected_failures`, and the smoke report's own `report_status`.
For timed schema v1 reports, valid evidence should also carry optional
`elapsed_ms_total` and `slowest_results` metadata.
When summary timing exists, the shared display string may add a compact
`elapsed=...; slowest=...` suffix while preserving the leading
`N/N PASS` compatibility shape.
`auto_research_status.py` must preserve the same failure metadata in its
`latest_smoke` object and in getdaytrends `canonical_smoke`, and its Markdown
summary must expose expected external versus unexpected canonical getdaytrends
smoke failures when the canonical smoke is not all-pass.
The complete-goal evidence consistency gate must validate the current
getdaytrends canonical workspace-smoke payload through the shared smoke reader,
not by trusting hand-written summary counters alone. The gate should pass the
current externally blocked state only when the smoke reader reports at least one
expected external failure and no unexpected failures.
Release approval must require the `getdaytrends_canonical_smoke_expected_blocked`
consistency row by name, so older green consistency evidence that predates this
smoke classification check cannot pass final approval.
The release manifest worktree section must include the smoke reader, smoke
runner, session bootstrap/context snapshot consumers, smoke/report tests, and
this quality-gate document whenever these artifacts define the approval
evidence contract.
Release approval must also enforce those smoke evidence contract paths directly
through its required worktree changed-path list, so manually edited or stale
release manifests cannot pass while omitting the smoke reader, runner, tests,
session bootstrap/context snapshot consumers, or quality-gate document that
define the approval evidence contract.
The complete-goal release evidence refresh must expose whether release approval
was generated after the final manifest refresh. If
`generated_after_final_manifest_refresh` is not `true`, the refresh is a local
gate failure rather than an expected external credential block.
The no-credential refresh summary must propagate that release-approval
freshness flag from the child release-evidence report so current blocked-state
operators can inspect one top-level JSON without opening the nested report.
The no-credential refresh must also fail local when the child release-evidence
report is externally blocked but its propagated release-approval freshness flag
is missing or not `true`.
`refresh_complete_goal_release_manifest.py --allow-missing-consistency` is only
valid for the release-evidence driver's pre-consistency bootstrap refreshes:
the first manifest refresh before scan regeneration and the second refresh after
launch secret scans but before `complete_goal_evidence_consistency_check.py`
runs. In that mode, the report must list
`complete-goal-evidence-consistency` under `allowed_missing_sources`, keep it out
of `missing_sources`, and mark the manifest consistency gate as not ok. The
final manifest refresh after evidence consistency must remain strict and must
not use this flag.
The shared reader classifies the known credential-bound
`getdaytrends launch readiness gate` failure as expected external only when the
failed result contains live database boundary evidence such as `live_db_doctor`
plus a masked Supabase `tenant/user` rejection or runtime database fallback
marker. Name-only matches remain unexpected failures. When a schema v1 smoke
summary includes `expected_external_failures` or `unexpected_failures`, the
reader must validate that each field is a list of strings and exactly matches
the classification recomputed from `results[]`.
Legacy array reports remain supported only when every entry is an object with a boolean `ok` field and at least one result; malformed legacy arrays and empty legacy arrays are skipped like corrupt reports.
Consumers should also reject schema v1 reports whose `schema_version` is not
`1` exactly, whose `schema_version` is a boolean, whose `generated_at` is not parseable, whose `status` is missing or outside
`complete`/`partial`, whose `generated_at` is missing a timezone offset, whose top-level `summary` object or `results` array is
missing, whose `summary.total` or `summary.completed` is zero, whose summary counts are inconsistent, whose `status` contradicts remaining check counts, or whose
`results[]` entries are missing required result fields, are not objects with
boolean `ok` values, whose trace fields (`scope`, `name`, `cwd`, `command`) are
empty, whose `scope` is not a known canonical smoke scope, whose
`results[].ok` values contradict their `returncode`, whose optional
`results[].elapsed_ms` is not a nonnegative integer, or whose
`results[].ok` pass/fail counts contradict `summary.passed` or
`summary.failed`, then continue to the newest valid smoke evidence.
When `summary.elapsed_ms_total` or `summary.slowest_results` is present,
consumers should reject reports where those fields do not match the result
`elapsed_ms` values.

Legacy compatibility commands remain available after:

```bash
python bootstrap_legacy_paths.py
python scripts/run_workspace_smoke.py --scope all
```

## Supplemental modernization radar

GitHub-similar system checks stay outside the deterministic default smoke gate
because live repository search is time-sensitive and network-dependent. The
current source-backed modernization radar is captured in a local manifest and
validated against concrete workspace evidence with:

```bash
python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-2026-06-04.json --markdown-out docs/reports/2026-06/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-06-04.md
```

The manifest must map each external repository pattern to existing
repo-relative evidence paths before a trend is treated as locally adopted.
Promote a radar gap into the default gate only after it has a repeatable,
offline check.

## Deterministic gate contents

- `workspace`
  - `tests/test_workspace_regressions.py`
  - `tests/test_workspace_smoke.py`
  - `tests/test_auto_research_status.py`
  - `tests/test_security_gate_contracts.py`
  - `tests/test_release_approval_check.py`
  - `packages/shared/tests`
  - dashboard frontend lint, unit tests, build, bundle budget
- `desci`
  - frontend lint, unit tests, build, bundle budget
  - contracts compile and tests
  - backend smoke pytest
  - release readiness contract pytest for env doctor, deploy readiness, release gate, deployment docs, product/browser smoke, production auth and LLM fallback policy, and worker bootstrap/dispatch behavior
  - operator JSON evidence contract coverage for atomic `--json-out` writers and dry-run artifact validation skip semantics

DeSci release-readiness pytest files:

- `apps/desci-platform/backend/tests/test_deploy_readiness.py`
- `apps/desci-platform/backend/tests/test_env_doctor.py`
- `apps/desci-platform/backend/tests/test_release_gate.py`
- `apps/desci-platform/backend/tests/test_deployment_docs.py`
- `apps/desci-platform/backend/tests/test_product_smoke.py`
- `apps/desci-platform/backend/tests/test_browser_smoke.py`
- `apps/desci-platform/backend/tests/test_llm_fallback_policy.py`
- `apps/desci-platform/backend/tests/test_auth.py`
- `apps/desci-platform/backend/tests/test_worker.py`

- `agriguard`
  - low-disk preflight for workspace, temp, npm cache, uv cache, and JSON output paths
  - frontend lint and build
  - contracts compile and tests
  - backend pytest suite
- `mcp`
  - compile smoke for NotebookLM and GitHub MCP paths
  - `automation/DailyNews/tests/unit` pytest suite
  - DailyNews first-run verifier smoke
  - Canva MCP build
  - DeSci research MCP pytest suite
  - Telegram MCP pytest suite
- `getdaytrends`
  - entrypoint syntax check for `automation/getdaytrends/main.py`
  - python compile smoke
  - `automation/getdaytrends/tests` pytest suite
  - launch readiness gate with `scripts/readiness_check.py --max-scheduler-age-hours 24 --max-cli-smoke-age-hours 24 --fail-on-runtime-fallback --require-live-db`
- `cie`
  - python compile smoke
  - `automation/content-intelligence/tests` pytest suite

## Smoke Check Inventory

The canonical check names emitted by `run_workspace_smoke.py --scope all` are:

- `workspace regression tests`
- `ops agents tests`
- `security contract tests`
- `release approval contract tests`
- `shared package tests`
- `dashboard frontend lint`
- `dashboard frontend tests`
- `dashboard frontend build`
- `dashboard bundle budget`
- `desci frontend lint`
- `desci frontend unit tests`
- `desci frontend build`
- `desci bundle budget`
- `desci contracts compile`
- `desci contracts tests`
- `desci backend smoke`
- `desci release readiness contracts`
- `agriguard frontend lint`
- `agriguard disk preflight` (emitted only as a fail-fast partial result)
- `agriguard frontend build`
- `agriguard contracts compile`
- `agriguard contracts tests`
- `agriguard backend tests`
- `notebooklm compile`
- `github-mcp compile`
- `DailyNews unit tests`
- `DailyNews X ops suite`
- `DailyNews X ops browser smoke`
- `DailyNews X action-log roundtrip smoke`
- `DailyNews first-run verifier smoke`
- `canva-mcp build`
- `desci-research-mcp tests`
- `telegram-mcp tests`
- `getdaytrends entrypoint syntax`
- `getdaytrends compile`
- `getdaytrends tests`
- `getdaytrends subpackage tests`
- `getdaytrends launch readiness gate`
- `getdaytrends Supabase recovery packet`
- `getdaytrends provider auth recovery packet`
- `cie compile`
- `cie tests`

Python compile checks use `ops/scripts/compile_workspace_paths.py`, which prunes these directories before traversal:

- `.agent`
- `.agents`
- `.venv`
- `venv`
- `__pycache__`
- `output`
- `archive`
- `var`
- `.pytest-temp-verify`
- `.pytest-root`
- `.pytest_cache`
- `.smoke-tmp`
- `.mypy_cache`
- `.ruff_cache`
- generated output folders

## Policy

External-service tests stay out of the default PR gate. Keep them manual, scheduled, or separately triggered so standard PRs stay deterministic.
The `getdaytrends launch readiness gate` is an ops/release smoke check: it is expected to fail closed when live Supabase credentials are unavailable or invalid, and should be treated as release evidence rather than a deterministic PR-only unit gate.

## Release Approval Overlay

The deterministic quality gate is a development-health signal. It is not, by itself, a release approval.

Release approval additionally requires:

- a passing deterministic gate for the affected scope,
- a clean worktree or an explicitly reviewed in-progress diff set,
- review of compatibility and deprecation warnings that are still allowed at runtime,
- confirmation of the active source of truth for any feature being released,
- explicit verification of manual or external service steps that the deterministic gate does not cover.

Release approval evidence should be captured as schema v1 JSON and validated
with:

```bash
python ops/scripts/release_approval_check.py --init-template release-approval.json
python ops/scripts/release_approval_check.py release-approval.json
```

`--init-template` writes a non-approval template. It is intentionally not a
passing approval artifact until the deterministic gate is marked true and real
evidence replaces the placeholders.

Operator-facing handoff artifacts should be generated from the same release
approval evidence, not inferred from deterministic QC alone:

```bash
python ops/scripts/release_approval_check.py release-approval.json --json-out var/release-approval.json --markdown-out docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF.md
```

The Markdown handoff is suitable for a GitHub Actions job summary, for example
by appending it to `GITHUB_STEP_SUMMARY`, but it remains a handoff artifact. It
does not make expected external blockers pass.

When the DeSci release gate should reference that operator handoff, pass the
artifact explicitly:

```bash
python apps/desci-platform/scripts/release_gate.py --release-approval-handoff docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF.md --json-out var/desci-release-gate.json
```

If `--release-approval-handoff` is supplied, the release gate adds a synthetic
`release-approval-handoff` result and fails closed when the Markdown artifact is
missing, lacks the expected title or required sections, contains unsafe
secret-shaped markers, or is not ready for job-summary use. The default release
gate behavior is unchanged when the option is omitted.

The evidence object must include:

- `schema_version`
- `generated_at`
- `release_candidate`
- `affected_scope`
- `deterministic_gate`
- `completion_audit_gate` (optional, required for artifacts that claim launch or completion readiness)
- `unblock_preflight_gate` (optional, validates complete-goal unblock evidence when present)
- `recovery_preflight_gate` (optional, validates the workspace recovery-wrapper preflight artifact when present)
- `evidence_consistency_gate` (optional, validates current complete-goal evidence consistency when present)
- `worktree`
- `compatibility_warnings`
- `source_of_truth`
- `evidence_references` (optional, validates supporting evidence JSON timestamps when present)
- `external_steps`

`deterministic_gate.ok` must be true and include both the command and evidence
path. The evidence path must point to an existing, complete, all-pass smoke JSON report.
The smoke report must be a schema v1 object with result scopes, and its scope must match `affected_scope` unless `affected_scope` is `all`.
The command must run `ops/scripts/run_workspace_smoke.py`, and its command `--scope` and `--json-out` values must match `affected_scope` and `deterministic_gate.evidence_path`.
Every gate evidence JSON `generated_at` must be parseable, timezone-aware, and not newer than the release approval root `generated_at`, so the approval artifact cannot predate evidence it claims to summarize.
When present, `completion_audit_gate.ok` must be true and its command must run
`ops/scripts/auto_research_status.py` with `--require-completion-audit`; the
command `--json-out` must match `completion_audit_gate.evidence_path`, and the
evidence JSON must report both top-level `status: ok` and
`completion_audit.status: ok` with no `completion_audit.blocking_requirements`.
If the referenced completion evidence is not approval-ready, `completion_audit_gate.ok`
must not be true; non-approval artifacts should keep it false until the evidence
and external-step statuses are repaired.
When present, `unblock_preflight_gate` must run
`ops/scripts/complete_goal_unblock_gate.py` with `--allow-blocked-external`,
`--allow-ready-to-rerun`, and a command `--json-out` matching
`unblock_preflight_gate.evidence_path`. Its evidence JSON must report a known
unblock status, boolean `rerun_recommended`, `secrets_redacted: true`,
`signals.credential_signal_present`,
`signals.credential_file_newer_than_input_status`,
`signals.side_channel_credential_signal`, structured `credential_file` freshness comparisons for the DailyNews and getdaytrends input-status artifacts, and a
`side_channel_inventory` object. The side-channel inventory
must be secret-redacted and include boolean
`new_local_credential_signal_present`, `.pgpass` source counts, scheduled-task
credential/env-file reference counts, and Docker Compose credential-reference
file counts; the side-channel signal must match
`side_channel_inventory.new_local_credential_signal_present`. It must also
include a `next_actions` object whose
`status` matches the unblock status and whose current-status actions include
non-empty names, descriptions, and commands. For `blocked_external`, those
commands must mention `dailynews_update_database_url.py`,
`getdaytrends_update_credentials.py`, and
`workspace_external_credential_recovery_refresh.py`; for `ready_to_rerun`, they
must mention `workspace_external_credential_recovery_refresh.py`. The status must be internally consistent with
`ok`, `rerun_recommended`, credential-signal booleans, side-channel signal, and blocking
requirements. Blocked preflight evidence is coherent for
non-approval artifacts, but `unblock_preflight_gate.ok` must not be true unless
the evidence reports `ready_to_rerun` or `complete_ready`; `review_required`
preflight evidence must be resolved before it can be carried in release approval evidence.
After completion evidence is approval-ready and no external step remains blocked,
`unblock_preflight_gate.ok` must be true or the gate must be omitted, so stale
blocked preflight evidence cannot pass after the blocker is marked resolved.
When present, `recovery_preflight_gate` must run
`ops/scripts/workspace_external_credential_recovery_refresh.py` with
`--execute`, `--preflight-unblock-gate`, and a command `--json-out` matching
`recovery_preflight_gate.evidence_path`. Its evidence JSON must report
`dry_run: false`, `preflight_unblock_gate: true`, boolean `ok`, status `ok` or
`action_required`, integer
summary counts that match the `results` array,
`execution_contract.approval_ready_requires_preflight_unblock_gate: true`,
`execution_contract.preflight_unblock_gate_present: true`,
`execution_contract.ok_blocked: false`, an empty
`execution_contract.ok_blocked_reason`, and a non-empty results array that
includes `Complete goal unblock preflight`. If the preflight stops before the full matrix, the evidence
must include `full_matrix_blocked.reason` set to
`complete_goal_unblock_preflight_not_ready`, a non-empty skipped-step list that
matches the skipped `results` rows, and detail text showing
`status=blocked_external`. `recovery_preflight_gate.ok`
must not be true unless the evidence reports recovery-ready `ok`; when recovery
evidence reports `status: ok`, any `full_matrix_blocked` object must report
`blocked: false`, summary `failed`, `skipped`, and `planned` counts must be
zero, `completed` must equal `total`, and every result row must be complete
and passing. After
completion evidence is approval-ready and no external step remains blocked,
`recovery_preflight_gate.ok` must be true or the gate must be omitted.
Executable recovery-wrapper artifacts produced without `--preflight-unblock-gate`
are diagnostic only; the wrapper marks them not approval-ready even if every
full-matrix step passes.
When present, `evidence_consistency_gate` must run
`ops/scripts/complete_goal_evidence_consistency_check.py` with a command
`--json-out` matching `evidence_consistency_gate.evidence_path`. Its evidence
JSON must report `status: ok`, `ok: true`, integer `summary.total`,
`summary.passed`, and `summary.failed` counts, `summary.failed: 0`,
`summary.passed` equal to `summary.total`, and a non-empty `results` array in
which every row reports `ok: true`. The consistency evidence `generated_at`
must not be newer than the release approval root `generated_at`, and
`evidence_consistency_gate.ok` must not be true until that evidence is fully
consistent.
`worktree.status` must be either `clean` or `reviewed_in_progress`; the
reviewed-in-progress state requires a review note and unique `changed_paths`; when the
validator runs against a git checkout, those entries must be repo-relative,
must not point at the repository root or `.git`, and entries must exist in git status.
If the status is `clean`, the actual git worktree must be clean when the
validator is run. Compatibility warnings and
source-of-truth status must be explicitly `reviewed` or `not_applicable`.
When present, `evidence_references.items` must be a non-empty list of supporting
JSON artifacts with repo-relative snapshot-style `path` values and expected
timezone-aware `generated_at` timestamps. Supporting reference paths must not use
mutable `latest` or `current` artifact names. Each referenced JSON file must exist,
contain a JSON object, expose `generated_at`, match the listed timestamp, and
not be newer than the release approval root `generated_at`. This prevents
hand-written supporting evidence summaries, such as browser-smoke or readiness
references, from drifting behind the artifacts they cite.
Manual or external steps must each be `verified`, `not_applicable`, or
`blocked`, with evidence text. `blocked` is a valid evidence status for an
active external dependency, but it fails approval until the blocker is resolved.
An empty external-step list requires a not-applicable reason.

### Release approval machine gate (operational checklist)

- `docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json` is the first machine-approved workspace release artifact for the current reviewed-in-progress scope.
- Preferred one-shot run (uses reviewed-in-progress defaults and auto-discovers the current artifact):

  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File ops/scripts/run_release_approval_gate_machine.ps1
  ```

  The wrapper runs workspace smoke, validates the discovered release approval
  artifact, writes machine JSON plus `RELEASE_APPROVAL_OPERATOR_HANDOFF`
  Markdown with `--markdown-out`, and refreshes session bootstrap evidence. In
  GitHub Actions it appends the Markdown handoff to `GITHUB_STEP_SUMMARY` when
  that environment file is present; locally, pass `-AppendGitHubStepSummary` to
  require the same append attempt.
  The `.github/workflows/desci-platform-quality.yml` workflow exposes this path
  only as the manual `workflow_dispatch` input `release_approval_handoff`, so
  ordinary PR and push quality gates remain deterministic and are not failed by
  expected external release-approval blockers unless an operator explicitly runs
  the handoff job. That manual job also runs the DeSci release gate in dry-run
  mode with `--release-approval-handoff`, writes
  `release-approval-handoff-artifact-index-machine.json` through
  `ops/scripts/write_release_approval_handoff_artifact_index.py`. The index
  includes the review order, exit codes, `upload_before_fail_closed`,
  `all_required_artifacts_present`, missing-artifact counts, and artifact
  existence/size metadata with `sha256` digests for existing files. The same
  script also writes
  `release-approval-handoff-artifact-index-summary.md` and appends that compact
  Markdown summary, including short SHA-256 prefixes, to `GITHUB_STEP_SUMMARY`
  so operators can see the first decision artifact and missing count without
  downloading the bundle. The job
  uploads that index plus
  `desci-release-gate-release-approval-handoff-machine.json`, and then fails
  closed after artifact upload if either the approval wrapper or release-gate
  handoff validation returned nonzero. The upload uses `if-no-files-found: error`
  and `retention-days: 30`.

- Equivalent manual verification sequence:

  1. `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-2026-05-28-release-approval-artifact.json`
  2. `python ops/scripts/release_approval_check.py docs/reports/2026-05/RELEASE_APPROVAL_WORKSPACE_2026-05-28.json --json-out var/release-approval-check-machine.json --markdown-out docs/reports/2026-06/RELEASE_APPROVAL_OPERATOR_HANDOFF_MACHINE.md`
  3. `python ops/scripts/session_bootstrap.py --json-out var/session-bootstrap-2026-05-28-release-approval-artifact.json`
- Validity condition: the smoke evidence must report `status: complete`, `8/8`, and `schema_version: 1`; the approval check must print `release approval evidence is valid`.
- Worktree policy:
  - `status: clean` requires a clean git worktree at validation time.
  - `status: reviewed_in_progress` must include `review_note` and `changed_paths`.
- `changed_paths` are required to be unique, repo-relative, non-root, non-`.git`, and actually dirty in `git status --porcelain` for the validated checkout.

DailyNews rule:

- Treat report status `published` as shorthand for `notion_synced` unless external delivery has been separately verified.

## JSON report schema

`run_workspace_smoke.py --json-out <path>` writes a schema v1 JSON object containing:

- `schema_version`
- `generated_at`
- `status`
- `summary`
- `results`

Each entry in `results` contains:

- `scope`
- `name`
- `cwd`
- `command`
- `returncode`
- `ok`
- `stdout_tail`
- `stderr_tail`
