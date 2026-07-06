# Auto Research Loop - AgriGuard Launch Peer Loaders - 2026-07-06

## Objective

Apply the confirmed dataclass-safe peer-module loading fix across all AgriGuard launch/operator scripts that duplicate `_load_peer_module`.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_LAUNCH_PEER_LOADERS_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Gap Found

- The guarded-launch loader fix exposed the same fragile dynamic-import pattern in six sibling launch scripts:
  - `consume_guarded_launch_handoff.py`
  - `index_guarded_launch_artifacts.py`
  - `prepare_launch_env.py`
  - `render_guarded_launch_handoff.py`
  - `render_launch_operator_packet.py`
  - `validate_launch_env_template.py`
- These loaders executed peer modules without temporarily registering them in `sys.modules`, which can break dataclass annotation resolution for peer scripts using `from __future__ import annotations`.

## Fix

- Hardened each duplicated `_load_peer_module` implementation to:
  - Register the target module in `sys.modules` before `exec_module`.
  - Restore the previous module binding after execution.
  - Remove the temporary binding when no previous module existed.
- Added a smoke regression that loads all seven launch peer-loader scripts and verifies each can import the dataclass-based `ab_test_qr_page` peer module.

## Verification

- Manual cross-loader repro after fix:
  - `consume_guarded_launch_handoff True`
  - `index_guarded_launch_artifacts True`
  - `prepare_launch_env True`
  - `render_guarded_launch_handoff True`
  - `render_launch_operator_packet True`
  - `run_guarded_launch True`
  - `validate_launch_env_template True`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -k "launch_peer_loaders"`
  - Result: `1 passed, 60 deselected`
- `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py apps/AgriGuard/backend/tests/test_consume_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_index_guarded_launch_artifacts.py apps/AgriGuard/backend/tests/test_prepare_launch_env.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_render_launch_operator_packet.py apps/AgriGuard/backend/tests/test_validate_launch_env_template.py apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Result: `143 passed in 49.08s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-launch-peer-loaders-2026-07-06.json`
  - Result: exit `1` as expected.
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Checked Firebase credential path: `C:\secure\missing-firebase-service-account.json`

## Current Blocker

Local launch peer loading, operator packet, handoff, validation, and smoke coverage are green. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`: `C:\secure\missing-firebase-service-account.json`.
