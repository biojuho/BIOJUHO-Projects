# AutoResearch Dev-Server Operator Runbook - 2026-06-04

## Outcome

The manifest-backed dev-server workflow now has a concise operator guide at `docs/guides/dev-server-control.md`, linked from `docs/QUALITY_GATE.md`.

## Added Coverage

- Manifest validation command.
- Live status commands for all targets and selected stacks.
- Dependency-aware frontend start examples for dashboard, DeSci, AgriGuard, and Canva preview.
- Log tail command.
- Grouped stop command with `--include-dependencies`.
- Browser QA evidence checklist.
- Current target id inventory.

## Verification

- `python -m pytest tests\test_workspace_smoke.py::test_quality_gate_documents_default_check_names -q -p no:cacheprovider` -> PASS

## Boundary

This is an operator handoff/documentation improvement only. Runtime grouped stop behavior was already covered by the dev-server group-stop cycle.
