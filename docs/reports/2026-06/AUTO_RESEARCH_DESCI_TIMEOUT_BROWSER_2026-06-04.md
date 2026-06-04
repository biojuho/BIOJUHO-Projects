# AutoResearch DeSci Timeout Browser Pass - 2026-06-04

## Scope

- Surface: DeSci local API/frontend readiness and browser route coverage.
- Baseline: `desci-api` was live on `8000`, but the generic 1-2 second readiness timeout misclassified `/health` as unavailable. The managed `desci-frontend` start failed because its API dependency appeared unready.
- Variant adopted: add target-level `timeout_seconds` support to the dev-server manifest/status probe, set `desci-api` to `5` seconds, and prevent stale failed-start PIDs from being reused as managed state when an external service is already ready.
- Smoke blocker settled: the clean remote worktree also exposed an unrelated shared fact-check regression where `source_names` were scored for credibility but not included in the verification corpus. The existing test expected source publisher names to verify entity claims, so the source corpus now includes source names.

## Changed Paths

- `ops/references/dev_server_targets.json`
- `ops/scripts/dev_server_status.py`
- `ops/scripts/dev_server_control.py`
- `tests/test_dev_server_status.py`
- `tests/test_dev_server_control.py`
- `packages/shared/fact_check/verifier.py`
- `docs/reports/2026-06/AUTO_RESEARCH_DESCI_TIMEOUT_BROWSER_2026-06-04.md`

## Decision Rule

Adopt the variant if:

- manifest validation accepts positive per-target timeouts and rejects invalid values,
- probes pass target-specific timeout values to the fetcher,
- DeSci API is classified ready with the manifest timeout,
- the controller reuses already-ready external services without attaching stale managed PIDs,
- DeSci browser routes load without console, page, or request failures,
- focused tests and workspace smoke pass.

## Evidence

- Initial failure:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-desci-stack-start-2026-06-04.json start --target desci-frontend --wait-ready --wait-timeout 60 --poll-interval 1 --timeout 1`
  - Result: failed because dependency `desci-api` did not become ready.
  - Tail evidence: `var/dev-server-control-desci-api-tail-start-fail-2026-06-04.json` showed a duplicate bind failure while an existing DeSci API was already on `8000`.
- Raw API probe:
  - `curl.exe -i --max-time 8 http://127.0.0.1:8000/health`
  - Result: `200 OK` with `vector_store_backend:"chroma"` after roughly 2 seconds.
- Target-specific readiness:
  - `python ops/scripts/dev_server_status.py --target desci-api --timeout 1 --json-out var/dev-server-status-desci-api-target-timeout-2026-06-04.json`
  - Result: `1/1` ready because the target-level `timeout_seconds: 5` overrode the generic CLI timeout.
- Managed reuse:
  - `python ops/scripts/dev_server_control.py --json-out var/dev-server-control-desci-api-reuse-timeout-2026-06-04.json start --target desci-api --wait-ready --wait-timeout 15 --poll-interval 1 --timeout 1`
  - Result: `dev server already ready: desci-api`.
- Stack readiness:
  - `python ops/scripts/dev_server_status.py --target desci-api --target desci-frontend --timeout 1 --json-out var/dev-server-status-desci-stack-ready-timeout-2026-06-04.json`
  - Result: `2/2` ready.
- Browser click pass:
  - Python Playwright toggled KO/EN and visited `/`, `/explore`, `/pricing`, and `/login`.
  - Screenshot: `var/desci-live-click-pass-2026-06-04.png`.
  - Result: `events: []`, no console errors, page errors, or request failures.
- Focused tests:
  - `python -m pytest tests\test_dev_server_control.py tests\test_dev_server_status.py -q -p no:cacheprovider`
  - Result: `17` passed.
  - `python -m pytest packages\shared\tests\test_fact_check_verifier.py -q -p no:cacheprovider`
  - Result: `9` passed.
- Workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/workspace-smoke-workspace-desci-timeout-browser-2026-06-04-final.json`
  - Result: passed `6/6` in the clean worktree after ignored junctions restored the expected local `.venv` and dashboard `node_modules`.

## Remaining Launch Work

- Continue live browser passes for deeper authenticated DeSci flows when credentials are available.
- Consider adding grouped dependency stop to `dev_server_control.py` after more multi-target sessions confirm the needed operator behavior.
