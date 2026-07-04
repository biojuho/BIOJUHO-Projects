# AutoResearch Loop: DeSci Handoff Release Discovery

Date: 2026-07-04

## Objective

Remove the remaining manual artifact-selection gap from the DeSci launch
handoff refresh. After the live-source scope fix, the refresh exited cleanly but
reported `release_handoff=not_configured` unless the operator supplied the
release handoff JSON path.

## Baseline

- Explicit handoff refresh with
  `--release-handoff-json apps\desci-platform\var\release-handoff-provider-remediation-2026-07-04.json`
  exited `0`.
- Result:
  - `status=action_required`
  - `topic=DeSci`
  - `live_source=current`
  - `secret_scan=valid`
  - `release_handoff=valid`
  - `provider_preflight=False`

Without the explicit path, the same refresh previously reported
`release_handoff=not_configured`, which hid the current provider preflight
summary from the bundle.

## Change

- `ops/scripts/desci_launch_handoff_refresh.py` now auto-discovers the latest
  `apps/desci-platform/var/release-handoff*.json` artifact when
  `--release-handoff-json` is omitted.
- Explicit `--release-handoff-json` still wins.
- The discovered artifact is included in all handoff secret-scan passes.

## Verification

- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py`
  - Exit code `0`.
- `python -m pytest tests\test_desci_launch_handoff_refresh.py -q`
  - `10 passed`.
- Real refresh without `--release-handoff-json`:
  - `python ops\scripts\desci_launch_handoff_refresh.py --live-source-commit b8bbf393759d6e67e780f03c572ec626fab6593b --check-live-source --allow-action-required --radar-json apps\desci-platform\var\github-modernization-radar-desci-handoff-refresh-2026-07-04-post-governance.json --radar-markdown-out apps\desci-platform\docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_HANDOFF_REFRESH_2026-07-04_POST_GOVERNANCE.md --status-json-out apps\desci-platform\var\auto-research-status-desci-handoff-refresh-auto-release-handoff-2026-07-04.json --status-markdown-out apps\desci-platform\docs\reports\2026-07\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_HANDOFF_REFRESH_AUTO_RELEASE_HANDOFF_2026-07-04.md --secret-scan-json-out apps\desci-platform\var\desci-launch-secret-scan-handoff-refresh-auto-release-handoff-2026-07-04.json --bundle-json-out apps\desci-platform\var\desci-launch-handoff-refresh-auto-release-handoff-2026-07-04.json`
  - Exit code `0`.
  - Auto-discovered release handoff:
    `apps/desci-platform/var/release-handoff-provider-remediation-2026-07-04.json`.
  - Bundle result: `ok=true`, `unexpected_failed_checks=[]`,
    `failed_checks=[desci_launch_handoff_refresh_ready]`,
    `release_decision=no-go`, `provider_preflight_ok=false`,
    `provider_count=3`, `ready_provider_count=1`, `failed_check_count=4`,
    `auth_context_missing_count=4`, `missing_cli_count=0`.

## Current Boundary

The handoff refresh now carries the current provider preflight evidence by
default. Launch remains blocked by external provider/auth context, not by missing
handoff discovery.
