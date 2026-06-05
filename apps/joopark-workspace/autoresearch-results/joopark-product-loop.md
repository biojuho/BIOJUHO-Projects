# JooPark Product AutoResearch Loop

Generated: 2026-06-06T02:14:17+09:00

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

## Experiment: GitHub Pages workflow scope handoff

- Hypothesis: The workflow template is more operational if a dry-run handoff script validates the template and target path while refusing to create `.github/workflows/joopark-pages.yml` unless the operator explicitly requests it in a workflow-scope session.
- Primary metric: `pagesWorkflowHandoffChecks`.
- Baseline: 0 handoff checks; the README described copying the template, but no script proved dry-run behavior or guarded accidental workflow file creation.
- Candidate: `scripts/prepare-github-pages-workflow.mjs` validates required Pages workflow terms, reports the target, defaults to dry-run, lets `--dry-run` override `--write`, and only writes with explicit `--write`; the release audit runs the dry-run and verifies README handoff commands.
- Decision: keep.

## Evidence

- The first dry-run validation caught a no-exit bug that would have continued into the write path; the adopted candidate fixes `result()` to exit on pass and rechecks that `.github/workflows/joopark-pages.yml` is not created.
- `node scripts/prepare-github-pages-workflow.mjs --dry-run` passed with `willWrite: false`, `targetExists: false`, and all template/target checks true.
- `node scripts/prepare-github-pages-workflow.mjs --write --dry-run` also stayed in dry-run mode, proving the safer flag wins.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 30/30 with `github_pages_workflow_scope_handoff`.

## Experiment: GitHub main PR bridge strategy

- Hypothesis: The no-common-history PR blocker becomes actionable when the release branch can prove why direct PR creation fails and outputs a main-based bridge plan for `apps/joopark-workspace`.
- Primary metric: `mainBridgeStrategyChecks`.
- Baseline: 0 PR bridge strategy checks; the log only recorded that GitHub rejected a draft PR because `codex/joopark-workspace-release` has no common history with `main`.
- Candidate: `scripts/plan-main-bridge.mjs` checks `merge-base`, verifies GitHub `main` already has `apps/joopark-workspace`, and prints the main-based bridge branch plan for `codex/joopark-workspace-main-bridge`; the release audit verifies the script, README guidance, and live plan output.
- Decision: keep.

## Evidence

- `git ls-remote --heads biojuho-projects main codex/joopark-workspace-release` observed `main` at `f32affb` and the release branch at `01f9bee`.
- `git merge-base HEAD biojuho-projects/main` returned no merge base, matching the previous GitHub PR blocker.
- `node scripts/plan-main-bridge.mjs` passed with `noCommonHistory: true`, `mainAppPathExists: true`, `appPath: apps/joopark-workspace`, and `bridgeBranch: codex/joopark-workspace-main-bridge`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 31/31 with `github_main_pr_bridge_strategy`.

## Experiment: monorepo-safe Pages workflow target

- Hypothesis: The Pages workflow handoff must target the Git repository root, not the app directory, before the app is synced into `apps/joopark-workspace` on the main branch.
- Primary metric: `pagesWorkflowHandoffChecks`.
- Baseline: 4 handoff checks; the helper validated dry-run behavior and explicit writes, but its target path was relative to the app root.
- Candidate: `scripts/prepare-github-pages-workflow.mjs` resolves `git rev-parse --show-toplevel`, reports `targetRepositoryPath`, and writes only to the repository-root `.github/workflows/joopark-pages.yml`; the release audit now requires the repo-root target evidence.
- Decision: keep.

## Evidence

- `node scripts/prepare-github-pages-workflow.mjs --dry-run` passed with `targetRepositoryPath: .github/workflows/joopark-pages.yml`, `willWrite: false`, and a repository-root path.
- `node scripts/prepare-github-pages-workflow.mjs --write --dry-run` stayed in dry-run mode and did not create `.github/workflows/joopark-pages.yml`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 31/31 after requiring `gitRoot`, `rev-parse --show-toplevel`, and `targetRepositoryPath`.

## Experiment: PR-ready main bridge plan state

- Hypothesis: The bridge plan should pass both before and after creating the main-based branch: before, it should detect `noCommonHistory`; after, it should detect a PR-ready branch with common history.
- Primary metric: `mainBridgeStrategyChecks`.
- Baseline: 4 bridge strategy checks; the audit required `noCommonHistory: true`, which is correct on the orphan release branch but wrong after the bridge branch is based on `main`.
- Candidate: `scripts/plan-main-bridge.mjs` now emits `main-subdirectory-bridge` for orphan release state and `pr-ready-main-history` for main-based branch state; the release audit accepts both while still requiring `apps/joopark-workspace`.
- Decision: keep.

## Evidence

- The bridge worktree surfaced the issue: once based on `biojuho-projects/main`, the branch correctly has a merge base and should be PR-ready rather than failing the bridge audit.
- `node scripts/plan-main-bridge.mjs` still passes on the orphan release branch with `strategy: main-subdirectory-bridge`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 31/31 after accepting both bridge states.

