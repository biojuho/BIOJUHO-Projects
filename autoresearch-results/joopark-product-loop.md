# JooPark Product AutoResearch Loop

Generated: 2026-06-05T20:27:13+09:00

## Experiment: autoresearch ecosystem launch data

- Hypothesis: Adding current AutoResearch ecosystem repositories to the project seed data improves launch readiness for an AutoResearch-based product without regressing the static SPA release gates.
- Primary metric: AutoResearch-related adoption candidates in `data/adoption-candidates.json`.
- Baseline: 14 total adoption candidates, 0 AutoResearch candidates.
- Candidate: 24 total adoption candidates, 10 AutoResearch candidates.
- Decision: keep.

## Evidence

- External/GitHub discovery included `karpathy/autoresearch`, `Veritas-7/autoresearch-skill-system`, `biojuho/autoresearch-skill-system`, Codex/Claude skill variants, MLX/WebGPU/Playwright adjacent projects, and awesome-list trackers.
- `node scripts/audit-release-readiness.mjs --run-gates` passed with 10 AutoResearch candidates in the packaged release data.
- Computer Use manual check opened `http://127.0.0.1:5178/#pm-portfolio`, searched `autoresearch`, rendered the filtered candidate cards, and opened the `Veritas-7/autoresearch-skill-system` detail panel.
- `python3 -m unittest discover -s tests` in `autoresearch-skill-system` passed 263 tests.
- `python3 .agents/skills/autoresearch/scripts/autoresearch_validate.py --project-root .` passed in `autoresearch-skill-system`.

## Next Loop

- Continue with the highest-impact product gap after the next full gate: publish/remote state, direct launch packaging, or deeper UI workflow coverage.

## Experiment: release audit coverage for AutoResearch launch data

- Hypothesis: The release audit should fail if the AutoResearch ecosystem candidate set is missing or too thin.
- Primary metric: Release-audit requirement coverage for AutoResearch launch data.
- Baseline: 9 release-audit checks, no explicit AutoResearch ecosystem data check.
- Candidate: 11 release-audit checks, including `autoresearch_ecosystem_candidates`.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now requires at least 8 AutoResearch-related candidates and the specific `karpathy/autoresearch`, `Veritas-7/autoresearch-skill-system`, and `biojuho/autoresearch-skill-system` entries.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 11/11 checks.
- The latest packaged release still passed route, mobile, interaction, and accessibility smoke checks.

## Remote Sync Note

- Added and fetched `veritas` remote for `https://github.com/Veritas-7/autoresearch-skill-system.git`.
- Latest observed `veritas/main`: `cc8a207` (`v8.313 Versioned Core Fence Parser`, 2026-06-05T09:50:47Z).
- Local fallback branch and `veritas/main` are divergent, so direct merge is not adopted.
- Generated `autoresearch-skill-system/autoresearch-results/veritas-main-port-plan.json`; status `ready`, 83 planned create actions, 0 blockers.

## Experiment: storage health surface

- Hypothesis: A local-first workspace should expose browser storage pressure before users hit localStorage quota or persistence failures.
- Primary metric: release audit requirement coverage.
- Baseline: `node scripts/audit-release-readiness.mjs --run-gates` passed 9/9 checks, but had no storage quota/persistence requirement.
- Candidate: settings UI shows local payload bytes, StorageManager quota estimate, usage percent, persistence state, refresh, and persistence request; interaction smoke verifies the panel.
- Decision: keep.

## Evidence

- `node --check app.js` and `node --check scripts/smoke-interactions.mjs` passed.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 10/10 after the candidate.

## Experiment: owned GitHub repository snapshot refresh

- Hypothesis: Refreshing the local GitHub seed from authenticated GraphQL improves project coverage and makes the workspace reflect current owned projects.
- Primary metric: owned GitHub repositories in `data/repos.json`.
- Baseline: 12 projects, generated `2026-06-04T09:28:03+00:00`.
- Candidate: 14 projects, generated `2026-06-05T09:50:52+00:00`, adding `health-match` and `autoresearch-skill-system`.
- Decision: keep.

## Evidence

- `./scripts/sync-github.sh` wrote 14 projects with `mode=graphql`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 11/11 after the sync.

## Experiment: compatible vendored OSS freshness

- Hypothesis: Updating compatible vendored Markdown/XSS libraries improves dependency freshness without adding a build step or CDN runtime dependency.
- Primary metric: compatible outdated vendored libraries.
- Baseline: marked `18.0.4`, DOMPurify `3.4.7`; Fuse.js stayed pinned at `6.6.2` because the checked Fuse.js `7.4.1` UMD path returns 404 for the current classic `<script>` loading model.
- Candidate: marked `18.0.5`, DOMPurify `3.4.8`, README/vendor license table updated, and audit checks added for the refreshed versions.
- Decision: keep.

