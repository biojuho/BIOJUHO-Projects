# AutoResearch Loop: Launch Operator Packet

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Convert fail-closed launch preflight output into a redacted operator packet that
lists the exact remaining launch inputs and safe rerun commands without
weakening the launch gate or exposing secrets.

## Scope and Owned Paths

- `scripts/render_launch_operator_packet.py`
- `backend/tests/test_render_launch_operator_packet.py`

The worktree is broadly dirty from unrelated ongoing work, so this cycle used
new AgriGuard-owned files only.

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` main:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local modernization radar:
  `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-2026-07-04-continuation.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_2026-07-04_CONTINUATION.md`
  reported `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`.

The adopted source-backed pattern is fail-closed completion evidence with
machine-readable status and durable human-readable handoff.

## A/B Hypothesis

Baseline: `launch_env_preflight.py` writes a strict JSON report. It is correct,
but an operator still has to translate raw errors into a launch checklist.

Variant: add a packet renderer that reads preflight JSON and writes both JSON
and Markdown with stable operator action IDs, affected variable names,
validation criteria, redacted source errors, and safe rerun commands. The
renderer exits nonzero while blocked unless `--exit-zero-on-blocked` is used for
diagnostic artifact generation.

Primary KPI: current blocked preflight is reduced to a deterministic packet with
the exact external inputs required for launch.

Decision rule: adopt if focused tests pass, the renderer exits fail-closed by
default, current preflight output generates a useful redacted packet, and
canonical AgriGuard smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_render_launch_operator_packet.py -q
```

Result: `4 passed in 0.36s`.

Compile check:

```powershell
python -m py_compile scripts/render_launch_operator_packet.py backend/tests/test_render_launch_operator_packet.py
```

Result: passed.

Current strict preflight:

```powershell
python scripts/launch_env_preflight.py --check-docker --json-out ..\var\agriguard-launch-env-preflight-operator-packet-current.json
```

Result: expected `status=fail`; Docker daemon and compose config checks passed.
Errors were missing `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`, app-scoped
secret, QR token pepper, public verify URL, and allowed origins.

Operator packet rendering:

```powershell
python scripts/render_launch_operator_packet.py --preflight-json ..\var\agriguard-launch-env-preflight-operator-packet-current.json --json-out ..\var\agriguard-launch-operator-packet-current.json --markdown-out ..\var\agriguard-launch-operator-packet-current.md --exit-zero-on-blocked
```

Result: packet status `blocked`, `secrets_redacted=true`,
`blocking_action_count=5`, action IDs:

- `set_firebase_service_account_file`
- `set_secret_key`
- `set_qr_token_pepper`
- `set_public_verify_base_url`
- `set_allowed_origins`

Fail-closed exit behavior:

```powershell
python scripts/render_launch_operator_packet.py --preflight-json ..\var\agriguard-launch-env-preflight-operator-packet-current.json --json-out ..\var\agriguard-launch-operator-packet-current-nonzero-check.json --markdown-out ..\var\agriguard-launch-operator-packet-current-nonzero-check.md
```

Result: returned exit code `1` as expected for a blocked packet.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-launch-operator-packet.json
```

Result: `passed=5`, `failed=0`, `total=5`; elapsed `5m25s`.

## Adopt Decision

Adopt the launch operator packet renderer. It makes the current external
operator blocker explicit and reusable while preserving the strict launch
preflight as the authority.

## Remaining Launch Blocker

Real compose/browser launch still requires operator-provided production values:

- `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE` pointing to a real Firebase Admin
  service-account JSON outside the repo.
- Strong `AGRIGUARD_SECRET_KEY`.
- Stable strong `AGRIGUARD_QR_TOKEN_PEPPER`.
- HTTPS `AGRIGUARD_PUBLIC_VERIFY_BASE_URL`.
- Explicit production `AGRIGUARD_ALLOWED_ORIGINS`.

## Next Cycle

Integrate the packet renderer into `scripts/launch_compose.py` so preflight
failures automatically emit the packet alongside the aggregate compose launch
report.