## Experiment: Veritas AutoResearch refresh v8.344

- Hypothesis: The release branch should preserve and advance the main branch Veritas freshness evidence instead of overwriting it during the PR bridge sync.
- Primary metric: `veritasFreshnessChecks`.
- Baseline: release data had stale Veritas metadata with `lastCommit: null`, `pushedAt: 2026-06-05T09:43:59Z`, and no `github-api:veritas-autoresearch-refresh` source marker.
- Candidate: `data/adoption-candidates.json` records Veritas `lastCommit: 96858c69be8712c9ad34f9ee6ce9f01f0b09c7a7`, `pushedAt: 2026-06-05T11:55:44Z`, the source marker, and a release audit freshness gate for that exact evidence.
- Decision: keep.

## Evidence

- `git ls-remote https://github.com/Veritas-7/autoresearch-skill-system.git refs/heads/main` returned `96858c69be8712c9ad34f9ee6ce9f01f0b09c7a7`.
- `gh repo view Veritas-7/autoresearch-skill-system --json pushedAt,updatedAt,description,stargazerCount,forkCount,defaultBranchRef,latestRelease` returned pushedAt `2026-06-05T11:55:44Z`, updatedAt `2026-06-05T11:55:49Z`, default branch `main`, 1 star, 1 fork, and no latest release.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 31/31 with refreshed `autoresearch_ecosystem_candidates.veritas.fresh: true`.

## Experiment: Veritas freshness UI smoke

- Hypothesis: The Veritas freshness data is more useful when the release portfolio UI exposes the upstream commit and the interaction smoke can find that candidate by commit.
- Primary metric: `veritasCandidateFreshnessVisible`.
- Baseline: the release data required Veritas freshness, but portfolio cards did not render `lastCommit` and the interaction smoke did not prove the Veritas card could be found by source evidence.
- Candidate: candidate cards render a short `Commit 96858c69` badge with the exact pushedAt marker, project search indexes `lastCommit`, and the packaged interaction smoke searches `96858c69` to verify the Veritas card, commit, pushedAt marker, description, and safe GitHub link.
- Decision: keep.

## Experiment: OpenProject freshness refresh

- Hypothesis: The release branch should preserve the main branch's highest-priority project-management benchmark freshness evidence instead of leaving OpenProject with stale metadata.
- Primary metric: `openProjectFreshnessChecks`.
- Baseline: `opf/openproject` had `lastCommit: null`, `pushedAt: 2026-06-05T10:35:36Z`, no OpenProject-specific source marker, and no UI smoke that could find the risk-review candidate by upstream commit.
- Candidate: `data/adoption-candidates.json` records OpenProject `lastCommit: 5b5c5c911788d7b77f9b80e1fc3bd4b0c1b61ce4`, `pushedAt: 2026-06-05T12:44:52Z`, the `github-api:openproject-freshness-refresh` source marker, and audit evidence for freshness/source validity.
- Decision: keep.

## Evidence

- `gh api repos/opf/openproject` returned `pushed_at: 2026-06-05T12:44:52Z`, 15,235 stars, 3,288 forks, 212 open issues, default branch `dev`, Ruby, and repository size 2,705,404 KB.
- `gh api 'repos/opf/openproject/commits?per_page=1'` returned commit `5b5c5c911788d7b77f9b80e1fc3bd4b0c1b61ce4` dated `2026-06-05T11:55:31Z`.
- The release interaction smoke now verifies `veritasCandidateFreshnessVisible` and `openProjectCandidateFreshnessVisible` through commit searches and commit badge metadata.

## Experiment: Leantime freshness refresh

- Hypothesis: The release branch should preserve the main branch's next project-management benchmark freshness evidence instead of leaving Leantime with stale `lastCommit` metadata.
- Primary metric: `leantimeFreshnessChecks`.
- Baseline: `Leantime/leantime` had `lastCommit: null`, no `github-api:leantime-freshness-refresh` source marker, and no commit-search UI smoke.
- Candidate: `data/adoption-candidates.json` records Leantime `lastCommit: b3a1037bf596d284b53355d23cadf1d9ab56b599`, `pushedAt: 2026-06-05T04:17:00Z`, the `github-api:leantime-freshness-refresh` source marker, and audit evidence for freshness/source validity.
- Decision: keep.

## Evidence

- `gh api repos/Leantime/leantime` returned `pushed_at: 2026-06-05T04:17:00Z`, 9,986 stars, 981 forks, 316 open issues, default branch `master`, and `archived: false`.
- `gh api repos/Leantime/leantime/commits/master` returned commit `b3a1037bf596d284b53355d23cadf1d9ab56b599` dated `2026-06-04T20:06:21Z` with message `chore(logicmodelcanvas): drop unused snapshot mount div (#3491)`.
- The release audit now expects 34/34 checks with `workspace_ecosystem_candidates.leantime.fresh: true`.

