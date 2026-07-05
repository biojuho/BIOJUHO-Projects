# AutoResearch Loop: AgriGuard Registry Mobile Submit

Date: 2026-07-05

## Source Check

- Skill used: `AutoResearch Karpathy Loop`
- External pattern check: `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git HEAD refs/heads/main`
- Verified source revision: `b8bbf393759d6e67e780f03c572ec626fab6593b`

## Target

The Crop Registry form rendered without overflow, but the submit action was below the first mobile viewport. On a 390 x 844 viewport, the `Register Harvest` button started at y=895.

## A/B Result

Baseline, before variant:

- Viewport: `390 x 844`
- Page width: `scrollWidth=390`
- Description field: `top=737`, `bottom=865`, `height=128`
- Submit button: `top=895`, `bottom=935`, `height=40`
- Submit visible in first viewport: `false`

Variant, after compact mobile form spacing:

- Viewport: `390 x 844`
- Page width: `scrollWidth=390`
- Registry card: `top=192`, `bottom=832`, `height=640`
- Description field: `top=657`, `bottom=753`, `height=96`
- Submit button: `top=775`, `bottom=815`, `height=40`
- Submit visible in first viewport: `true`
- Submit fully visible in first viewport: `true`
- Horizontal overflow: `false`

The submit action moved upward by 120 px and is now fully visible with all fields in the first mobile viewport.

## Implementation

- Changed Registry page spacing to mobile-first `space-y-5`.
- Reduced card padding on mobile and restored desktop padding at `sm`.
- Reduced mobile form gaps while preserving desktop gaps.
- Reduced mobile input vertical padding and textarea height.
- Added focused unit assertions for the mobile form spacing contract.

## Evidence

- Focused test: `npm.cmd run test -- ProductRegistry`
  - Result: `1 passed`, `1 passed`
- Measurement screenshot: `var\agriguard-registry-mobile-compact-submit\registry-compact-submit.png`
- Mobile browser suite: `python apps/AgriGuard/scripts/run_browser_smoke_suite.py --base-url http://127.0.0.1:5176 --api-url http://127.0.0.1:8002 --mobile --json-out var\agriguard-browser-smoke-suite-registry-mobile-compact-submit.json --output-dir var\agriguard-browser-smoke-suite-registry-mobile-compact-submit --timeout-ms 30000`
  - Result: `6 / 6` steps, `135 / 135` checks, `18 / 18` screenshots
- AgriGuard smoke: `python ops/scripts/run_workspace_smoke.py --scope agriguard --json-out var\workspace-smoke-agriguard-registry-mobile-compact-submit.json`
  - Result: `5 / 5`
- Workspace smoke: `python ops/scripts/run_workspace_smoke.py --scope workspace --json-out var\workspace-smoke-registry-mobile-compact-submit.json`
  - Result: `9 / 9`

## Remaining External Blocker

This loop improves local launch readiness. Protected production operator paths still require the real Firebase Admin/service-account/operator token configuration before a production launch can be called complete.
