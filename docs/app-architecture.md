# JooPark Workspace App Architecture

This app intentionally ships as a static, no-build SPA. The current production file is `app.js`, but maintenance now treats it as a set of bounded surfaces instead of one undifferentiated script.

## Product Runtime

- Shell: `index.html` owns the static sidebar, topbar, modal, sheet, palette, and view containers.
- Runtime: `app.js` owns personal/PM state transitions, CRUD, import/export wrappers, search, and delegated actions. `search-empty-state.js`, `home-execution-view.js`, `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js`, `workspace-storage.js`, `storage-status-view.js`, `settings-view.js`, `system-status-view.js`, `backup-import-guards.js`, `backup-import-ui.js`, `release-status.js`, `operations-copy-actions.js`, `verify-workspace-summary.js`, `dialog-shell.js`, `project-picker.js`, `global-search.js`, `command-palette.js`, `db-catalog.js`, `review-handoff.js`, `review-result-view.js`, `review-execution-checklist.js`, `review-issue-payload.js`, `review-result-state.js`, `review-result-draft-state.js`, `review-creation-actions.js`, `review-package-view.js`, `review-artifact-view.js`, `review-artifact-state.js`, `review-copy-actions.js`, `review-submission-copy.js`, `review-recommendation-export.js`, and `pwa-runtime.js` own extracted static runtime helpers loaded before `app.js`.
- Data: `data/repos.json` and `data/adoption-candidates.json` seed portfolio and benchmark candidates.
- Release: `scripts/package-release.mjs`, `scripts/verify-release.mjs`, and `scripts/smoke-release.mjs` package and verify the static artifact. `scripts/refresh-launch-readiness.mjs` refreshes the workflow UI plan, remote workflow file check, publish dispatch plan, launch execution packet, launch handoff verifier, and output quality audit into `data/launch-readiness-refresh.json` and `data/launch-readiness-refresh.md` without running dispatch.

## App Surfaces