## Experiment: Leantime freshness UI smoke

- Hypothesis: Leantime freshness is more useful when the release portfolio UI exposes the upstream commit and the interaction smoke can find that candidate by commit.
- Primary metric: `leantimeCandidateFreshnessVisible`.
- Baseline: portfolio cards could not be searched by Leantime upstream commit because `lastCommit` was absent.
- Candidate: the packaged interaction smoke searches `b3a1037b` and verifies the Leantime card, commit, pushedAt marker, and safe GitHub link.
- Decision: keep.

## Evidence

- The release interaction smoke now reports `persistedChecks.leantimeCandidateFreshnessVisible: true` when the packaged UI renders the Leantime freshness badge.

## Experiment: Imported candidate metadata refresh

- Hypothesis: Freshness evidence should stay current for users who already have persisted project data; importing only missing candidates leaves existing adoption candidates with stale `lastCommit` metadata.
- Primary metric: `leantimeCandidateFreshnessVisible`.
- Baseline: `node scripts/audit-release-readiness.mjs --run-gates` failed 31/34 because the packaged interaction smoke found `Leantime candidate commit was stale`; release header and fallback checks could not pass while interaction smoke failed.
- Candidate: `mergeImportedProjects` now deduplicates by canonical GitHub repo key and refreshes metadata fields (`lastCommit`, `pushedAt`, stars, forks, issues, language, URL, topics, stage) for existing `sourceKind: "adoption-candidate"` records while preserving user-owned fields and members.
- Decision: keep.

## Evidence

- `BASE_URL=http://127.0.0.1:5181 node scripts/smoke-interactions.mjs` passed with `leantimeCandidateFreshnessVisible: true` and no console/network issues.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 34/34; packaged release evidence includes route smoke 15/15, mobile 15/15, 18 interaction steps, accessibility pass, release header checks 6/6, and fallback checks 4/4.

## Experiment: Veritas AutoResearch refresh v8.374

- Hypothesis: The product launch data should track the current Veritas upstream head instead of the earlier v8.344 evidence when the source-backed harness advances.
- Primary metric: `veritasFreshnessChecks`.
- Baseline: Veritas freshness evidence pointed to `96858c69be8712c9ad34f9ee6ce9f01f0b09c7a7` / `2026-06-05T11:55:44Z`.
- Candidate: `data/adoption-candidates.json`, the release audit, and the packaged interaction smoke now require Veritas `lastCommit: b0d4177dadce49f78f6978a2a36c777698ca9cb2`, `pushedAt: 2026-06-05T13:51:51Z`, and a `b0d4177d` portfolio commit search.
- Decision: keep.

## Evidence

- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned `b0d4177dadce49f78f6978a2a36c777698ca9cb2` with message `v8.374 Quality Manifest Status Evidence Exposure Gate`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T13:51:51Z`, `updated_at: 2026-06-05T13:52:02Z`, 1 star, 1 fork, 1 open issue, size 787 KB, default branch `main`, and `archived: false`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 34/34 with `autoresearch_ecosystem_candidates.veritas.fresh: true`.

## Experiment: candidate metadata refresh gate coverage

- Hypothesis: The persisted-candidate metadata refresh is safer to ship when the release gate proves stale local adoption-candidate metadata is refreshed from the source snapshot.
- Primary metric: `candidateMetadataRefresh` in packaged interaction smoke.
- Baseline: `mergeImportedProjects` refreshed existing adoption candidates, but the release audit did not require a stale-metadata refresh smoke.
- Candidate: `scripts/audit-release-readiness.mjs` now includes `workspace_candidate_metadata_refresh`, and `scripts/smoke-interactions.mjs` intentionally stales the Leantime candidate commit, pushedAt, and stars before verifying `mergeImportedProjects` refreshes and persists the snapshot values.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed 35/35 with `persistedChecks.candidateMetadataRefresh: true`, 18 interaction steps, 15 desktop routes, 15 mobile routes, 0 console/network/layout failures, accessibility pass, release header checks 6/6, and fallback checks 4/4.

## Experiment: Veritas AutoResearch refresh v8.381

- Hypothesis: The product launch data should track the current Veritas upstream head instead of the earlier v8.374 evidence when the source-backed harness advances.
- Primary metric: `veritasCurrentHeadFresh`.
- Baseline: GitHub API showed Veritas had advanced from `b0d4177dadce49f78f6978a2a36c777698ca9cb2` / `2026-06-05T13:51:51Z`, while the workspace snapshot and smoke still required that older commit.
- Candidate: `data/adoption-candidates.json`, release audit, and packaged interaction smoke now require Veritas `lastCommit: 04714cdc78e2997594cc2daad5a9403d2e4d2b20`, `pushedAt: 2026-06-05T14:20:51Z`, and a `04714cdc` portfolio commit search.
- Decision: keep.

## Evidence

- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned `04714cdc78e2997594cc2daad5a9403d2e4d2b20` dated `2026-06-05T14:20:50Z` with message `v8.381 Completion Audit Markdown Invalid UTF8 Gate`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T14:20:51Z`, `updated_at: 2026-06-05T14:21:03Z`, 1 star, 1 fork, 1 open issue, size 787 KB, default branch `main`, and `archived: false`.

