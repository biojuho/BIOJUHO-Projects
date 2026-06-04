# AutoResearch DeSci Dev-Server Control - 2026-06-04

## Objective

Close the remaining DeSci launch-readiness gap in the manifest-backed dev-server control path: start the DeSci frontend through `ops/scripts/dev_server_control.py`, let it manage the API dependency, verify the real browser path, and stop the managed stack cleanly.

## Baseline Failure

- Initial command:
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-start-2026-06-04.json start --target desci-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 2`
  - Result: failed with `dependency desci-api did not become ready`.
- Backend evidence after the failed start:
  - `desci-api` was live as managed PID `10712`, but `/health` was too slow for the default 2-second probe budget during warmup.
  - A second frontend start failed with `desci-api is already managed with live pid 10712`, so the controller could not reuse a warming dependency.

## Variant Adopted

- `ops/references/dev_server_targets.json`
  - Added `timeout_seconds: 5.0` to `desci-api` because `/health` checks vector, Redis, RabbitMQ, LLM, IPFS, and GROBID state and can legitimately exceed the generic 2-second UI probe budget.
- `ops/scripts/dev_server_status.py`
  - Added optional target-level `timeout_seconds` validation.
  - `probe_target()` now uses the target timeout override and records the effective timeout in status output.
- `ops/scripts/dev_server_control.py`
  - If a target is already managed with a live PID and `--wait-ready`/reuse is enabled, the controller now waits on that existing process instead of treating it as a duplicate-start error.

## Verification

- Focused tests:
  - `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py -q -p no:cacheprovider` -> `18 passed`.
  - `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py tests\test_workspace_smoke.py::test_quality_gate_documents_default_check_names -q -p no:cacheprovider` -> `19 passed`.
- Managed DeSci start:
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-frontend-start-fixed-2026-06-04.json start --target desci-frontend --wait-ready --wait-timeout 90 --poll-interval 2 --timeout 2`
  - Result: `dev server ready: desci-frontend pid=13048, attempts=3`.
- Managed status:
  - `python ops\scripts\dev_server_status.py --target desci-api --target desci-frontend --timeout 2 --json-out var\dev-server-status-desci-managed-fixed-2026-06-04.json`
  - Result: `2/2 ready`; `desci-api` used `timeout_seconds: 5.0`.
- Browser route smoke:
  - `python apps\desci-platform\scripts\browser_smoke.py --frontend http://127.0.0.1:5175 --json-out var\desci-browser-smoke-managed-control-2026-06-04.json`
  - Result: `7/7 OK`.
- Click-level browser evidence:
  - Opened `http://127.0.0.1:5175/`, clicked Explore, filled the Explore search box with `AI`, returned home, clicked Pricing, and saved `desci-managed-control-clicks.png`.
  - Console evidence: `desci-managed-control-console.md` -> `0` warnings/errors, `0` page errors, `0` non-aborted request failures.
- Canonical smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-workspace-desci-control-2026-06-04.json` -> `8/8 PASS`.
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-managed-control-2026-06-04.json` -> `8/8 PASS` after the underlying long-running process completed; final artifact status is `complete`.
- Stop/cleanup:
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-frontend-stop-fixed-2026-06-04.json stop --target desci-frontend --timeout 10`
  - `python ops\scripts\dev_server_control.py --json-out var\dev-server-control-desci-api-stop-fixed-2026-06-04.json stop --target desci-api --timeout 10`
  - Final status: `python ops\scripts\dev_server_status.py --target desci-api --target desci-frontend --timeout 2 --json-out var\dev-server-status-desci-after-stop-fixed-2026-06-04.json` -> `0/2 ready`.

## Decision

Adopted. The controller can now start a DeSci frontend session through the manifest, reuse an already managed API dependency while it warms, preserve logs/status evidence, pass browser and smoke gates, and stop the stack without manual process handling.

## Remaining Notes

- DeSci backend logs still show `rabbitmq_dependency_missing` warnings when RabbitMQ is not installed locally. The health endpoint reports `rabbitmq_ok=false`, but the product browser path, route smoke, backend smoke, and release-readiness contracts all passed; this remains environment noise rather than a launch-blocking code defect.
