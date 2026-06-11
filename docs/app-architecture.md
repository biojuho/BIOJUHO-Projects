# JooPark Workspace App Architecture

This app ships as a static, no-build SPA. `index.html` loads browser globals in a fixed order, then `app.js` orchestrates state, routing, persistence, and delegated actions.

## Runtime Loading

Initial runtime scripts in `index.html`:

`search-empty-state.js`, `home-execution-view.js`, `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, `llm-wiki-view.js`, `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js`, `workspace-storage.js`, `dashboard-storage.js`, `dashboard-prioritization.js`, `dashboard-evidence-receipts.js`, `dashboard-insights-engine.js`, `dashboard-autoresearch-loop.js`, `dashboard-view.js`, `storage-status-view.js`, `settings-view.js`, `system-status-view.js`, `backup-import-guards.js`, `backup-import-ui.js`, `dialog-shell.js`, `project-picker.js`, `global-search.js`, `command-palette.js`, `keyboard-shortcuts.js`, `interaction-setup.js`, `event-reminders.js`, `footer-clock.js`, `db-catalog.js`, `runtime-error-boundary.js`, `pwa-runtime.js`, `workspace-seed-data.js`, `home-view.js`, `ops-runtime-loader.js`, `app.js`.

Vendor scripts are local files under `vendor/` and must keep their `integrity` and `crossorigin` attributes in `index.html`.

Operational and review-only code is no longer in the initial script list. `ops-runtime-loader.js` exposes `window.JooParkOpsRuntime` and loads these files only when a gated route needs them:

`release-status.js`, `operations-copy-actions.js`, `verify-workspace-summary.js`, `review-recommendation-export.js`, `review-execution-checklist.js`, `review-issue-payload.js`, `review-result-view.js`, `review-handoff.js`, `review-artifact-view.js`, `review-package-view.js`, `review-artifact-state.js`, `review-result-draft-state.js`, `review-creation-actions.js`, `review-copy-actions.js`, `review-submission-copy.js`, `review-result-state.js`.

`app.js` owns the route gate through `OPS_RUNTIME_VIEW_GROUPS`. System routes load the release group, portfolio routes load the review group, and clipboard-only operations can load the operations group.

## Ops Runtime Diagnostics

`ops-runtime-loader.js` records loaded, pending, and failed lazy files, group-level last-load status, and bounded load events. System Status renders these as `Ops runtime diagnostics` with `loaded lazy files`, `ready groups`, release/review group rows, and failed-file details so browser smoke can prove lazy runtime readiness without parsing raw console output.

## Responsibility Map

| Surface | Primary Files | App Boundary |
| --- | --- | --- |
| Shell and search | `search-empty-state.js`, `dialog-shell.js`, `project-picker.js`, `global-search.js`, `command-palette.js`, `keyboard-shortcuts.js`, `interaction-setup.js`, `event-reminders.js`, `footer-clock.js` | topbar search, palette, shortcuts, body event delegation, notification reminders, footer clock, modal/sheet focus handling |
| Home | `workspace-seed-data.js`, `home-view.js`, `home-execution-view.js`, `dashboard-view.js`, `dashboard-insights-engine.js`, `dashboard-prioritization.js`, `dashboard-autoresearch-loop.js`, `dashboard-evidence-receipts.js`, `dashboard-storage.js` | dashboard seed data, first screen, readiness, execution queue, operational cockpit, AutoResearch loop receipts |
| Personal productivity | `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js` | calendar, todo, notes, habit, stats wrappers |
| Knowledge base | `llm-wiki-view.js` | LLM wiki browsing and draft creation wrappers |
| PM execution | `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js` | portfolio cards, Kanban, Gantt, resources |
| DB catalog | `db-catalog.js` | DB instances, schema, queries, backups |
| Persistence and import | `workspace-storage.js`, `dashboard-storage.js`, `storage-status-view.js`, `backup-import-guards.js`, `backup-import-ui.js` | localStorage v3, dashboard intelligence collections, import size/count/schema guards, storage health |
| Dashboard intelligence | `dashboard-storage.js`, `dashboard-prioritization.js`, `dashboard-evidence-receipts.js`, `dashboard-insights-engine.js`, `dashboard-autoresearch-loop.js`, `dashboard-view.js` | local dashboard records, candidate scoring, evidence receipts, insight cards, repeatable local AutoResearch loop, dashboard rendering |
| Settings and system | `settings-view.js`, `system-status-view.js`, `dashboard-view.js`, `pwa-runtime.js`, `runtime-error-boundary.js` | settings, system status, dashboard decision receipts, PWA evidence, global runtime error boundary |
| Operations runtime | `ops-runtime-loader.js`, `release-status.js`, `operations-copy-actions.js`, `verify-workspace-summary.js` | lazy release evidence, copy helpers, verify summary |
| Review runtime | `review-*.js` files listed above | lazy review handoff, issue payload, artifact, receipt, and copy flows |

## Claude Artifact Storage Compatibility

`workspace-storage.js` keeps `localStorage` v3 as the normal browser source of truth. When a Claude Artifact-style `window.storage` API exists, the same v3 payload is also mirrored to the personal key `joopark-workspace:v3` with `shared=false`; related data stays batched in that single key so persistence does not loop over many async storage calls.

On first load, if no local v2/v3 payload exists and `window.storage` is available, the app attempts one async hydration from that key before committing seeded data. Settings and System Status expose the mirror status, key, scope, last bytes, and mirror/hydration errors, while `localStorage` export/import remains the recovery and portability path.

## Action Handlers

Delegated actions stay in explicit maps. `MODAL_ACTION_HANDLERS` runs before broad app-shell handlers, followed by maps for shell, storage/settings, operations copy, operations parser, PM CRUD, DB CRUD, record opening, and view-specific actions. Keep this order intact when adding actions.

## Dashboard Intelligence

Dashboard intelligence is still no-server local state. `dashboard-autoresearch-loop.js` reads current browser data plus release/product evidence, scores candidates through `dashboard-prioritization.js`, writes bounded records through `dashboard-storage.js`, and exposes receipt text through `dashboard-evidence-receipts.js`. The persisted collections are `dashboardInsights`, `dashboardResearchLoops`, `dashboardImprovementCandidates`, `dashboardDecisionReceipts`, `dashboardEvidenceSnapshots`, and `dashboardHealthChecks`; System Status shows the latest receipt without weakening the existing `readyForExternalClaim=true` release guard.

## Generated Artifact Policy

Generated files are split by whether the static app reads them as release evidence. Tracked evidence files stay in git because `package-release.mjs`, System Status, Settings runbooks, or smoke checks read them directly. Local inventory/cache files that can be regenerated and are not required for the shipped app stay ignored.

| Artifact | Producer | Policy |
| --- | --- | --- |
| `data/repos.json` | `scripts/sync-github.sh` or manual seed refresh | Track as portfolio seed data. |
| `data/adoption-candidates.json` | candidate snapshot refresh / manual curation | Track as reference seed data; hidden by default in the UI unless `showReferenceProjects=true`. |
| `data/workflow-ui-install-plan.json` | `scripts/plan-workflow-ui-install.mjs --dry-run --write` | Track as launch workflow install evidence. |
| `data/remote-workflow-file-check.json` | `scripts/check-remote-workflow-files.mjs --write` | Track as remote workflow parity evidence. |
| `data/publish-dispatch-plan.json` | `scripts/plan-publish-dispatch.mjs --live --write` | Track as dispatch guard evidence. |
| `data/launch-execution-packet.json` | `scripts/capture-launch-execution-packet.mjs --write` | Track as operator packet evidence. |
| `data/launch-handoff-verification.json`, `data/launch-handoff-verification.md` | `scripts/verify-launch-handoff.mjs --write --markdown` | Track as launch handoff evidence. |
| `data/launch-readiness-refresh.json`, `data/launch-readiness-refresh.md` | `scripts/refresh-launch-readiness.mjs --write` | Track as consolidated readiness receipt. |
| `data/output-quality-audit.json` | `scripts/capture-output-quality-audit.mjs --write` | Track as output-quality and System Status evidence. |
| `data/publish-evidence.json` | `scripts/capture-publish-evidence.mjs --write` | Track only when it contains current guarded publish evidence; never treat it as public completion by itself. |
| `data/pages-attestation-proof.json`, `data/pages-attestation-proof.md` | `scripts/capture-pages-attestation-proof.mjs --write --markdown` | Track as optional attestation proof when captured. |
| `data/main-bridge-plan.json` | `scripts/plan-main-bridge.mjs --write` | Track as local bridge planning evidence while the release branch is active. |
| `data/github-project-discovery.json`, `data/github-project-discovery.md` | `npm run audit:github-projects` | Ignore as regenerated local inventory cache; rerun on demand before using it for decisions. |
| `autoresearch-results/verify-workspace-summary.json` | `npm run verify:full` | Track as the full verification summary shown in System Status. |
| `autoresearch-results/joopark-product-loop.json`, `autoresearch-results/joopark-product-loop.md` | `scripts/sync-product-loop-summary.mjs --write --markdown` | Track as the product-loop receipt. |
| `autoresearch-results/release-readiness-gates.json`, `autoresearch-results/release-readiness-summary.json` | `scripts/audit-release-readiness.mjs --run-gates` | Ignore as regenerated gate cache; `verify-workspace-summary.json` carries the tracked completion summary. |

## Checks

Run the structure and documentation guards together after changing runtime boundaries:

```bash
npm run check:structure
npm run check:docs
```

`npm run check:docs` reads `index.html` and `ops-runtime-loader.js`, then fails if this document omits an initial or lazy runtime file. `npm test` and CI run the same check.

## Structure Gate

`scripts/check-app-structure.mjs` is the Structure Gate for `app.js`, direct runtime helpers, and lazy operations/review helpers. The gate keeps `requiredBoundaries`, `extractionCandidates`, action handler maps, duplicate functions, oversized sections, and `maxAppLines` visible before another feature lands.

## Next Extraction Order

Next Extraction Order favors self-contained helpers first: keep `home-execution-view.js` for due/priority execution queue rendering, then continue with `dialog-shell.js` sheet/modal focus restoration, `project-picker.js` Project picker focus restoration, and `global-search.js` Global search search role affordance before moving more stateful surfaces.

## Module Migration Rule

Module Migration Rule: runtime helpers may move out of `app.js` only when `index.html`, `ops-runtime-loader.js`, `sw.js`, `scripts/package-release.mjs`, `scripts/verify-release.mjs`, `scripts/smoke-release.mjs`, and `scripts/audit-release-readiness.mjs` agree on direct versus lazy loading.

## Operations Evidence

`scripts/refresh-launch-readiness.mjs` refreshes `data/launch-readiness-refresh.json`, `data/launch-readiness-refresh.md`, and launch readiness refresh evidence without executing dispatch. Operations copy flows live in `operations-copy-actions.js` for Settings/System copy clipboard/status/dataset feedback.

`scripts/capture-github-project-discovery.mjs` refreshes `data/github-project-discovery.json` and `data/github-project-discovery.md` as a read-only inventory. The System Status helper renders this as `data-system-github-project-discovery`, and the artifact must keep `privacy.publicArtifactSafe=true`, `absoluteLocalPathExposure=false`, and `localPathMode=relative-to-local-root` because `data/` is packaged with the static release.

## Extraction Rule

Do not convert the app to browser ES modules in one jump. Continue extracting pure helpers or self-contained surfaces behind tests, then change loading strategy only after release smoke covers all routes.