## Experiment: Veritas dynamic snapshot freshness gate

- Hypothesis: The Veritas freshness gate should follow the source-backed adoption snapshot instead of hard-coding a fast-moving upstream commit in scripts.
- Primary metric: Veritas exact freshness literals in `scripts/audit-release-readiness.mjs` and `scripts/smoke-interactions.mjs`.
- Baseline: scripts hard-coded the v8.381 Veritas full commit, short commit, pushedAt marker, and version text, so the gate became stale as soon as upstream advanced.
- Candidate: `data/adoption-candidates.json` now records Veritas v8.383 (`b1d3228587f87e0f25fc31ea32bc583cce451d60`, `2026-06-05T14:29:42Z`), while audit and interaction smoke read the Veritas expected commit, pushedAt, short commit, and description from the adoption snapshot.
- Decision: keep; the full release gate passed with the snapshot-driven Veritas checks.

## Evidence

- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned `b1d3228587f87e0f25fc31ea32bc583cce451d60` dated `2026-06-05T14:29:41Z` with message `v8.383 Launchctl Exit File Read Failure Gate`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T14:29:42Z`, `updated_at: 2026-06-05T14:29:46Z`, 1 star, 1 fork, 1 open issue, size 787 KB, default branch `main`, and `archived: false`.
- `rg` found no Veritas exact commit, pushedAt, or version literals in the audit and interaction smoke scripts after the candidate change.
- `npm run verify` passed `35/35` after regenerating `dist/release`.

## Experiment: Veritas AutoResearch refresh v8.389

- Hypothesis: With the Veritas freshness gate snapshot-driven, the product launch data can follow the fast-moving upstream head without editing audit or smoke code.
- Primary metric: `veritasCurrentHeadFresh`.
- Baseline: main recorded Veritas v8.383 (`b1d3228587f87e0f25fc31ea32bc583cce451d60`, `2026-06-05T14:29:42Z`) after the dynamic gate landed.
- Candidate: `data/adoption-candidates.json` now records Veritas v8.389 (`f273071a78bd59bf7b2aae6eed5678453467a3f3`, `2026-06-05T14:50:53Z`) while the release audit and interaction smoke still derive expectations from the snapshot.
- Decision: keep.

## Evidence

- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned `f273071a78bd59bf7b2aae6eed5678453467a3f3` dated `2026-06-05T14:50:52Z` with message `v8.389 Launchctl Remove Start Failure Gate`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T14:50:53Z`, `updated_at: 2026-06-05T14:51:28Z`, 1 star, 1 fork, 1 open issue, size 1043 KB, default branch `main`, and `archived: false`.

## Experiment: Workspace benchmark dynamic snapshot freshness gate

- Hypothesis: OpenProject and Leantime freshness gates should follow the source-backed adoption snapshot instead of hard-coding fast-moving benchmark commits in scripts.
- Primary metric: OpenProject/Leantime exact freshness literals in `scripts/audit-release-readiness.mjs` and `scripts/smoke-interactions.mjs`.
- Baseline: scripts hard-coded OpenProject and Leantime full commits, short commit searches, pushedAt markers, and audit expectations, for 16 exact freshness literals across the two scripts.
- Candidate: `data/adoption-candidates.json` now records OpenProject `6885ca695dd38384c651704675143be63f9a514d` / `2026-06-05T15:01:04Z` and refreshed Leantime popularity metadata, while audit and interaction smoke read OpenProject/Leantime expected commit, pushedAt, and short commit from the adoption snapshot.
- Decision: keep; the full release gate passed with snapshot-driven workspace benchmark checks.

## Evidence

- `gh api repos/opf/openproject/commits/dev` returned `6885ca695dd38384c651704675143be63f9a514d` dated `2026-06-05T14:42:32Z` with message `Merge pull request #23580 from opf/merge-release/17.5-20260605114354`.
- `gh api repos/opf/openproject` returned `pushed_at: 2026-06-05T15:01:04Z`, `updated_at: 2026-06-05T14:42:41Z`, 15,235 stars, 3,288 forks, 211 open issues, size 2,705,681 KB, default branch `dev`, and `archived: false`.
- `gh api repos/Leantime/leantime/commits/master` still returned `b3a1037bf596d284b53355d23cadf1d9ab56b599` dated `2026-06-04T20:06:21Z`.
- `gh api repos/Leantime/leantime` returned `pushed_at: 2026-06-05T04:17:00Z`, `updated_at: 2026-06-05T13:39:16Z`, 9,987 stars, 983 forks, 317 open issues, size 247,835 KB, default branch `master`, and `archived: false`.
- `rg` found no OpenProject or Leantime exact commit, pushedAt, or short commit literals in the audit and interaction smoke scripts after the candidate change.
- `npm run verify` passed `35/35` after regenerating `dist/release`.