| Surface | Primary Code Boundary | Responsibility |
| --- | --- | --- |
| Shell utilities | top of `app.js` | Escaping, Markdown rendering, search empty-state helpers, benchmark scoring helpers |
| State and refs | `const dashboard`, `const refs` | In-memory dashboard state and DOM handles |
| Home | `home-execution-view.js` plus `View: Home` wrappers | First-run guidance, today agenda, due/priority execution queue rendering, quick todo creation, route shortcuts |
| Portfolio review | `portfolio-view.js`, `review-handoff.js`, `review-result-view.js`, `review-execution-checklist.js`, `review-issue-payload.js`, `review-result-state.js`, `review-result-draft-state.js`, `review-creation-actions.js`, `review-package-view.js`, `review-artifact-view.js`, `review-artifact-state.js`, `review-copy-actions.js`, `review-submission-copy.js`, `review-recommendation-export.js` plus `View: Portfolio` wrappers | Candidate queue, benchmark rubrics, recommendation export shells, review handoff packages, validator saved-result UI, execution checklist item/progress/body sync calculation, issue payload Decision Summary/pinned note/tracker fields, validator state/repair receipt side effects, issue-sheet checklist controls, GitHub comment Markdown/draft controls, GitHub comment copy state, issue draft assignee override DOM/dataset mutation, review issue/note creation mutations, artifact receipts, post-repair artifact link receipts, fresh receipt controls, receipt compare/repair UI, copy status/dataset feedback, project list semantics |
| PM execution | `kanban-view.js`, `gantt-view.js`, `team-view.js`, plus `View: Kanban`/`View: Gantt`/`View: Team / Resources` wrappers | Issues, Kanban lane/card rendering, accessible Gantt milestones/bars, team load, resource matrix semantics, execution checklists |
| DB catalog | `db-catalog.js` plus thin `app.js` wrappers | Local DB documentation, provenance boundary, view rendering, query and migration records, modal-backed DB CRUD |
| Settings/System | `settings-view.js`, `system-status-view.js`, `storage-status-view.js`, `operations-copy-actions.js`, `release-status.js`, `verify-workspace-summary.js` plus thin Settings/System wrappers | Settings KPI/profile/theme/backup rendering, System KPI/operational/source snapshot rendering, storage health rendering, privacy/deploy handoff, publish readiness, launch readiness refresh evidence, full verify summary loading/validation, copy clipboard/status/dataset feedback |
| Dialog shell | `dialog-shell.js` plus thin sheet/modal wrappers | Shared sheet/modal open-close, body lock, notification expanded state, focus restoration, and tab trapping |
| Project picker | `project-picker.js` plus thin picker wrappers | Project picker scaffold, option rendering, search status, body lock, and focus restoration |
| Global search | `global-search.js` plus thin search wrappers | Topbar current-view search, search role affordance, clear recovery, no-results reveal, and search-inert command palette fallback |
| Persistence/import | `workspace-storage.js`, `persist`, `loadPersisted`, `backup-import-guards.js`, `backup-import-ui.js` | localStorage v3 persistence, v2 migration, storage health data, import application, import size/count/shape guards, destructive confirmation, normalization |
| Personal views | `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, Calendar/Todo/Notes/Habits/Stats wrappers | Personal productivity flows, Calendar month/agenda rendering, Todo KPI/filter/list rendering, Notes card/Markdown preview rendering, Habits weekly/streak rendering, accessible Stats chart rendering, and analytics |
| Routing/actions | `VIEWS`, `renderCurrentView`, `handleActions` | Hash routing and delegated event handling |
| CRUD | `PM CRUD`, `DB CRUD` | Modal-backed create/edit/delete operations |
| Command palette | `command-palette.js` plus thin `app.js` wrappers | Global search, commands, shortcuts, startup coordination |
| Review handoff | `review-handoff.js`, `review-result-view.js`, `review-execution-checklist.js`, `review-issue-payload.js`, `review-result-state.js`, `review-result-draft-state.js`, `review-creation-actions.js`, `review-package-view.js`, `review-artifact-view.js`, `review-artifact-state.js`, `review-copy-actions.js`, `review-submission-copy.js`, `review-recommendation-export.js` plus thin `app.js` wrappers | AI prompt contract, package manifest, bundle export, recommendation export rendering, review package shell composition, result validator saved-card/output rendering, execution checklist item/progress/body sync calculation, Decision Summary/body payload/pinned note/tracker fields, validator state mutation, repair snapshots, post-repair receipt attachment, validated issue/note body rendering, issue-sheet checklist rendering, GitHub comment Markdown/draft rendering, GitHub comment copy state, issue draft node lookup, assignee override DOM/dataset mutation, created issue/note mutation, assignee follow-up presentation, artifact diff/receipt rendering, artifact receipt compare state, archived-body repair preview/apply/undo, post-repair artifact link rendering, fresh receipt rendering, copy clipboard/status/dataset feedback, JSON result parser, and result shape validation |
| PWA runtime | `pwa-runtime.js` plus thin `app.js` wrappers | Service worker registration, service worker/cache/manifest/standalone/online runtime inspection, and System Status PWA evidence updates |

## Structure Gate

Run:

```bash
npm run check:structure
```

The gate reports:

- required product boundaries and the terms that prove each exists,
- line-count thresholds for `app.js`, sections, and functions,
- duplicate function declarations,
- oversized sections/functions that should be split before adding new work,
- extraction candidates for future module migration.

Warnings do not block release yet; failures do. This keeps the current static app stable while preventing accidental loss of major product boundaries.

## Next Extraction Order

1. Completed runtime helpers: `search-empty-state.js`, `home-execution-view.js`, `calendar-view.js`, `todo-view.js`, `notes-view.js`, `habits-view.js`, `stats-view.js`, `portfolio-view.js`, `kanban-view.js`, `gantt-view.js`, `team-view.js`, `workspace-storage.js`, `storage-status-view.js`, `settings-view.js`, `system-status-view.js`, `backup-import-guards.js`, `backup-import-ui.js`, `release-status.js`, `operations-copy-actions.js`, `verify-workspace-summary.js`, `dialog-shell.js`, `project-picker.js`, `global-search.js`, `command-palette.js`, `db-catalog.js`, `review-handoff.js`, `review-result-view.js`, `review-execution-checklist.js`, `review-issue-payload.js`, `review-result-state.js`, `review-result-draft-state.js`, `review-creation-actions.js`, `review-package-view.js`, `review-artifact-view.js`, `review-artifact-state.js`, `review-copy-actions.js`, `review-submission-copy.js`, `review-recommendation-export.js`, and `pwa-runtime.js`.
2. Next extraction target: split the next stateful review mutation surface only after release smoke coverage stays green.

## Module Migration Rule

Do not convert `app.js` to browser ES modules in one jump. First extract pure helpers or self-contained surfaces behind tests, then switch `index.html` to module loading only when release smoke covers all routes. Browser modules are a good long-term fit for this static app, but the release path depends on local static hosting rather than `file://` execution.
