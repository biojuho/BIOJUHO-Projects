# AutoResearch GetDayTrends Lock Path Override

## Objective

Adopt the strongest local analogue from the current `crewAIInc/crewAI` lock-store
signal without widening getdaytrends runtime behavior beyond its process
lockfile boundary.

## Source Signal

- Repository: `crewAIInc/crewAI`
- Source page: `https://github.com/crewAIInc/crewAI/commits/main/`
- Source commit: `https://github.com/crewAIInc/crewAI/commit/f3a15a4`
- Upstream signal: `feat(lock_store): make locking backend overridable (#6015)`
- Local mapping: keep the default getdaytrends file lock unchanged, but allow an
  operator or test harness to choose a lock path explicitly with
  `GETDAYTRENDS_LOCK_FILE`.

## A/B Contract

- Baseline: `_acquire_lock()` and `_release_lock()` always used the module-level
  `_LOCK_FILE`, so alternate scheduler/worktree runs had to monkeypatch source
  state or share the default `data/getdaytrends.lock`.
- Variant: `_get_lock_file()` resolves `GETDAYTRENDS_LOCK_FILE` once per
  acquire/release call and falls back to `_LOCK_FILE` when the env value is
  absent or blank.
- Primary KPI: an operator can isolate a lockfile path for a specific runtime
  without changing source or weakening the duplicate-run guard.
- Guardrails: default behavior stays compatible with existing `_LOCK_FILE`
  monkeypatch tests, blank env values fall back to the configured default, and
  release removes only the lock owned by the current process.
- Decision: adopted. The variant gives getdaytrends the needed operational
  override while preserving the existing single-process lock semantics.

## Changed Files

- `automation/getdaytrends/main.py`
  - Added `_get_lock_file()`.
  - Updated `_acquire_lock()` and `_release_lock()` to use the resolved lock path.
- `automation/getdaytrends/tests/test_main.py`
  - Added `test_lock_file_env_override_controls_acquire_and_release`.
  - Added `test_blank_lock_file_env_uses_configured_default`.

## Verification

- `python -m pytest automation\getdaytrends\tests\test_main.py -q --tb=line`
  - `11 passed`
- `python ops\scripts\run_workspace_smoke.py --scope getdaytrends --json-out var\workspace-smoke-getdaytrends-lock-path-override-2026-06-05.json`
  - `passed=2`
  - `failed=0`
  - `total=2`
- `current_tip_freshness_gate`
  - proof baseline: `0cd7ad0`
  - allowed post-proof paths include `automation/getdaytrends/main.py` and
    `automation/getdaytrends/tests/test_main.py`
- `protected_path_freshness`
  - proof baseline: `0cd7ad0`
  - no changed protected paths after proof
- `global_objective_complete=false`

## Remaining Boundary

This cycle hardens getdaytrends lock configurability only. It does not complete
credential-gated Canva/GitHub/Telegram/OTLP/hosted-runtime launch blockers, and
the broader AutoResearch loop remains open until the user explicitly stops it.
