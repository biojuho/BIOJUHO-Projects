# Auto Research Loop - AgriGuard Registry Label Copy

Date: 2026-07-06

## Source Refresh

- Upstream reference refresh: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Current upstream `main`: `b8bbf393759d6e67e780f03c572ec626fab6593b`
- Radar refresh:
  - `python ops/scripts/github_modernization_radar.py --json-out var/github-modernization-radar-auto-research-agriguard-continue-3-2026-07-06.json --markdown-out docs/reports/2026-07/GITHUB_SIMILAR_SYSTEMS_MODERNIZATION_AGRIGUARD_CONTINUE_3_2026-07-06.md`
  - Result: valid radar with 8 sources, 8 adopted, 0 partially adopted, 0 watch.

## Finding

The crop registry success state showed the newly created public verify label, but operators had to manually select the long label URL before printing or sharing it. The related QR token workflow already exposed a copy affordance, so the registry flow was one step behind the product surface users would expect after creating a batch.

The browser smoke also caught that the styled cold-chain checkbox could be intercepted by the decorative control during real interaction. That made the visual checkbox look correct but less reliable for automated and accessibility-driven activation.

## Change

- Added a `Copy label URL` action to the registration success card.
- The action writes the public verify label URL to `navigator.clipboard`, then changes its accessible label and visible state to `Copied`.
- Kept a fail-closed `Copy failed` state when the clipboard API is unavailable or rejects the write.
- Adjusted the custom cold-chain checkbox so the native input covers the clickable label while the decorative checkbox ignores pointer events.
- Added focused coverage for the clipboard call, copied state, accessible button label, and checkbox activation surface.

## Verification

- `npm.cmd test -- ProductRegistry.test.jsx`
  - Passed: 1 test file.
- `npx.cmd eslint src/components/ProductRegistry.jsx src/components/ProductRegistry.test.jsx`
  - Passed.
- Focused Playwright mobile registry copy smoke:
  - Evidence: `var/agriguard-registry-label-copy-mobile-2026-07-06.json`
  - Screenshot: `var/agriguard-registry-label-copy-mobile-2026-07-06.png`
  - Result: 7/7 checks passed.
  - Covered: registration success, public verify label, label URL rendering, copy button visibility, copied state, no horizontal overflow, screenshot artifact.
- Full browser smoke suite:
  - Desktop evidence: `var/agriguard-browser-smoke-suite-2026-07-06-registry-label-copy-desktop.json`
    - Result: 7/7 steps, 168/168 checks, 19/19 screenshots.
  - Mobile evidence: `var/agriguard-browser-smoke-suite-2026-07-06-registry-label-copy-mobile.json`
    - Result: 7/7 steps, 183/183 checks, 19/19 screenshots.
- Full frontend test suite:
  - `npm.cmd test -- --run`
  - Result: 18 files passed, 95 tests passed.
- Backend smoke:
  - `python -m pytest apps/AgriGuard/backend/tests/test_smoke.py -q`
  - Result: 56 passed.
- Workspace smoke:
  - `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var/workspace-smoke-agriguard-2026-07-06-registry-label-copy.json`
  - Result: complete, 5/5 passed, 0 unexpected failures.

## Remaining Launch Blocker

Strict launch readiness is still externally blocked until a real Firebase Admin service-account file is present for `AGRIGUARD_FIREBASE_SERVICE_ACCOUNT_FILE`. This change does not weaken that gate.
