# AutoResearch Loop - AgriGuard Prepare Launch Env

## Objective

Reduce manual launch-env work without putting secrets in git. The final
guarded-launch blocker still listed six operator env values, but three of them
are machine-generated values: database password, app secret key, and QR token
pepper. Operators should only need to provide values the repo cannot know:
public HTTPS origins, public verify URL, and a Firebase Admin service-account
JSON path.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/prepare_launch_env.py`
- `apps/AgriGuard/backend/tests/test_prepare_launch_env.py`
- `apps/AgriGuard/scripts/run_guarded_launch.py`
- `apps/AgriGuard/scripts/guarded_launch_handoff.schema.json`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: require operators to manually edit every generated env-template
  placeholder.
- Variant: add a helper that writes an operator env file in `var/`, generates
  strong values for local secrets, redacts reports, validates shape, and emits
  safe next commands.
- Primary KPI: helper-generated env passes shape validation with
  `ready_for_preflight=true`, and guarded launch advances from
  `env_shape_blocked` to strict preflight.
- Guardrails: helper refuses overwrite unless `--force`, sample domains still
  fail closed, reports do not include generated secrets, and canonical
  AgriGuard smoke must pass.

## Variant Evidence

- `prepare_launch_env.py` generates:
  - `AGRIGUARD_DB_PASSWORD`
  - `AGRIGUARD_SECRET_KEY`
  - `AGRIGUARD_QR_TOKEN_PEPPER`
- Operators provide:
  - `AGRIGUARD_ALLOWED_ORIGINS`
  - `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`
  - `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`
- The helper writes a dotenv file, immediately runs the existing
  `validate_launch_env_template.py` shape report, and prints/writes only a
  redacted report.
- The helper returns:
  - `0` when shape validation is ready for strict preflight.
  - `1` when the generated file still fails shape validation.
  - `2` when the output file already exists and `--force` was not passed.
- The guarded-launch compact status view and handoff schema now expose the
  readiness fields that downstream handoff validation already expects from the
  artifact index and operator packet.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py -q
```

Result: `8 passed in 0.47s`.

```powershell
python apps/AgriGuard/scripts/prepare_launch_env.py --out var\agriguard-launch-operator.generated.env --allowed-origins https://app.agriguard.io --public-verify-base-url https://verify.agriguard.io --firebase-service-account-file C:\secure\firebase-service-account.json --json-out var\agriguard-launch-env-prepared-helper.json --markdown-out var\agriguard-launch-env-prepared-helper.md --force
```

Result: exit code `0`, `status=pass`, `ready_for_preflight=true`,
`placeholder_count=0`, and `blocking_findings=[]`. The report listed generated
fields and redacted all values.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --env-file var\agriguard-launch-operator.generated.env --emit-handoff --status-json-out var\agriguard-guarded-launch-status-after-prepared-env-helper.json
```

Result: expected exit code `1`. The launch advanced past env-shape validation:
`readiness_env_validation_ready_for_preflight=true`,
`readiness_env_validation_placeholder_count=0`, and blocker class changed to
`preflight_blocked`. Strict preflight then failed only because the supplied
example Firebase service-account file path did not exist:
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE file does not exist.`

## Decision

Adopt the prepare-launch-env helper. It removes avoidable manual secret
generation from the launch path while preserving fail-closed checks for the
external Firebase credential and public deployment values.

## Next Cycle

Run canonical smoke, commit and push this scoped patch, then continue with the
next launch-readiness gap.