## Evidence

- Local VM load check found `Fuse` as a function, `marked.parse` as a function, and `DOMPurify.version` as `3.4.8`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 12/12.

## Experiment: release source provenance

- Hypothesis: A launch package should be traceable to the exact branch, commit, and dirty working-tree paths used to build it.
- Primary metric: release manifest source provenance fields.
- Baseline: `release-manifest.json` had 5 top-level keys and only `sourceCommit`; dirty working-tree state was not represented.
- Candidate: `release-manifest.json` has `source.commit`, `source.branch`, `source.dirty`, and `source.dirtyFiles`, while keeping `sourceCommit` for compatibility.
- Decision: keep.

## Evidence

- `node scripts/package-release.mjs` writes `source` metadata and release notes now show source commit, branch, and dirty/clean state.
- `node scripts/verify-release.mjs` now fails if source metadata is missing or inconsistent.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 13/13 with `release_source_provenance` included.
- Computer Use manual check opened `http://127.0.0.1:5178/#settings`, confirmed the settings screen rendered, and clicked storage status refresh successfully.
- `python3 -m unittest discover -s tests` in `autoresearch-skill-system` passed 263 tests.

## Experiment: explicit note Markdown sanitizer smoke

- Hypothesis: After updating marked/DOMPurify, the browser smoke should prove both Markdown rendering and unsafe HTML sanitization, not only note persistence.
- Primary metric: explicit Markdown security checks in interaction smoke output.
- Baseline: 0 explicit security result fields; note persistence was checked but sanitizer behavior was only implied by implementation markers.
- Candidate: interaction smoke injects strong Markdown plus unsafe `script`, `onclick`, and `javascript:` link payloads, then reports `persistedChecks.markdownSanitized: true`.
- Decision: keep.

## Evidence

- `node --check scripts/smoke-interactions.mjs` and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 13/13.
- Packaged interaction evidence included `markdownSanitized: true`, with 0 console and network issues.

## Publish Result

- Committed the accepted product launch hardening changes as `3b48ed5 Harden JooPark launch readiness`.
- Pushed `3b48ed5` to `biojuho-projects/codex/joopark-workspace-release`.
- Draft PR creation was blocked because `codex/joopark-workspace-release` has no common history with repository `main`.

## Experiment: publish branch sync audit

- Hypothesis: Release readiness should not claim publish completion when the current branch is ahead, behind, gone, diverged, or not tracking a remote branch.
- Primary metric: publish-state audit coverage.
- Baseline: the audit checked only that a Git remote exists.
- Candidate: audit also checks the current branch tracking line and blocks `ahead`, `behind`, `gone`, or `diverged` states.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now includes `publish_branch_sync`.
- The branch was pushed to `biojuho-projects/codex/joopark-workspace-release`, so the branch sync check can pass after this evidence commit is pushed.

## Experiment: local-first workspace ecosystem candidates

- Hypothesis: Product launch readiness improves when the adoption data covers local-first workspace, AI workspace, developer dashboard, task, Kanban, and calendar projects beyond AutoResearch-only candidates.
- Primary metric: workspace-related adoption candidates in `data/adoption-candidates.json`.
- Baseline: 24 total candidates, 0 explicitly source-marked local-first workspace discovery candidates.
- Candidate: 32 total candidates, 8 local-first workspace discovery candidates, with `EpicenterHQ/epicenter`, `OpenLoaf/OpenLoaf`, and `happybhati/workstream` required by the release audit.
- Decision: keep.

## Evidence

- `data/adoption-candidates.json` now includes the `github-search:local-first-workspace` source marker.
- `scripts/audit-release-readiness.mjs` now includes `workspace_ecosystem_candidates`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 20/20 with 8 workspace candidates.

## Experiment: workspace candidate UI smoke

- Hypothesis: Workspace discovery data should be proven in the actual portfolio UI, not only by JSON seed and static audit checks.
- Primary metric: interaction-smoke evidence for imported workspace candidate search.
- Baseline: no automated UI smoke checked that an imported workspace candidate was visible and searchable in the portfolio.
- Candidate: `scripts/smoke-interactions.mjs` searches `OpenLoaf`, verifies one portfolio card, and reports `persistedChecks.workspaceCandidateVisible: true`; the release audit now includes `workspace_candidate_ui_smoke`.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed with `workspace candidate portfolio search`, `workspaceCandidateVisible: true`, and 18 interaction steps.
- `scripts/audit-release-readiness.mjs` now checks for the workspace candidate UI smoke markers before passing release readiness.

