# AutoResearch Vibe Tools Workspace Path Guard

- Date: 2026-06-05
- Cycle status: adopted
- Global objective complete: `false`
- Source signal: `google/adk-python` commit `1fa7cda`, `fix: block path traversal in Agent Builder file tools`.
- Source link: https://github.com/google/adk-python/commit/1fa7cda96a41d8bcadefb7cb7346d4795560d9f6

## A/B Contract

- Baseline: `read_file_tool` and `write_code_tool` accepted raw filesystem
  paths from agent-facing Vibe Coding workers. A relative traversal or absolute
  path could reach outside the workspace before normal OS file errors applied.
- Variant: resolve every requested file through a repo-root workspace guard.
  Empty paths, absolute paths, `..` traversal, and symlink escapes are rejected
  before reads or writes occur.
- Primary KPI: traversal and absolute-path attempts return safe tool errors and
  do not create files outside the configured workspace root.
- Guardrails: allowed test-command validation remains unchanged; normal
  repo-relative reads and writes continue to work; parent directory creation
  behavior is not broadened.
- Decision rule: adopt only if the focused Vibe tool regression suite passes,
  the module compiles, and AutoResearch audits accept the new evidence.

## Result

- Adopted variant: yes.
- `WORKSPACE_ROOT` is derived from `packages/shared/llm/reasoning/vibe_tools.py`.
- `_resolve_workspace_file()` rejects absolute paths and paths whose resolved
  target is outside the workspace root.
- Rejected tool calls return the guarded `Path escapes workspace root` marker
  instead of touching the requested filesystem path.
- `read_file_tool()` and `write_code_tool()` now use the resolved workspace path
  instead of opening the user-supplied string directly.

## Changed Paths

- `packages/shared/llm/reasoning/vibe_tools.py`
- `tests/test_vibe_tools_validation.py`

## Verification

- `python -m pytest tests\test_vibe_tools_validation.py -q`
  - Passed: `34`.
- `python -m py_compile packages\shared\llm\reasoning\vibe_tools.py`
  - Passed.

## Next Cycle

- Continue using the live GitHub source digest for small source-backed hardening
  slices that reduce launch risk without requiring external credentials.

## Audit Marker

- `global_objective_complete=false`