## Experiment: GitHub Pages workflow scope preflight

- Hypothesis: Pages workflow activation is safer when the handoff script detects missing `workflow` scope before writing the repository-root workflow file.
- Primary metric: Pages workflow scope preflight checks.
- Baseline: `scripts/prepare-github-pages-workflow.mjs --write` validated the template and explicit write mode, but did not inspect the current GitHub token scope before attempting the repository-root workflow write.
- Candidate: `scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` reports `workflowScopeAvailable`, and `--write` fails before creating `.github/workflows/joopark-pages.yml` when the current token lacks `workflow` scope.
- Decision: keep; current token lacks `workflow` scope, so activation remains a follow-up for a workflow-scope token or GitHub UI session.

## Evidence

- `gh api -i user` reported `X-Oauth-Scopes: gist, read:org, repo`, with no `workflow` scope.
- `node scripts/prepare-github-pages-workflow.mjs --dry-run` passed with `workflowScopeChecked: false`, `workflowScopeAvailable: null`, and `willWrite: false`.
- `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` passed with `workflowScopeChecked: true`, `workflowScopeAvailable: false`, and scopes `gist`, `read:org`, `repo`.
- `node scripts/prepare-github-pages-workflow.mjs --write` failed before writing with `reason: missing workflow scope`, `workflowScopeAvailable: false`, and no `.github/workflows/joopark-pages.yml` file created.

## Experiment: Workspace benchmark HEAD freshness refresh

- Hypothesis: The benchmark queue is more useful for launch triage when Colanode, Parabol, and Worklenz carry commit-level freshness evidence, not only repo-level pushedAt metadata.
- Primary metric: workspace benchmark HEAD snapshots.
- Baseline: only OpenProject and Leantime had `lastCommit` snapshots and commit-search browser smoke coverage.
- Candidate: `data/adoption-candidates.json` now records `lastCommit` for `colanode/colanode`, `ParabolInc/parabol`, and `Worklenz/worklenz`, while audit and interaction smoke require source markers plus commit-search UI coverage for all three.
- Decision: keep.

## Evidence

- `gh api repos/colanode/colanode/commits/main` returned `d649523637f0f059c936418488165d4a689da27c` dated `2026-04-03T09:33:46Z`; repo metadata returned `pushed_at: 2026-04-03T14:23:17Z`, 4,892 stars, 300 forks, 44 open issues, and size 79,013 KB.
- `gh api repos/ParabolInc/parabol/commits/master` returned `f1c60852df00522c74ba9ab49127fd72103ea519` dated `2026-06-04T00:13:54Z`; repo metadata returned `pushed_at: 2026-06-04T00:16:02Z`, 2,002 stars, 366 forks, 68 open issues, and size 149,121 KB.
- `gh api repos/Worklenz/worklenz/commits/main` returned `c4c32686587ad0d2fcd0b0b7c806a04858f03f7b` dated `2026-02-25T14:39:35Z`; repo metadata returned `pushed_at: 2026-02-25T14:39:35Z`, 3,067 stars, 321 forks, 62 open issues, and size 13,805 KB.

## Experiment: Workspace benchmark HEAD freshness coverage

- Hypothesis: After the benchmark HEAD refresh, the next highest-value coverage gain is to add commit-level evidence for Anytype and Focalboard so local-first knowledge and Kanban benchmark rows are comparable with the PM rows.
- Primary metric: workspace benchmark HEAD snapshots.
- Baseline: 5 of 14 local-first/project-management candidates had source-backed `lastCommit` snapshots after PR #167.
- Candidate: 7 of 14 candidates now carry source-backed `lastCommit` snapshots, adding `anyproto/anytype-ts` and `mattermost-community/focalboard`; audit and interaction smoke require both candidates by short commit.
- Decision: keep; the rebased release gate remains the deciding proof.

## Evidence

- `gh api repos/anyproto/anytype-ts/commits/develop` returned `153917ec6d28e41da672ad93cd9448a644dacfb8` dated `2026-06-04T23:49:47Z`; repo metadata returned `pushed_at: 2026-06-05T02:04:08Z`, 8,037 stars, 517 forks, 169 open issues, and size 985,782 KB.
- `gh api repos/mattermost-community/focalboard/commits/main` returned `a84bbb65e32edf972856b329417096ac413518e9` dated `2025-06-11T13:30:05Z`; repo metadata returned `pushed_at: 2026-05-18T16:05:00Z`, 26,212 stars, 2,544 forks, 779 open issues, and size 59,223 KB.

## Experiment: Workspace benchmark HEAD freshness refresh 2

