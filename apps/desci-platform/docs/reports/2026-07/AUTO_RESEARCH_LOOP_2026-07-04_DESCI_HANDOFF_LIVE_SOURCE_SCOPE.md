# AutoResearch Loop: DeSci Handoff Live Source Scope

Date: 2026-07-04

## Objective

Continue the DeSci launch loop after the Governance wallet click-smoke recovery
by checking broader browser coverage, related GitHub systems, and the current
launch handoff path.

## Source Scan

Related GitHub projects checked:

- https://github.com/GizmoQuest/DeSciOS
  - Browser-accessible DeSci research environment with AI assistance, IPFS,
    and peer-to-peer workflow positioning.
- https://github.com/haailabs/SciDex
  - On-chain peer review system with frontend, backend, smart contracts, and
    WalletConnect/Web3 integration.
- https://github.com/replicare-desci/replicare
  - Research reproduction platform using DOI lookup, IPFS artifact storage,
    MetaMask, Web3.js, ethers, React, and RainbowKit.

Decision: do not add a UI feature in this cycle. The current DeSci browser
surface already passed the broad app-click suite, so the highest-value gap was
in the release handoff gate that decides whether launch evidence is actionable.

## Baseline Evidence

- `python scripts\browser_smoke.py --frontend http://127.0.0.1:5173 --expect-dev-auth --json-out var\browser-smoke-full-current-2026-07-04-post-governance.json --screenshot-dir var\browser-smoke-full-current-2026-07-04-post-governance-screens --trace-on-failure-dir var\browser-smoke-full-current-2026-07-04-post-governance-traces`
  - Exit code `0`.
  - Result: `61 passed`, `0 failed`.
  - Launch control remains `no-go` for required external operator values:
    `auth`, `stripe`, and `cors`.

- `python ops\scripts\desci_launch_handoff_refresh.py --live-source-commit b8bbf393759d6e67e780f03c572ec626fab6593b --check-live-source --allow-action-required --radar-json apps\desci-platform\var\github-modernization-radar-desci-handoff-refresh-2026-07-04-post-governance.json --radar-markdown-out apps\desci-platform\docs\reports\2026-07\GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_DESCI_HANDOFF_REFRESH_2026-07-04_POST_GOVERNANCE.md --status-json-out apps\desci-platform\var\auto-research-status-desci-handoff-refresh-2026-07-04-post-governance.json --status-markdown-out apps\desci-platform\docs\reports\2026-07\AUTO_RESEARCH_OPERATOR_STATUS_DESCI_HANDOFF_REFRESH_2026-07-04_POST_GOVERNANCE.md --secret-scan-json-out apps\desci-platform\var\desci-launch-secret-scan-handoff-refresh-2026-07-04-post-governance.json --bundle-json-out apps\desci-platform\var\desci-launch-handoff-refresh-2026-07-04-post-governance.json`
  - Baseline exit code `1`.
  - Veritas live source was current.
  - Secret scan was valid with `0` findings.
  - Unexpected failed check: `tracked_sources_match_live`.

## A/B Decision

Baseline behavior:

- The handoff script checked the primary Veritas live source, but passed only
  `live_source_commit` into `auto_research_status.build_status`.
- `build_status` inferred the full radar source set was checked because one
  live commit was present.
- Non-primary radar sources were therefore reported as `unavailable`, creating
  a false unexpected handoff failure.

Variant:

- Keep Veritas live-source validation enabled.
- Pass `live_sources_checked=False` from the DeSci handoff refresh path because
  this script does not fetch the whole radar source set.

Decision rule:

- Adopt only if focused tests pass and the real handoff refresh exits `0` while
  preserving expected `action_required` status for provider/preflight work.

Result: adopted.

## Verification

- `python -m py_compile ops\scripts\desci_launch_handoff_refresh.py`
  - Exit code `0`.
- `python -m pytest tests\test_desci_launch_handoff_refresh.py -q`
  - `9 passed`.
- Real handoff refresh command from the baseline section rerun after the fix:
  - Exit code `0`.
  - `status=action_required`
  - `topic=DeSci`
  - `live_source=current`
  - `secret_scan=valid`
  - `findings=0`
  - `unexpected_failed_checks=[]`
  - `failed_checks=[desci_launch_handoff_refresh_ready]`

## Current Boundary

The broad DeSci app-click surface is green and the handoff refresh no longer
fails on a false source-scope blocker. Public launch remains no-go until the
external operator supplies provider/deployment values and the provider preflight
turns green.
