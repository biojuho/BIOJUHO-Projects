# AutoResearch Loop: Compose Operator Packet

Date: 2026-07-04
App: AgriGuard
Decision: Adopted

## Objective

Make `scripts/launch_compose.py` automatically emit the redacted launch
operator packet whenever strict preflight blocks compose startup.

## Scope and Owned Paths

- `scripts/launch_compose.py`
- `backend/tests/test_launch_compose_script.py`

## External Sources Checked

- `Veritas-7/autoresearch-skill-system` main:
  `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Local modernization radar from this continuation remained valid:
  `8 sources`, `adopted=8`, `partially_adopted=0`, `watch=0`.

The relevant pattern is durable fail-closed status: a blocked launch attempt
should produce both machine-readable status and the operator handoff artifact in
the same run.

## A/B Hypothesis

Baseline: `launch_compose.py` wrote an aggregate launch report on preflight
failure, but the operator packet had to be generated separately.

Variant: add default operator-packet JSON/Markdown paths, include the packet
command in dry-run and aggregate command metadata, run the packet renderer after
preflight failure with `--exit-zero-on-blocked`, and embed a compact packet
summary into `child_reports.operator_packet`.

Primary KPI: one failed launch-wrapper run produces a single aggregate report
that links the packet and lists the blocking action IDs.

Decision rule: adopt if focused tests cover dry-run command planning,
preflight-failure packet generation, embedded packet summaries, and canonical
AgriGuard smoke remains green.

## Evidence

Focused tests:

```powershell
python -m pytest backend/tests/test_launch_compose_script.py backend/tests/test_render_launch_operator_packet.py -q
```

Result: `13 passed in 0.70s`.

Current fail-closed launch-wrapper run:

```powershell
python scripts/launch_compose.py --run-browser-smoke --json-out ..\var\agriguard-launch-compose-operator-packet-preflight.json --launch-report-json ..\var\agriguard-compose-launch-operator-packet-report.json --operator-packet-json ..\var\agriguard-launch-compose-operator-packet.json --operator-packet-markdown ..\var\agriguard-launch-compose-operator-packet.md
```

Result: expected exit code `1`. Docker daemon and compose config checks passed,
compose was not run, and the aggregate report embedded:

- `child_reports.operator_packet.status`: `blocked`
- `child_reports.operator_packet.preflight_status`: `fail`
- `child_reports.operator_packet.secrets_redacted`: `true`
- `child_reports.operator_packet.blocking_action_count`: `5`
- `child_reports.operator_packet.operator_action_ids`:
  `set_firebase_service_account_file`, `set_secret_key`,
  `set_qr_token_pepper`, `set_public_verify_base_url`,
  `set_allowed_origins`

Dry-run command plan:

```powershell
python scripts/launch_compose.py --run-browser-smoke --dry-run
```

Result: plan includes `operator_packet_command`, default
`operator_packet_json`, default `operator_packet_markdown`, and
`will_write_operator_packet_on_preflight_failure=true`.

Canonical smoke:

```powershell
python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-compose-operator-packet.json
```

Result: `passed=5`, `failed=0`, `total=5`; elapsed `5m55s`.

## Adopt Decision

Adopt the compose-launch packet integration. Operators now get the redacted
handoff packet from the same command that blocks unsafe launch, so the next
required action is visible without manually running another script.

## Remaining Launch Blocker

Real compose/browser launch still requires the same operator-provided production
values: Firebase Admin service-account JSON path, strong app secret, stable QR
token pepper, HTTPS public verify URL, and explicit production allowed origins.

## Next Cycle

Use the packet action IDs as the basis for a guarded operator-ready checklist or
credential-shape fixture so the remaining external inputs can be validated
before any live compose retry.