- Hypothesis: The local-first benchmark queue should expose commit-level freshness for Epicenter and OpenLoaf before deeper product comparison work.
- Primary metric: workspace benchmark HEAD snapshots.
- Baseline: 7 workspace benchmark candidates had source-backed `lastCommit` snapshots after the Anytype/Focalboard coverage update.
- Candidate: 9 workspace benchmark candidates now carry source-backed `lastCommit` snapshots, adding `EpicenterHQ/epicenter` and `OpenLoaf/OpenLoaf`; audit and interaction smoke require both candidates by short commit.
- Decision: keep.

## Evidence

- `gh api repos/EpicenterHQ/epicenter/commits/main` returned `6d854a92b5c5a55d171fb6584f9686d50af10b7c` dated `2026-06-04T15:14:45Z`; repo metadata returned `pushed_at: 2026-06-05T14:50:11Z`, 4,605 stars, 348 forks, 170 open issues, 64 open PRs, and size 59,857 KB.
- `gh api repos/OpenLoaf/OpenLoaf/commits/main` returned `f7eccf6064317cb2923137079b68d79b8e5c5f3e` dated `2026-05-14T06:51:56Z`; repo metadata returned `pushed_at: 2026-05-14T11:24:18Z`, 65 stars, 7 forks, 1 open issue, and size 201,235 KB.
- `gh api repos/anyproto/anytype-ts` later returned 516 forks, so the snapshot was adjusted from 517 to 516 during the rebase.

## Experiment: Remaining workspace freshness refresh

- Hypothesis: Closing the remaining local-first/workspace rows with commit-level snapshots makes the benchmark queue ready for deeper UX comparison work instead of more metadata cleanup.
- Primary metric: workspace benchmark HEAD snapshots.
- Baseline: 9 workspace benchmark candidates had source-backed `lastCommit` snapshots after the Epicenter/OpenLoaf refresh.
- Candidate: 14 workspace benchmark candidates now carry source-backed `lastCommit` snapshots, adding `happybhati/workstream`, `Taskosaur/Taskosaur`, `ioniks/MarkdownTaskManager`, `taskcoach/taskcoach`, and `dotnetfactory/fluid-calendar`; audit and interaction smoke require all five by short commit.
- Decision: keep; the full release gate remains the deciding proof.

## Evidence

- GitHub GraphQL returned `happybhati/workstream` default branch `main` at `ff358f14d0624529589a4c86df14f6928d0e46a2`, committed `2026-04-23T15:58:54Z`, pushed `2026-04-24T09:38:51Z`, with 4 stars, 1 fork, 10 open issues, 6 open PRs, and size 1,632 KB.
- GitHub GraphQL returned `Taskosaur/Taskosaur` default branch `main` at `3a6e39f662c6fd8b22980c16d4441d8887347c31`, committed `2026-06-02T10:32:37Z`, pushed `2026-06-02T11:00:39Z`, with 493 stars, 96 forks, 8 open issues, 2 open PRs, and size 9,677 KB.
- GitHub GraphQL returned `ioniks/MarkdownTaskManager` default branch `master` at `e0551bc7a4367c20ba9239292f10e13707b6b765`, committed `2025-11-14T09:12:43Z`, pushed `2025-11-14T09:14:35Z`, with 406 stars, 55 forks, 2 open issues, 4 open PRs, and size 812 KB.
- GitHub GraphQL returned `taskcoach/taskcoach` default branch `master` at `dad6168f8771cda4566dedfad1e678ea253c2a7f`, committed `2026-05-19T00:44:53Z`, pushed `2026-05-28T16:07:10Z`, with 31 stars, 6 forks, 92 open issues, 3 open PRs, and size 590,173 KB.
- GitHub GraphQL returned `dotnetfactory/fluid-calendar` default branch `main` at `1c6de42da24520d0a917b5e3b5044f53573c023e`, committed `2026-05-28T16:42:37Z`, pushed `2026-05-28T16:42:40Z`, with 959 stars, 63 forks, 64 open issues, 1 open PR, and size 2,279 KB.

## Experiment: Remaining workspace metadata drift refresh

- Hypothesis: After the benchmark queue reached 14/14 commit freshness, the next useful cleanup is to remove repo metadata drift in the same high-priority remaining workspace candidates.
- Primary metric: remaining workspace open issue drift count.
- Baseline: 5 remaining workspace candidates had stale `openIssues` values compared with current GitHub REST repo metadata.
- Candidate: `data/adoption-candidates.json` now records current REST `open_issues_count` values for `happybhati/workstream`, `Taskosaur/Taskosaur`, `ioniks/MarkdownTaskManager`, `taskcoach/taskcoach`, and `dotnetfactory/fluid-calendar`, reducing the drift count to 0 while preserving 14/14 `lastCommit` coverage.
- Decision: keep.

## Evidence

