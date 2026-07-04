# AutoResearch Loop: DeSci Handoff Clean Checkout Fallback

Date: 2026-07-04

## Objective

Continue DeSci launch hardening after the release-handoff auto-discovery fix by
checking whether the tracked handoff refresh can run from a clean checkout.

## Scope

Owned paths changed in this cycle:

- `ops/scripts/desci_launch_handoff_refresh.py`
- `tests/test_desci_launch_handoff_refresh.py`

Generated evidence was left in `apps/desci-platform/var/` and not staged.

## External Source Check

- `Veritas-7/autoresearch-skill-system`
  - `HEAD`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
  - `refs/heads/main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`

The adopted pattern remains bounded, source-backed improvement: validate the
actual gate, adopt only after focused tests and product smoke pass, and keep
provider/auth blockers classified as external.

## Baseline

Current worktree evidence showed:

- `ops/scripts/desci_launch_handoff_refresh.py` was tracked.
- `ops/scripts/auto_research_status.py` was not tracked.
- `ops/scripts/desci_launch_secret_scan.py` was not tracked.

That meant a clean checkout could import the tracked handoff refresh script but
miss helper modules that were only present as local scratch files.

A real refresh with a fresh radar artifact also exposed a DeSci-specific topic
edge case:

- Command:
  - `python ops\scripts\desci_launch_handoff_refresh.py --live-source-commit b8bbf393759d6e67e780f03c572ec626fab6593b --check-live-source --allow-action-required --radar-json apps\desci-platform\var\github-modernization-radar-clean-checkout-fallback-2026-07-04.json --radar-markdown-out apps\desci-platform\docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_CLEAN_CHECKOUT_FALLBACK_2026-07-04.md --status-json-out apps\desci-platform\var\auto-research-status-desci-clean-checkout-fallback-2026-07-04.json --status-markdown-out apps\desci-platform\docs\reports\2026-07\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_CLEAN_CHECKOUT_FALLBACK_2026-07-04.md --secret-scan-json-out apps\desci-platform\var\desci-launch-secret-scan-clean-checkout-fallback-2026-07-04.json --bundle-json-out apps\desci-platform\var\desci-launch-handoff-refresh-clean-checkout-fallback-2026-07-04.json`
- Baseline result:
  - Exit code `1`.
  - `status=ok`
  - `topic=`
  - `live_source=current`
  - `secret_scan=valid`
  - `release_handoff=valid`
  - `provider_preflight=False`

The failed bundle had `topic_ok=false` even though the script is explicitly the
DeSci launch handoff refresh.

## A/B Decision

Variant:

- Keep using `auto_research_status.py` and `desci_launch_secret_scan.py` when
  they are present.
- Add tracked fallback implementations for:
  - minimal DeSci status generation,
  - Veritas live commit lookup,
  - Markdown status output,
  - DeSci launch-handoff secret scanning.
- Default only a blank status topic to `DeSci`; a non-DeSci topic still fails
  closed.

Decision rule:

- Adopt only if the clean-helper-missing test passes, the blank-topic test
  passes, the real handoff refresh exits `0`, launch-click smoke remains green,
  and the DeSci workspace smoke remains green.

Result: adopted.

## Verification

- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py`
  - Exit code `0`.
- `python -m pytest tests\test_desci_launch_handoff_refresh.py -q`
  - `12 passed`.
- Real handoff refresh command from the baseline section rerun after the fix:
  - Exit code `0`.
  - `status=ok`
  - `topic=DeSci`
  - `live_source=current`
  - `secret_scan=valid`
  - `findings=0`
  - `missing=0`
  - `release_handoff=valid`
  - `provider_preflight=False`
- Direct launch-click smoke:
  - `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --launch-click-suite --json-out var\browser-smoke-launch-click-clean-checkout-fallback-2026-07-04.json --screenshot-dir var\browser-smoke-launch-click-clean-checkout-fallback-2026-07-04-screens --trace-on-failure-dir var\browser-smoke-launch-click-clean-checkout-fallback-2026-07-04-traces`
  - Exit code `0`.
  - `44 passed`, `0 failed`.
- DeSci workspace smoke:
  - `python ops\scripts\run_workspace_smoke.py --scope desci --json-out apps\desci-platform\var\workspace-smoke-desci-clean-checkout-fallback-2026-07-04.json`
  - Exit code `0`.
  - `8 passed`, `0 failed`.

## Current Boundary

The tracked DeSci handoff refresh no longer depends on untracked local helper
files for clean-checkout operation. The launch handoff now reaches the real
current boundary: provider preflight remains false because external provider
auth/config context is missing, while app-click and local DeSci smoke are green.
