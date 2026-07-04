# AutoResearch Loop - AgriGuard Prepare Env Firebase File Check

## Objective

Tighten the launch-env preparation helper so it does not report
`ready_for_preflight=true` when the operator-supplied Firebase Admin service
account path is missing on the current host. The prior helper removed generated
secret work, but could still push operators into strict preflight just to learn
that the Firebase JSON file did not exist.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/prepare_launch_env.py`
- `apps/AgriGuard/backend/tests/test_prepare_launch_env.py`
- This cycle report.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` latest observed `main`:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`.

## A/B Hypothesis and Decision Rule

- Baseline: helper validates shape only and returns pass for a missing Firebase
  JSON path.
- Variant: helper requires the Firebase service-account file to exist by
  default, while preserving an explicit `--allow-missing-firebase-file` planning
  mode.
- Primary KPI: a missing Firebase file is caught at prepare time with a
  redacted blocker before guarded launch reaches strict preflight.
- Guardrails: sample-domain and overwrite guards remain intact; reports still
  redact generated secrets and credential paths; canonical AgriGuard smoke must
  pass.

## Variant Evidence

- Added local Firebase file checks to the helper report:
  - `allow_missing_firebase_file`
  - `firebase_service_account_file_exists`
  - redacted Firebase path marker
- Default mode appends
  `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist on this host.`
  to validation blockers and returns exit code `1` when the path is missing.
- `--allow-missing-firebase-file` keeps the old planning behavior available for
  operators who need to draft an env file before copying the credential onto
  the host.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py -q
```

Result: `5 passed in 0.36s`.

```powershell
python apps/AgriGuard/scripts/prepare_launch_env.py --out var\agriguard-launch-operator.missing-firebase.env --allowed-origins https://app.agriguard.io --public-verify-base-url https://verify.agriguard.io --firebase-service-account-file C:\secure\missing-firebase-service-account.json --json-out var\agriguard-launch-env-prepared-missing-firebase.json --markdown-out var\agriguard-launch-env-prepared-missing-firebase.md --force
```

Result: expected exit code `1`, `status=fail`,
`ready_for_preflight=false`,
`local_file_checks.firebase_service_account_file_exists=false`, and a redacted
missing-file blocker.

```powershell
python apps/AgriGuard/scripts/prepare_launch_env.py --out var\agriguard-launch-operator.missing-firebase-planning.env --allowed-origins https://app.agriguard.io --public-verify-base-url https://verify.agriguard.io --firebase-service-account-file C:\secure\missing-firebase-service-account.json --allow-missing-firebase-file --json-out var\agriguard-launch-env-prepared-missing-firebase-planning.json --markdown-out var\agriguard-launch-env-prepared-missing-firebase-planning.md --force
```

Result: exit code `0`, `status=pass`, `ready_for_preflight=true`,
`allow_missing_firebase_file=true`, and
`firebase_service_account_file_exists=false`.

## Decision

Adopt the default file-existence check. It moves an avoidable launch retry
failure into the preparation step while retaining an explicit planning escape
hatch.

## Next Cycle

Run canonical AgriGuard smoke, commit and push this scoped patch, then continue
with app-click/browser validation for the next launch-readiness loop.
