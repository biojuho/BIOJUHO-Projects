# AutoResearch DeSci Upload Name Fallback

- Date: 2026-06-05
- Source repo: `pydantic/pydantic-ai`
- Source commit: `ed31bdd64e11ce1475916a398ee3312791ed2d38`
- Source signal: `Handle UploadedFile consistently with FileUrl in UI adapters (#5772)`
- Source URL: https://github.com/pydantic/pydantic-ai/commit/ed31bdd64e11ce1475916a398ee3312791ed2d38
- Local product commit: `343caeb44834baebebf6525abb3e31749a8fa052`
- Local status: adopted
- Global objective complete: `false`

## Source Signal

Pydantic AI made uploaded-file handling explicit alongside file URL handling, treating client-supplied file references as a boundary that must be normalized or rejected before provider/runtime code consumes it.

## A/B Contract

- A: Keep DeSci upload normalization focused only on FastAPI's `UploadFile.filename`. Upload-like adapters that expose only `.name` fall back to `upload.bin`, while direct `AssetManager` calls do not share the same route-level candidate selection.
- B: Add a shared upload filename candidate helper that checks `.filename` and `.name`, then normalizes either value through the existing URL/path stripping before parser, vector index, or IPFS metadata code sees it.

Decision: adopted B. It keeps uploaded-file and file-URL-like inputs on the same safe display-label path without preserving client-side URLs, storage paths, or tokenized query strings.

## Local Changes

- `apps/desci-platform/backend/services/upload_security.py`
  - Adds `upload_filename_candidate()` for `.filename` and `.name`.
  - Routes `normalize_upload_file()` through the shared candidate helper.
- `apps/desci-platform/backend/services/asset_manager.py`
  - Uses the same shared candidate helper when saving direct upload objects.
- `apps/desci-platform/backend/tests/test_asset_manager.py`
  - Adds a name-only upload object regression that passes a tokenized HTTPS file reference and expects `research-note.pdf` everywhere downstream.

## Verification

- `python -m pytest apps\desci-platform\backend\tests\test_asset_manager.py -q` -> `5 passed`
- `python -m py_compile apps\desci-platform\backend\services\upload_security.py apps\desci-platform\backend\services\asset_manager.py` -> passed
- `python ops\scripts\run_workspace_smoke.py --scope desci --check-timeout 240 --json-out var\workspace-smoke-desci-upload-name-fallback-2026-06-05.json` -> `7/7 passed`
- `git push origin HEAD:feat/observability-gateway-2026-05` for product commit `343caeb44834baebebf6525abb3e31749a8fa052` -> pre-push passed `250` Python tests plus dashboard, Canva, MCP, workflow, and AutoResearch gates
- `python -m pytest apps\desci-platform\backend\tests\test_asset_manager.py tests\test_autoresearch_completion_audit.py tests\test_autoresearch_objective_coverage.py -q` -> `24 passed`
- `python ops\scripts\autoresearch_completion_audit.py` -> `88 criteria`, `global_objective_complete=false`
- `python ops\scripts\autoresearch_objective_coverage.py` -> `7 requirements`, `global_objective_complete=false`

## Completion State

- `protected_path_freshness` proof baseline: `343caeb44834baebebf6525abb3e31749a8fa052`
- `global_objective_complete=false`