## Experiment: workspace candidate triage meta

- Hypothesis: Imported adoption candidates are easier to evaluate when portfolio cards expose adoption stage, stars, forks, language, and a safe repository link directly in the card.
- Primary metric: candidate triage metadata audit coverage.
- Baseline: workspace candidate cards were searchable but did not show triage metadata or safe GitHub links.
- Candidate: adoption-candidate cards render stage, stars, forks, language, and sanitized GitHub links; interaction smoke asserts the `OpenLoaf/OpenLoaf` values.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed after checking `OpenLoaf` stage, stars, forks, language, and safe GitHub link in the packaged interaction smoke.
- `scripts/audit-release-readiness.mjs` now includes `workspace_candidate_triage_meta`.

## Experiment: portfolio candidate filter

- Hypothesis: Once adoption candidates are added, operators need to separate owned projects from candidate projects without relying only on search.
- Primary metric: portfolio candidate-filter smoke coverage.
- Baseline: the portfolio listed owned and adoption-candidate projects together with no explicit segmented filter.
- Candidate: the portfolio adds `전체`, `운영 프로젝트`, and `도입 후보` segmented filters; interaction smoke verifies candidate-only, owned-only, and all-project recovery states.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed with `persistedChecks.portfolioCandidateFilter: true`.
- `scripts/audit-release-readiness.mjs` now includes `portfolio_candidate_filter`.

## Experiment: portfolio candidate ranking

- Hypothesis: Candidate filtering becomes more useful when the candidate-only view sorts by a metadata-based priority score instead of only showing raw project cards.
- Primary metric: portfolio candidate ranking smoke coverage.
- Baseline: candidate cards exposed metadata, but the candidate-only view did not compute or verify an ordered priority list.
- Candidate: adoption candidates receive a local priority score from stage, recent activity, stars/forks, health, and risks; candidate-only portfolio view sorts by score; interaction smoke verifies the highest-priority candidate appears first.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed with `persistedChecks.portfolioCandidateRanked: true`.
- `scripts/audit-release-readiness.mjs` now includes `portfolio_candidate_ranking`.

## Experiment: release smoke isolated output

- Hypothesis: The release audit should test a fresh package without deleting or rewriting the shared `dist/release` directory.
- Primary metric: release smoke temp-output audit checks.
- Baseline: 0 explicit audit checks requiring packaged browser gates to use isolated release output.
- Candidate: `package-release.mjs` and `smoke-release.mjs` honor `RELEASE_OUT_DIR`, and `audit-release-readiness.mjs --run-gates` runs packaged browser gates in a temporary release directory with an explicit `release_smoke_temp_output` checklist item.
- Decision: keep.

## Evidence

- `node --check scripts/package-release.mjs`, `node --check scripts/smoke-release.mjs`, and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 20/20, with packaged browser gates served from `RELEASE_OUT_DIR=<temp>`.
- The final gate still had 15 desktop routes, 15 mobile routes, 18 interaction steps, `markdownSanitized: true`, `workspaceCandidateVisible: true`, `portfolioCandidateFilter: true`, `portfolioCandidateRanked: true`, candidate triage metadata checks, and 0 console, network, and layout issues.

## Experiment: workspace benchmark candidate refresh

- Hypothesis: The workspace product loop improves when benchmark candidates include current local-first and project-management systems with live GitHub metadata, not only earlier manual discovery rows.
- Primary metric: workspace-related adoption candidates in `data/adoption-candidates.json`.
- Baseline: 32 total adoption candidates, 8 workspace candidates.
- Candidate: 38 total adoption candidates, 14 workspace candidates, adding `colanode/colanode`, `anyproto/anytype-ts`, `opf/openproject`, `ParabolInc/parabol`, `Leantime/leantime`, and `Worklenz/worklenz`.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed 21/21 with 52 projects loaded in the packaged interaction smoke, `workspaceCompetitiveCandidateVisible: true`, and `portfolioCandidateRanked: true`.
- `scripts/audit-release-readiness.mjs` now requires the `github-api:workspace-benchmark-refresh` source marker and adds `workspace_competitive_candidate_smoke`.
- `scripts/smoke-interactions.mjs` searches `colanode`, verifies category/description, stars, forks, language, and safe GitHub link rendering.
- External sources checked: `https://github.com/colanode/colanode`, `https://github.com/anyproto/anytype-ts`, `https://github.com/opf/openproject`, `https://github.com/ParabolInc/parabol`, `https://github.com/Leantime/leantime`, and `https://github.com/Worklenz/worklenz`.

