# AutoResearch DeSci Upload Filename Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Audit marker: `global_objective_complete=false`
- Source signal: `pydantic/pydantic-ai` commit `ed31bdd64e11`,
  `Handle UploadedFile consistently with FileUrl in UI adapters (#5772)`.
- Source link: https://github.com/pydantic/pydantic-ai/commit/ed31bdd64e11ce1475916a398ee3312791ed2d38

## A/B Contract

- Baseline: DeSci uploaded bytes were saved under UUID filenames, but the
  client-provided multipart `filename` still flowed into parser labels,
  manifests, responses, IPFS metadata fallback titles, and asset-list display.
  A crafted URL-like filename could therefore preserve remote or local file
  reference semantics even though the backend had already received bytes.
- Variant: treat every multipart filename as a local display label. Normalize
  URL/path-like filenames at the router boundary and again inside
  `AssetManager`, then use only the normalized label for parser calls,
  manifests, indexing metadata, and responses.
- Primary KPI: uploaded file references such as `file://...` or `s3://...`
  are reduced to basename labels before any downstream product workflow sees
  them.
- Guardrails: no change to upload bytes, auth, IPFS pinning, vector indexing,
  parser selection, or accepted file types.
- Decision rule: adopt only if upload manager and route tests prove URL-like
  filenames are normalized and existing upload endpoint tests still pass.

## Result

- Adopted variant: yes.
- Added `services/upload_security.py` with
  `normalize_client_upload_filename()` and `normalize_upload_file()`.
- `/upload` and `/assets/upload` normalize `UploadFile.filename` before
  delegating to the asset manager.
- `AssetManager` now uses `display_filename` for parser labels, manifests,
  responses, company-asset metadata, and paper fallback titles.
- Regression tests cover `file://...` and `s3://...` filenames at both the
  route and asset-manager layers.

## Changed Paths

- `apps/desci-platform/backend/services/upload_security.py`
- `apps/desci-platform/backend/services/asset_manager.py`
- `apps/desci-platform/backend/routers/web3.py`
- `apps/desci-platform/backend/tests/test_asset_manager.py`
- `apps/desci-platform/backend/tests/test_api_endpoints.py`
- `ops/references/autoresearch_completion_contract.json`
- `ops/references/autoresearch_objective_requirements.json`

## Verification

- `python -m pytest apps/desci-platform/backend/tests/test_asset_manager.py apps/desci-platform/backend/tests/test_api_endpoints.py -q`
  - Passed: `26`.
- `python -m pytest tests/test_autoresearch_completion_audit.py tests/test_autoresearch_objective_coverage.py -q`
  - Passed: `19`.
- `python ops\scripts\run_workspace_smoke.py --scope desci --json-out var\workspace-smoke-desci-upload-filename-2026-06-05.json`
  - Passed: `7/7`.
- `python ops\scripts\autoresearch_completion_audit.py --json-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_COMPLETION_AUDIT_SUMMARY_2026-06-04.md`
  - Valid: `47` criteria, `global_objective_complete=false`.
- `python ops\scripts\autoresearch_objective_coverage.py --json-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.json --markdown-out docs\reports\2026-06\AUTO_RESEARCH_OBJECTIVE_COVERAGE_2026-06-05.md`
  - Valid: `7` requirements, `global_objective_complete=false`.

## Freshness Baseline

- Pushed proof commit: pending product push.
- `current_tip_freshness_gate`: pending refresh after the product commit is on
  `origin/feat/observability-gateway-2026-05`.
- Audit marker: `global_objective_complete=false`.

## Next Cycle

- Continue source-backed adoption from the GitHub digest; likely next target is
  OpenHands timestamp/async identity hardening unless a higher-priority source
  movement appears.