- `gh api repos/happybhati/workstream` returned `open_issues_count: 16`, with 4 stars, 1 fork, and `pushed_at: 2026-04-24T09:38:51Z`.
- `gh api repos/Taskosaur/Taskosaur` returned `open_issues_count: 10`, with 493 stars, 96 forks, and `pushed_at: 2026-06-02T11:00:39Z`.
- `gh api repos/ioniks/MarkdownTaskManager` returned `open_issues_count: 6`, with 406 stars, 55 forks, and `pushed_at: 2025-11-14T09:14:35Z`.
- `gh api repos/taskcoach/taskcoach` returned `open_issues_count: 95`, with 31 stars, 6 forks, and `pushed_at: 2026-05-28T16:07:10Z`.
- `gh api repos/dotnetfactory/fluid-calendar` returned `open_issues_count: 65`, with 959 stars, 63 forks, and `pushed_at: 2026-05-28T16:42:40Z`.

## Experiment: Candidate freshness drift monitor

- Hypothesis: Once the benchmark queue has source-backed snapshots, launch readiness improves if operators can detect stale GitHub HEAD metadata without editing the release data by hand.
- Primary metric: candidate freshness drift monitor checks.
- Baseline: no dedicated drift monitor; freshness was only enforced by static release audit expectations and browser smoke for known candidates.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` validates local snapshot shape offline and compares live GitHub GraphQL HEAD/pushedAt/star/fork/issue/PR/disk metadata on demand; release audit requires the script, README handoff, and snapshot-only proof.
- Decision: keep; live drift failure can be promoted to scheduled CI after token policy is confirmed.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` validates all source-backed adoption candidates without network access.
- `node scripts/check-candidate-freshness-drift.mjs --live` monitored 15 source-backed candidates and reported `driftCount: 9`, proving the monitor catches current upstream movement without failing unless `--fail-on-drift` is set.
- The live run already detected `Veritas-7/autoresearch-skill-system` moving from `f273071a78bd59bf7b2aae6eed5678453467a3f3` to `ee204b1d561134d9a72edc1be112b58d546797e9`, making the next refresh target concrete.
- `--live --fail-on-drift` converts detected drift into a failing exit code for automation.
- `scripts/audit-release-readiness.mjs` now includes `candidate_freshness_drift_monitor`, while `npm run lint` checks the new script syntax.

## Experiment: Veritas drift refresh v8.410

- Hypothesis: The new drift monitor should immediately translate a detected Veritas upstream move into a refreshed launch snapshot without touching audit or smoke code.
- Primary metric: candidate freshness live drift count.
- Baseline: live drift monitor reported 9 drifted source-backed candidates, including stale Veritas metadata at `f273071a78bd59bf7b2aae6eed5678453467a3f3`.
- Candidate: `data/adoption-candidates.json` now records Veritas `lastCommit: 30a376349ec5451f2373bc71ee0c69bfb758781c`, `pushedAt: 2026-06-05T16:31:52Z`, disk size 1,231 KB, 0 open issues, 1 open PR, and a `github-api:veritas-drift-refresh-v8410` source marker.
- Decision: keep; the monitor now reports Veritas clean and the remaining live drift count dropped to 8.

## Evidence

- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned `30a376349ec5451f2373bc71ee0c69bfb758781c` dated `2026-06-05T16:31:49Z` with message `v8.410 redact sensitive evidence keys`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T16:31:52Z`, `updated_at: 2026-06-05T16:31:56Z`, 1 star, 1 fork, REST `open_issues_count: 1`, size 1,231 KB, default branch `main`, and `archived: false`.
- GitHub GraphQL returned 0 open issues, 1 open PR, `diskUsage: 1231`, and the same default branch HEAD, matching the refreshed snapshot semantics used by the drift monitor.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 15 monitored candidates and 14 GitHub API source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live` reported `driftCount: 8`, with no Veritas drift remaining.

## Experiment: Remaining live drift refresh

- Hypothesis: Once the drift monitor exists, closing the remaining live drift rows makes the adoption benchmark snapshot ready for scheduled drift enforcement rather than ad hoc metadata cleanup.
- Primary metric: candidate freshness live drift count.
- Baseline: live drift monitor reported 9 drifted source-backed candidates after Veritas advanced again and the remaining workspace rows still had disk/star/PR/pushedAt drift.
- Candidate: `data/adoption-candidates.json` now refreshes Veritas to v8.414 (`5da25eadef357ad63a9083b0ca45eb5a2d8ebd26`), updates Epicenter disk size, Focalboard stars, Colanode/Anytype/OpenProject/Parabol/Leantime/Worklenz open PR counts, OpenProject pushedAt/disk size, and Leantime stars/open issue aggregate.
- Decision: keep; the live drift monitor reported `driftCount: 0` immediately after the refresh.

## Evidence

