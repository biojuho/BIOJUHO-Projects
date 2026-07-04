# AutoResearch Loop: AgriGuard Prepare Env Bundle Commands

## Objective

Harden `prepare_launch_env.py` so the generated operator `safe_next_commands` can target a specific guarded-launch artifact bundle instead of always pointing at the default guarded status path.

## Scope And Owned Paths

- `apps/AgriGuard/scripts/prepare_launch_env.py`
- `apps/AgriGuard/backend/tests/test_prepare_launch_env.py`

## External Sources Checked

- Veritas AutoResearch source: `Veritas-7/autoresearch-skill-system`, observed `main` at `b8bbf393759d6e67e780f03c572ec626fab6593b`.
- Local modernization radar: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_RESUME_2026-07-05.md`, regenerated successfully with 8 sources and 8 adopted patterns earlier in this run.

## A/B Hypothesis

- Baseline: `prepare_launch_env.py` emitted plain string next commands with default `var/agriguard-launch-env-template-validation.*` and `var/agriguard-guarded-launch-status.json` paths.
- Variant: add guarded output path parameters and emit PowerShell-safe commands that target the chosen guarded output directory, prefix, env-validation outputs, and status JSON.
- Primary KPI: a real prepare-env report emits 2 next commands, both PowerShell-safe, both containing the active guarded prefix.
- Decision rule: adopt only if the real prepare-env path remains redacted, focused tests pass, workspace and AgriGuard smoke pass, and browser smoke remains clean.

## Variant Evidence

Real prepare-env command:

```powershell
python apps/AgriGuard/scripts/prepare_launch_env.py --app-root apps/AgriGuard --out var\agriguard-prepare-bundle-paths.env --allowed-origins https://app.agriguard.io --public-verify-base-url https://verify.agriguard.io --firebase-service-account-file C:\secure\missing-agriguard-firebase-service-account.json --allow-missing-firebase-file --force --guarded-output-dir var --guarded-output-prefix agriguard-prepare-bundle-paths --guarded-status-json var\agriguard-prepare-bundle-paths-status.json --json-out var\agriguard-prepare-bundle-paths.json --markdown-out var\agriguard-prepare-bundle-paths.md
```

Expected result: exit `0` for planning mode with `allow_missing_firebase_file=true`, while secrets remain redacted.

Generated report proof:

```json
{"command_count":2,"prefix":"agriguard-prepare-bundle-paths","command_path_hits":2,"shells":2,"secrets_redacted":true}
```

## Verification Commands

- `python -m py_compile apps/AgriGuard/scripts/prepare_launch_env.py`
- `python -m ruff check apps/AgriGuard/scripts/prepare_launch_env.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py`
- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q` -> 7 passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py tests/test_security_gate_contracts.py -q` -> 22 passed.
- `python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_launch_env_preflight.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q` -> 108 passed.
- `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-agriguard-prepare-bundle-paths.json` -> 9 passed, 0 failed.
- `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-prepare-bundle-paths.json` -> 5 passed, 0 failed.
- `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5174 --api-url http://127.0.0.1:8002 --json-out var\agriguard-browser-smoke-prepare-bundle-paths.json --output-dir var\agriguard-browser-smoke-prepare-bundle-paths --timeout-ms 120000` -> 6 flows, 135 checks, 18 screenshot artifacts passed.

## Adopt Decision

Adopted. The variant keeps prepare-env redaction intact and aligns operator next commands with the selected guarded-launch artifact bundle.

## Commit And Push Status

Pending at report creation.

## Next Cycle

Continue auditing secondary recovery command surfaces, especially handoff validation and status-only views that may still rely on caller-provided command text instead of normalized bundle-local commands.