## Experiment: portfolio candidate next action

- Hypothesis: Candidate cards become more useful when they recommend the next review action instead of only showing score and metadata.
- Primary metric: `candidateNextActionVisible` in packaged interaction smoke.
- Baseline: candidate cards showed priority, stage, stars, forks, language, and safe GitHub links, but no next-action recommendation.
- Candidate: adoption candidates now receive deterministic action chips such as `아키텍처 벤치`, `PM 벤치`, `리스크 리뷰`, `스파이크`, or `월간 관찰`, derived from source availability, priority, risks, issues, category, and topics.
- Decision: keep.

## Evidence

- External source signals used: Colanode documents local SQLite + Yjs + kanban/calendar workspace patterns, Anytype documents offline-first/P2P blocks with kanban/calendar, and OpenProject documents planning, roadmap, Gantt, boards, and GitHub-linked work packages.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 22/22.
- Packaged interaction smoke reported `candidateNextActionVisible: true`, `workspaceCompetitiveCandidateVisible: true`, and `portfolioCandidateRanked: true`.
- `scripts/smoke-interactions.mjs` verifies Colanode renders `아키텍처 벤치` with `로컬 퍼스트 구조`, and verifies OpenProject computes `리스크 리뷰`.

## Experiment: portfolio candidate action filter

- Hypothesis: Once candidates have next-action recommendations, the portfolio should let operators narrow the candidate queue by those actions instead of scanning every card.
- Primary metric: `candidateActionFilter` in packaged interaction smoke.
- Baseline: candidate cards showed action chips, but the portfolio could not filter by action type.
- Candidate: a candidate action segmented filter narrows the queue by `스파이크`, `아키텍처 벤치`, `PM 벤치`, `리스크 리뷰`, `일정 UX 벤치`, `월간 관찰`, `기능 검토`, or `소스 보강`; selecting an action also keeps the portfolio in candidate mode.
- Decision: keep.

## Evidence

- External source signals used: Linear documents filters across nearly every view and a Triage inbox for review/prioritization, while OpenProject documents work package views as filter-based lists and table configurations.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 23/23.
- Packaged interaction smoke reported `candidateActionFilter: true`, `candidateNextActionVisible: true`, and `portfolioCandidateRanked: true`.
- `scripts/smoke-interactions.mjs` verifies the architecture filter keeps Colanode visible and the risk filter keeps OpenProject visible.

## Experiment: portfolio candidate action summary

- Hypothesis: Selected action queues are easier to act on when the UI shows the matching count, top candidate, top reason, and risk count near the action filter.
- Primary metric: `candidateActionSummaryVisible` in packaged interaction smoke.
- Baseline: the action filter narrowed candidate cards, but operators had no queue summary for the selected next action.
- Candidate: the selected action queue renders a compact summary with the action label, queue count, top candidate, top priority reason, and risk count.
- Decision: keep.

## Evidence

- External source signals used: Linear filter and triage patterns, plus OpenProject filtered work package views, support keeping filtered queues visible with review context.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 24/24.
- Packaged interaction smoke reported `candidateActionSummaryVisible: true`.
- `scripts/smoke-interactions.mjs` verifies the architecture summary shows `colanode/colanode` and `로컬 퍼스트 구조`, and the risk summary shows `리스크 리뷰`.
- External sources checked: `https://linear.app/docs/filters`, `https://linear.app/docs/triage`, and `https://www.openproject.org/docs/user-guide/work-packages`.

## Experiment: standalone deploy support files

- Hypothesis: The release artifact is more publishable if the package includes host-specific static deployment support files and the verifier rejects missing or malformed deployment metadata.
- Primary metric: `standaloneDeploySupportFiles`.
- Baseline: `dist/release` had 0 of the target static-host support files: `404.html`, `_headers`, `_redirects`, and `vercel.json`.
- Candidate: `scripts/package-release.mjs` generates all 4 files, and `scripts/verify-release.mjs` validates GitHub Pages 404 fallback, Netlify headers/redirects, and Vercel header configuration.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages documents `404.html` custom pages, Netlify documents `_headers` and `_redirects` files in the publish directory, and Vercel documents project configuration through `vercel.json` headers.
- `node scripts/package-release.mjs && node scripts/verify-release.mjs` passed with `files: 15`, `bytes: 557204`, and `deploySupportFiles: 4`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 25/25.
- Packaged browser gates still reported 15 desktop routes, 15 mobile routes, 18 interaction steps, 0 console/network/layout failures, and `candidateActionSummaryVisible: true`.
- External sources checked: `https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-custom-404-page-for-your-github-pages-site`, `https://docs.netlify.com/manage/routing/headers/`, `https://docs.netlify.com/routing/redirects/`, and `https://vercel.com/docs/project-configuration/vercel-json`.