- GitHub GraphQL returned current values for all 9 drifted rows; Veritas default branch `main` was at `5da25eadef357ad63a9083b0ca45eb5a2d8ebd26`, committed `2026-06-05T16:42:24Z`, with message `v8.414 mixed status fail closed`.
- The same GraphQL run returned Epicenter `diskUsage: 59907`, Focalboard `stargazerCount: 26211`, Colanode `openPRs: 7`, Anytype `openPRs: 7`, OpenProject `pushedAt: 2026-06-05T15:36:21Z`, `openPRs: 211`, `diskUsage: 2705667`, Parabol `openPRs: 4`, Leantime `stargazerCount: 9988`, issue+PR aggregate 318, `openPRs: 2`, and Worklenz `openPRs: 9`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 15 monitored candidates and 15 GitHub API source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 0`.

## Experiment: Candidate freshness repo filter

- Hypothesis: Before scheduled fail-on-drift automation, operators need a focused check for high-churn repos such as Veritas so one fast-moving source does not obscure the rest of the candidate queue.
- Primary metric: candidate freshness repo filter checks.
- Baseline: the drift monitor could only scan every source-backed adoption candidate, so checking a single high-churn repo required reading the full live drift payload.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` now accepts repeatable `--repo owner/name` filters in snapshot-only and live modes, includes `repoFilters` in JSON output, and documents the focused Veritas command in the README.
- Decision: keep; filtered checks make Veritas refresh cadence and future fail-on-drift automation easier to operate.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system` passed with `monitored: 1` and `repoFilters: ["veritas-7/autoresearch-skill-system"]`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo=https://github.com/Veritas-7/autoresearch-skill-system/` passed, proving URL-form filters normalize to the same repo key.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system` reported only the Veritas drift after upstream moved again from `5da25eadef357ad63a9083b0ca45eb5a2d8ebd26` to `d95324fed121fc359cacf96cfc1aefb9fc2b141b` (`v8.417 api key header redaction`, `2026-06-05T16:51:33Z`).

## Experiment: Candidate freshness drift cadence policy

- Hypothesis: Before fail-on-drift automation is promoted, high-churn sources need a documented repo-scoped cadence so a fast-moving candidate can be refreshed without blocking the whole queue.
- Primary metric: candidate freshness cadence policy checks.
- Baseline: the drift monitor had focused `--repo` checks, but no machine-readable cadence policy or release-audit requirement for when to run them before `--fail-on-drift`.
- Candidate: `scripts/check-candidate-freshness-drift.mjs --cadence-policy` emits a snapshot-only policy for `Veritas-7/autoresearch-skill-system`, including snapshot, live, and repo-scoped blocking commands; the release audit now requires `candidate_freshness_drift_cadence_policy`.
- Decision: keep; cadence evidence is offline and keeps fail-on-drift automation scoped to Veritas until the snapshot is refreshed.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy` passed with `cadencePolicy.id: candidate-freshness-drift-cadence-v1`, `repoScopedHighChurn: true`, and a scoped `--fail-on-drift` command.
- `scripts/audit-release-readiness.mjs` now includes `candidate_freshness_drift_cadence_policy` and exposes the policy under `evidence.snapshotOnly.cadencePolicy`.
- The README now documents the high-churn Veritas cadence commands before enabling fail-on-drift automation.

## Experiment: Veritas focused drift refresh v8.424

- Hypothesis: The new repo-scoped cadence policy should translate a focused Veritas drift signal into a snapshot refresh without touching broader benchmark rows.
- Primary metric: Veritas focused drift refresh checks.
- Baseline: the focused live drift check reported Veritas moving from v8.414 (`5da25eadef357ad63a9083b0ca45eb5a2d8ebd26`) to a newer upstream HEAD.
- Candidate: `data/adoption-candidates.json` now records Veritas v8.424 (`6e833346ef5ba9f8d3426ff8287f89c151435bc8`), `pushedAt: 2026-06-05T17:13:31Z`, disk size 826 KB, and a `github-api:veritas-focused-drift-refresh-v8424` source marker.
- Decision: keep; this validates the cadence-policy handoff with a narrow source-data refresh.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --cadence-policy` reported Veritas drift to `6e833346ef5ba9f8d3426ff8287f89c151435bc8` with `committedAt: 2026-06-05T17:13:30Z`.
- `gh api repos/Veritas-7/autoresearch-skill-system/commits/main` returned message `v8.424 session token header redaction`.
- `gh api repos/Veritas-7/autoresearch-skill-system` returned `pushed_at: 2026-06-05T17:13:31Z`, 1 star, 1 fork, REST `open_issues_count: 1`, size 826 KB, default branch `main`, and `archived: false`.

## Next Loop

- Continue with the highest-impact product gap after the next full gate: install the Pages workflow with a workflow-scope token or GitHub UI session, trigger the `Publish JooPark Pages` workflow, benchmark Taskosaur and Workstream UX flows against JooPark PM/calendar surfaces, promote repo-scoped fail-on-drift automation once GitHub token policy is confirmed, or add a lightweight Veritas snapshot writer once repeated focused refreshes stabilize.
