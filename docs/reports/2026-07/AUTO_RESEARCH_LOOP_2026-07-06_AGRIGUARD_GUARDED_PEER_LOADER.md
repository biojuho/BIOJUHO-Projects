# Auto Research Loop - AgriGuard Guarded Peer Loader - 2026-07-06

## Objective

Harden the guarded launch peer-module loader so it can import scripts that use dataclasses with postponed annotations.

## Source Check

- Upstream AutoResearch reference: `https://github.com/Veritas-7/autoresearch-skill-system.git`
- Latest observed `HEAD` / `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar output: `docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_GUARDED_PEER_LOADER_2026-07-06.md`
- Radar result: `8 sources, adopted=8, partially_adopted=0, watch=0`

## Gap Found

- Direct repro:
  - `run_guarded_launch._load_peer_module("ab_test_qr_page")`
  - Before the fix, this failed with `AttributeError: 'NoneType' object has no attribute '__dict__'` while importing the dataclass-based QR A/B script.
- Cause: the peer loader executed modules without temporarily registering them in `sys.modules`, which breaks dataclass annotation resolution for modules using `from __future__ import annotations`.

## Fix

- `apps/AgriGuard/scripts/run_guarded_launch.py`
  - Registers the peer module in `sys.modules` before `exec_module`.
  - Restores the previous module binding, or removes the temporary binding, after execution.
- `apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py`
  - Adds a regression test that loads `ab_test_qr_page` through the guarded peer loader and instantiates `QRSessionObservation`.
  - Asserts the helper restores `sys.modules` state after loading.

## Verification

- Direct repro after fix:
  - `loaded ab_test_qr_page True`
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py -k "load_peer_module"`
  - Result: `1 passed, 27 deselected`
- `python -m pytest apps/AgriGuard/backend/tests/test_run_guarded_launch_script.py apps/AgriGuard/backend/tests/test_render_guarded_launch_handoff.py apps/AgriGuard/backend/tests/test_validate_guarded_launch_handoff.py`
  - Result: `37 passed in 1.72s`
- `python apps\AgriGuard\scripts\run_guarded_launch.py --status-only --require-ready --status-json-out var\agriguard-guarded-launch-ready-gate-peer-loader-2026-07-06.json`
  - Result: exit `1` as expected.
  - Status: `blocked`
  - Blocker class: `preflight_blocked`
  - Checked Firebase credential path: `C:\secure\missing-firebase-service-account.json`

## Current Blocker

Local guarded-launch peer loading and handoff/status tests are green. Launch remains externally blocked until an operator provides a real Firebase Admin service-account `.json` at the configured host path for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`: `C:\secure\missing-firebase-service-account.json`.
