# AutoResearch Loop - AgriGuard Reasoned Env Findings

## Objective

Make the final guarded-launch env-shape blocker more precise for operators.
The validator already knew whether a blocked value was an angle-bracket
placeholder, a sample domain, or another known placeholder, but the
operator-facing `blocking_findings` collapsed every case into
`Replace placeholder value ...`.

## Scope and Owned Paths

- `apps/AgriGuard/scripts/validate_launch_env_template.py`
- `apps/AgriGuard/backend/tests/test_validate_launch_env_template.py`
- `apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py`
- This cycle report.

## A/B Hypothesis and Decision Rule

- Baseline: emit one generic placeholder replacement message for every
  placeholder-like value.
- Variant: emit reason-specific blocking findings:
  `angle-bracket placeholder`, `sample domain`, or `placeholder-like`.
- Primary KPI: the live operator packet should clearly distinguish real
  `<...>` placeholders from `example.com` sample domains while preserving
  redaction.
- Guardrails: focused validator/operator-packet tests and canonical AgriGuard
  smoke must pass.

## Baseline Evidence

The generated operator env template had two sample-domain values:

- `AGRIGUARD_ALLOWED_ORIGINS=https://app.example.com`
- `AGRIGUARD_PUBLIC_VERIFY_BASE_URL=https://verify.example.com`

But the operator action reported them as generic placeholder values, the same
wording used for `<set-...>` secrets and file paths.

## Variant Evidence

- Added `_placeholder_finding()` to map placeholder reasons to
  operator-facing findings.
- Angle-bracket values now produce
  `Replace angle-bracket placeholder value for ...`.
- `example.com` values now produce
  `Replace sample domain value for ...`.
- Unknown known-placeholder values still produce a conservative
  `Replace placeholder-like value for ...`.
- Operator packet source errors inherit these exact findings from the
  validation report.

## Verification Commands

```powershell
python -m pytest apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py -q
```

Result: `15 passed in 0.66s`.

```powershell
python apps/AgriGuard/scripts/validate_launch_env_template.py --env-file var\agriguard-guarded-launch.env.template --json-out var\agriguard-launch-env-template-validation-reasoned-placeholders.json --markdown-out var\agriguard-launch-env-template-validation-reasoned-placeholders.md
```

Result: expected exit code `1`, `status=fail`,
`ready_for_preflight=false`, `placeholder_count=6`, with sample-domain findings
for `AGRIGUARD_ALLOWED_ORIGINS` and `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`, and
angle-bracket findings for `AGRIGUARD_DB_PASSWORD`,
`AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, `AGRIGUARD_QR_TOKEN_PEPPER`, and
`AGRIGUARD_SECRET_KEY`.

```powershell
python apps/AgriGuard/scripts/run_guarded_launch.py --emit-handoff --status-json-out var\agriguard-guarded-launch-status-after-reasoned-env-findings.json
```

Result: expected exit code `1` because launch remains
`env_shape_blocked`. The operator packet action
`fix_env_shape_validation` contained the six reason-specific source errors and
kept secrets redacted.

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-reasoned-env-findings.json
```

Result: `passed=5`, `failed=0`, `total=5`, elapsed `9m34s`.

## Decision

Adopt reason-specific env-shape findings. The remaining blocker is still
external operator configuration, but the handoff now tells the operator exactly
which values are sample domains versus angle-bracket placeholders.

## Next Cycle

Commit and push this scoped patch, then continue with the next launch-readiness
gap.
