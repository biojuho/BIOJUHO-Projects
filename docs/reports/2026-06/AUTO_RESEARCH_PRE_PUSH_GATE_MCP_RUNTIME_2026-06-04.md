# AutoResearch Pre-Push Gate MCP Runtime - 2026-06-04

## Goal

Make the new dev-server MCP runtime part of the default local push gate instead of relying only on manual focused test runs.

## Baseline

- The installed `pre-push` hook ran `tests/test_workspace_smoke.py` only.
- Pre-push output stayed at `27 passed` after the MCP runtime landed.
- The repo-owned hook installer assumed `.git/hooks` was a directory under the current checkout, so linked worktrees were not handled cleanly.

## Variant

- `ops/hooks/pre-push` now runs:
  - `tests/test_workspace_smoke.py`
  - `tests/test_dev_server_mcp_contract.py`
  - `tests/test_dev_server_mcp_runtime.py`
- `ops/hooks/install_hooks.py` now resolves `git rev-parse --git-common-dir`, creates the hooks directory if needed, and skips directories such as `__pycache__`.
- The updated hook was installed into the common hooks directory from a linked worktree.

## Verification

- `python ops\hooks\install_hooks.py`
  - installed `pre-push` to `D:\AI project\.git\hooks\pre-push`
- `git push --dry-run origin HEAD:feat/observability-gateway-2026-05`
  - pre-push hook ran through Git's real hook path
  - `36 passed`
  - dry run returned `Everything up-to-date`
- `python -m py_compile ops\hooks\install_hooks.py`
  - passed

## Decision

Accepted. The local push gate now covers the dev-server MCP contract and runtime without materially slowing the hook.