## Experiment: release host header smoke

- Hypothesis: Deployment header support is stronger if the packaged-release smoke serves `_headers` locally and proves the configured security/cache headers over HTTP.
- Primary metric: `releaseHeaderSmokeChecks`.
- Baseline: `scripts/smoke-release.mjs` had 0 explicit HTTP header checks.
- Candidate: the release smoke parses `_headers`, applies matching rules in its temporary server, and verifies 6 headers: root content-type, frame, referrer, permissions, app no-cache, and vendor immutable cache.
- Decision: keep.

## Evidence

- External source signals used: Netlify documents `_headers` syntax in the publish directory and Vercel documents equivalent `vercel.json` headers, so local smoke should verify the same intended response behavior before upload.
- `node scripts/smoke-release.mjs` passed with `headers.status: pass` and all 6 header checks true.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 26/26 with `release_header_smoke`.
- Packaged browser gates still reported 15 desktop routes, 15 mobile routes, 18 interaction steps, 0 console/network/layout failures, and `candidateActionSummaryVisible: true`.

## Experiment: release direct-path fallback smoke

- Hypothesis: Static deployment readiness is stronger if the package uses a Netlify `200` rewrite for direct paths and the packaged-release smoke proves both the rewrite and GitHub Pages `404.html` app-shell fallback over HTTP.
- Primary metric: `releaseFallbackSmokeChecks`.
- Baseline: `scripts/smoke-release.mjs` had 0 explicit fallback checks, and `_redirects` used a temporary root redirect.
- Candidate: `_redirects` now uses `/* /index.html 200`; `scripts/smoke-release.mjs` parses redirect rules and verifies 4 fallback checks for direct path rewrite, no redirect `Location`, `404.html` matching the app shell, and HTML content type.
- Decision: keep.

## Evidence

- External source signals used: Netlify documents `200` status redirects as rewrites that keep the browser URL, and GitHub Pages documents `404.html` as the custom missing-page file.
- `node scripts/package-release.mjs && node scripts/verify-release.mjs && node scripts/smoke-release.mjs` passed with `fallbacks.status: pass` and all 4 fallback checks true.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 27/27 with `release_fallback_smoke`.
- Packaged browser gates still reported 15 desktop routes, 15 mobile routes, 18 interaction steps, 0 console/network/layout failures, `releaseHeaderSmokeChecks: 6`, and `candidateActionSummaryVisible: true`.
- External sources checked: `https://docs.netlify.com/routing/redirects/rewrites-proxies/`, `https://docs.netlify.com/manage/routing/redirects/redirect-options/`, and `https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-custom-404-page-for-your-github-pages-site`.

## Experiment: GitHub Pages publish workflow template

- Hypothesis: The project is closer to publish-ready when the verified release package has a checked GitHub Pages workflow template and operator docs that account for GitHub's `workflow` scope requirement.
- Primary metric: `pagesPublishWorkflowTemplateChecks`.
- Baseline: 0 Pages publish workflow template checks; the package could be built locally but no repository-safe workflow artifact documented upload or deploy steps.
- Candidate: `docs/github-pages-workflow.yml` packages `dist/release`, verifies it, uploads it through `actions/upload-pages-artifact@v3`, and deploys with `actions/deploy-pages@v4` using `pages: write` and `id-token: write`; README documents copying it to `.github/workflows/joopark-pages.yml` with a token or UI session that has `workflow` scope.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages custom workflow docs require `configure-pages`, `upload-pages-artifact`, and `deploy-pages`; GitHub Actions permission docs require explicit `pages` and `id-token` permissions for Pages deployments.
- Directly adding `.github/workflows/joopark-pages.yml` was rejected by GitHub because the OAuth token lacks `workflow` scope, so the adopted artifact is a pushable workflow template under `docs/`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 29/29 with `release_publish_workflow_template_files` and `github_pages_publish_workflow_template`.
- Packaged browser gates still reported 15 desktop routes, 15 mobile routes, 18 interaction steps, 0 console/network/layout failures, `releaseHeaderSmokeChecks: 6`, `releaseFallbackSmokeChecks: 4`, and `candidateActionSummaryVisible: true`.
- External sources checked: `https://docs.github.com/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages`, `https://github.com/actions/deploy-pages`, and `https://docs.github.com/actions/reference/workflow-syntax-for-github-actions`.

## Next Loop

- Continue with the highest-impact product gap after the next full gate: no-common-history PR strategy, deeper UI workflow coverage, or Pages workflow scope handoff.
