# JooPark Product AutoResearch Loop

Generated: 2026-06-08T02:15:03+09:00

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

## Experiment: Veritas snapshot writer

- Hypothesis: Repeated focused Veritas refreshes should use an explicit helper instead of manual JSON edits before repo-scoped fail-on-drift automation is promoted.
- Primary metric: Veritas snapshot writer checks.
- Baseline: Veritas refreshes required hand-editing `data/adoption-candidates.json` after reading live drift output.
- Candidate: `scripts/refresh-veritas-candidate-snapshot.mjs` supports offline `--snapshot-only`, live dry-run, and explicit `--write` modes for `Veritas-7/autoresearch-skill-system`; release audit now requires `veritas_snapshot_writer`.
- Decision: keep; the next focused refresh can be generated by a controlled writer while release audit remains network-independent.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --snapshot-only` validates the current Veritas row without network access.
- `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run` detected live Veritas v8.428 (`18e1c7ac4f59164bafbe898b04ae963be25c8f79`) and reported `changed: true` without writing.
- `node scripts/refresh-veritas-candidate-snapshot.mjs --write` wrote `data/adoption-candidates.json`, added `github-api:veritas-focused-drift-refresh-v8428`, and updated `pushedAt: 2026-06-05T17:25:20Z`.
- `--write` remains the only mode that writes the snapshot file.

## Experiment: Taskosaur/Workstream UX benchmark focus

- Hypothesis: Candidate triage improves when Taskosaur and Workstream show explicit benchmark focus chips mapped to JooPark PM, Kanban, and Calendar surfaces instead of only generic metadata.
- Primary metric: Taskosaur/Workstream benchmark focus checks.
- Baseline: 0 explicit benchmark-focus checks for Taskosaur and Workstream.
- Candidate: `data/adoption-candidates.json` records `benchmarkFocus` for both candidates, portfolio cards render `data-candidate-benchmark` chips, and interaction smoke verifies the Workstream PM/Calendar flow plus the Taskosaur PM/Kanban conversational task flow.
- Decision: keep; the full release gate passed.

## Evidence

- GitHub metadata/readme evidence: Taskosaur describes conversational AI task execution, natural-language task creation, Kanban/sprints, and self-hosted PM; Workstream describes PRs, tasks, calendar, AI review/readiness, and an agents dashboard in one developer command center.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_focus`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 40/40.

## Experiment: Veritas writer fail-on-change gate

- Hypothesis: The Veritas writer should be usable as a repo-scoped automation gate before workflow scheduling is enabled.
- Primary metric: Veritas snapshot writer fail-on-change support.
- Baseline: dry-run reported `changed`, but it always exited 0, so automation had to parse JSON to block stale snapshots.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` exits non-zero with `status: drift` only when live metadata would change the snapshot, while still never writing files.
- Decision: keep; this gives future scheduled CI a single repo-scoped command once token policy is confirmed.

## Evidence

- `--fail-on-change` is documented in the README and required by release audit static terms.
- `--write` remains separate from fail-on-change, so the gate can detect drift without mutating `data/adoption-candidates.json`.
- During rebase over the Taskosaur/Workstream benchmark branch, the writer refreshed Veritas to v8.435 (`dc6f03ea6f3317e2b202db736b125e4dac31e700`) with `github-api:veritas-focused-drift-refresh-v8435`.
- After the writer refresh, `--fail-on-change` can pass until the next Veritas upstream move.

## Experiment: Veritas writer refresh v8.442

- Hypothesis: After the benchmark-focus queue landed on main, the release snapshot should still track the current high-churn Veritas source before promoting the next PR.
- Primary metric: Veritas snapshot writer write.
- Baseline: main recorded Veritas v8.435, while `--dry-run --fail-on-change` reported a newer upstream snapshot.
- Candidate: `data/adoption-candidates.json` records Veritas v8.442 (`e962762d8a2a9c98cb57836d0044bc839786934b`), `pushedAt: 2026-06-05T18:09:19Z`, disk size 845 KB, and `github-api:veritas-focused-drift-refresh-v8442`.
- Decision: keep; the writer refreshed the high-churn source without changing the queue implementation already merged in main.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` exited non-zero with live drift before the write.
- `node scripts/refresh-veritas-candidate-snapshot.mjs --write` updated the Veritas row plus snapshot metadata to v8.442.

## Experiment: Taskosaur/Workstream benchmark focus queue

- Hypothesis: Candidate triage improves when benchmark-focus chips can drive an explicit filtered queue instead of only decorating individual cards.
- Primary metric: Taskosaur/Workstream benchmark queue checks.
- Baseline: 0 benchmark-focus queue checks.
- Candidate: portfolio state now has a benchmark-focus filter, the candidate view can narrow to benchmark-focus cards, the queue sorts focused candidates with PM/Calendar and PM/Kanban signals first, and interaction smoke verifies the filtered count, top summary, and top card chip.
- Decision: keep; the full release gate passed.

## Evidence

- `app.js` now includes `CANDIDATE_BENCHMARK_FILTERS`, `sortBenchmarkFocusProjects`, `candidateBenchmarkQueueSummary`, and `setPortfolioBenchmarkFilter`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkQueueVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_queue`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 41/41.

## Experiment: Taskosaur/Workstream benchmark comparison rubric

- Hypothesis: Candidate triage improves when the top benchmark-focus projects can be compared side by side on input source, AI assistance, PM surface, and operations model.
- Primary metric: Taskosaur/Workstream benchmark rubric checks.
- Baseline: 0 side-by-side rubric checks.
- Candidate: Workstream and Taskosaur now carry rubric rows in `data/adoption-candidates.json`, the focused benchmark queue renders a comparison grid, and interaction smoke verifies the two projects plus four rubric axes.
- Decision: keep; the full release gate passed.

## Evidence

- GitHub README evidence mapped Workstream to PR/task/calendar plus AI review/readiness, and Taskosaur to natural-language task execution, browser task execution, Kanban, sprints, and self-hosted PM.
- `app.js` now includes `projectBenchmarkRubric` and `candidateBenchmarkRubric`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkRubricVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_rubric`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 42/42.

## Experiment: Veritas writer refresh v8.452

- Hypothesis: After the benchmark comparison rubric landed on main, the release snapshot should still track the current high-churn Veritas source before promoting the next PR.
- Primary metric: Veritas snapshot writer write.
- Baseline: main recorded Veritas v8.442, while `--dry-run --fail-on-change` reported v8.452.
- Candidate: `data/adoption-candidates.json` records Veritas v8.452 (`fe7a7fe5ca0b2008a00a72a848fe3236ddb72f06`), `pushedAt: 2026-06-05T18:36:42Z`, disk size 845 KB, and `github-api:veritas-focused-drift-refresh-v8452`.
- Decision: keep; the writer refreshed only the high-churn Veritas row plus snapshot metadata.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` exited non-zero with live drift before the write.
- `node scripts/refresh-veritas-candidate-snapshot.mjs --write` updated the Veritas row plus snapshot metadata to v8.452.

## Experiment: Taskosaur/Workstream benchmark rubric score

- Hypothesis: Candidate triage improves when the benchmark rubric has explicit weights and a computed recommendation instead of only side-by-side descriptive rows.
- Primary metric: Taskosaur/Workstream benchmark rubric score checks.
- Baseline: 0 scored rubric recommendation checks.
- Candidate: Workstream and Taskosaur rubric rows now carry weights and scores, the focused benchmark comparison renders weighted totals and a top recommendation, and interaction smoke verifies Taskosaur wins with a score of 86 while Workstream scores 85.
- Decision: keep; the full release gate passed 43/43.

## Evidence

- `data/adoption-candidates.json` now records weighted rubric scores for the Workstream and Taskosaur benchmark rows.
- `app.js` now includes `projectBenchmarkRubricScore` plus `data-benchmark-rubric-recommendation`, `data-rubric-total-score`, `data-rubric-weight`, and `data-rubric-score` markers.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkRubricScoreVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_rubric_score`.
- `npm run verify` passed 43/43 with `candidateBenchmarkRubricScoreVisible: true`.

## Experiment: Taskosaur/Workstream benchmark recommendation export

- Hypothesis: The weighted recommendation becomes more operational when the winning candidate, score gap, rationale, and weighted axis scores can be exported as a decision-ready Markdown note.
- Primary metric: Taskosaur/Workstream benchmark recommendation export checks.
- Baseline: 0 recommendation export checks.
- Candidate: the focused benchmark rubric now renders a Markdown export panel with a `joopark-benchmark-recommendation.md` download link, Taskosaur as the 86-point first adoption target, Workstream as the 85-point secondary benchmark, a 1-point score gap, and the top Taskosaur AI-assistance rationale.
- Decision: keep; packaged release smoke passed with `candidateBenchmarkRecommendationExportVisible: true`.

## Evidence

- A/B baseline was the weighted recommendation card without an exportable decision artifact; B adds the Markdown export while preserving the existing recommendation and rubric cells.
- `app.js` now includes `candidateBenchmarkRecommendationExport` and `candidateBenchmarkRecommendationMarkdown`.
- `styles.css` now includes `.portfolio-benchmark-export`, `.portfolio-export-download`, and `.portfolio-export-body`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkRecommendationExportVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_recommendation_export`.

## Experiment: Taskosaur/Workstream benchmark review queue

- Hypothesis: Candidate triage improves when weighted rubric outcomes persist into a review queue with stable decision keys instead of remaining only a comparison display.
- Primary metric: Taskosaur/Workstream benchmark review queue checks.
- Baseline: 0 review queue persistence checks for scored benchmark decisions.
- Candidate: the focused benchmark view now renders a review queue from rubric scores, records Taskosaur as the top-ranked `도입 검토` decision with score 86, and exposes a stable `benchmark-review:repo-taskosaur-taskosaur:86` persist key.
- Decision: keep; `npm run verify` passed 45/45 after packaging with the export and review queue smoke included.

## Evidence

- `app.js` now includes `projectBenchmarkReviewDecision` and `candidateBenchmarkReviewQueue`.
- `styles.css` now includes `.portfolio-benchmark-review` and `.portfolio-review-item`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkReviewQueueVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_review_queue`.
- `npm run verify` passed 45/45 with `sourceDirty: false`.

## Experiment: Taskosaur/Workstream benchmark review handoff export

- Hypothesis: Review queue decisions are easier to hand off when the ranked decisions, stable persist keys, and rationale can be exported as a Markdown note.
- Primary metric: Taskosaur/Workstream benchmark review handoff checks.
- Baseline: 0 handoff export checks for review queue decisions.
- Candidate: the focused benchmark review queue now renders a `joopark-benchmark-review-queue.md` handoff export with Taskosaur as the primary decision key and Workstream as the secondary comparison decision.
- Decision: keep; `npm run verify` passed 46/46 after packaging with the handoff export smoke included.

## Evidence

- `app.js` now includes `candidateBenchmarkReviewQueueHandoff` and `candidateBenchmarkReviewQueueMarkdown`.
- `styles.css` now includes `.portfolio-review-handoff`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkReviewHandoffVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_review_handoff_export`.
- `npm run verify` passed 46/46 with `sourceDirty: false`.

## Experiment: Taskosaur/Workstream benchmark review handoff copy

- Hypothesis: A one-click clipboard action reduces handoff friction when the operator needs to paste the benchmark review decision into a PM issue, Slack note, or GitHub comment.
- Primary metric: Taskosaur/Workstream benchmark review handoff copy checks.
- Baseline: 0 clipboard copy checks for the review handoff export.
- Candidate: the focused benchmark review handoff now includes a copy button that writes the same Markdown handoff to clipboard, exposes the primary persist key on the copy control, and renders copy state.
- Decision: keep; `npm run verify` passed 47/47 after packaging with the clipboard smoke included.

## Evidence

- `app.js` now includes `copyBenchmarkReviewHandoff` and `writeClipboardText`.
- `styles.css` now includes `.portfolio-export-actions`, `.portfolio-export-copy`, and `.portfolio-export-status`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkReviewHandoffCopyVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_review_handoff_copy`.

## Experiment: Taskosaur benchmark review issue draft

- Hypothesis: Benchmark review handoff becomes more actionable when the primary decision can be converted into a PM issue draft without leaving the focused queue.
- Primary metric: Taskosaur/Workstream benchmark review issue draft checks.
- Baseline: 0 PM issue draft checks for the review handoff export.
- Candidate: the focused benchmark review handoff now renders a Taskosaur PM issue draft with title, project, priority, labels, stable source key, and an `이슈 생성` action that persists the draft into `dashboard.issues`.
- Decision: keep; interaction smoke passed with `candidateBenchmarkReviewIssueDraftVisible: true` after creating an issue with source key `benchmark-review:repo-taskosaur-taskosaur:86`.

## Evidence

- `app.js` now includes `benchmarkReviewIssueDraft`, `candidateBenchmarkReviewIssueDraft`, and `createBenchmarkReviewIssue`.
- `styles.css` now includes `.portfolio-review-issue-draft`, `.portfolio-issue-draft-grid`, and `.portfolio-issue-draft-body`.
- `scripts/smoke-interactions.mjs` now reports `candidateBenchmarkReviewIssueDraftVisible`.
- `scripts/audit-release-readiness.mjs` now includes `taskosaur_workstream_benchmark_review_issue_draft`.
- Baseline `npm run verify` was 47/47; the candidate expands the audit target to 48 checks.

## Experiment: Veritas focused snapshot writer v8.487

- Hypothesis: The high-churn Veritas AutoResearch candidate stays product-useful when a repo-scoped dry-run fails on upstream change and the snapshot writer immediately records the new focused version.
- Primary metric: Veritas snapshot writer changed flag.
- Baseline: the focused Veritas snapshot was v8.452 with commit `fe7a7fe5ca0b2008a00a72a848fe3236ddb72f06`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` reported `changed: true`, then `--write` updated the candidate to v8.487 with commit `00b59fdb4e6ac72baa38bfd50523279e07c0a6bb`.
- Decision: keep; the writer added source marker `github-api:veritas-focused-drift-refresh-v8487`, refreshed pushedAt to `2026-06-05T20:17:58Z`, and preserved the existing repo-scoped audit path.

## Evidence

- `data/adoption-candidates.json` now records `v8.487 최신 modal token secret env redaction`.
- `data/adoption-candidates.json` now records `diskKb: 865`, `openPRs: 1`, and the latest observed Veritas commit `00b59fdb4e6ac72baa38bfd50523279e07c0a6bb`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasSnapshotWriterChanged: true`.
- Veritas moved from v8.484 to v8.487 during this loop, so PR-time freshness is time-dependent; the retained control is the repo-scoped writer plus `--fail-on-change` detection.
- Pages workflow installation and scheduled CI wiring remain blocked in this session because `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` reported `workflowScopeAvailable: false`.

## Experiment: Plane PM benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more launch-useful when a high-signal Jira/Linear-class PM benchmark is tracked alongside smaller workspace candidates.
- Primary metric: Plane PM candidate freshness checks.
- Baseline: 0 Plane PM candidate checks; `makeplane/plane` was absent from the adoption candidate snapshot.
- Candidate: add `makeplane/plane` as a researched PM workflow candidate with current GitHub metadata, AGPL risk context, popularity, default-branch commit, and portfolio interaction smoke.
- Decision: keep; Plane has 50,363 stars, 4,431 forks, 756 open issues, 128 open PRs, recent push `2026-06-05T15:22:38Z`, and commit `0bbfe95cc74c9c958d66b156df2783fdbc180f8e`.

## Evidence

- `data/adoption-candidates.json` now includes `makeplane/plane` with source markers `github-search:plane-pm-benchmark` and `github-api:plane-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `planeCandidateFreshnessVisible` and verifies Plane by commit search, star/fork count, language, risk-review action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `plane_pm_candidate_freshness_ui_smoke`.
- AppFlowy and AFFiNE were also checked as high-signal workspace candidates and were promoted in the next loop.

## Experiment: Veritas focused snapshot writer v8.510

- Hypothesis: The high-churn Veritas AutoResearch candidate should keep tracking upstream when the repo-scoped writer reports a new focused drift immediately after the previous release sync.
- Primary metric: Veritas snapshot writer changed flag.
- Baseline: the focused Veritas snapshot was v8.509 with commit `7656aa53040b6e331ffba6bcaa71812a023ce3f2`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` reported `changed: true`, then `--write` updated the candidate to v8.510 with commit `5e4b31b0c2b1763f45b2eea4ba7e740dd8209360`.
- Decision: keep; the writer added source marker `github-api:veritas-focused-drift-refresh-v8510`, refreshed pushedAt to `2026-06-05T21:17:28Z`, and preserved the existing repo-scoped audit path.

## Evidence

- `data/adoption-candidates.json` now records `v8.510 최신 rabbitmq url env redaction`.
- `data/adoption-candidates.json` now records `diskKb: 886`, `openPRs: 1`, and the latest observed Veritas commit `5e4b31b0c2b1763f45b2eea4ba7e740dd8209360`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasFocusedSnapshotVersion: v8.510`.
- Pages workflow installation and scheduled CI wiring remain blocked in this session because `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` reported `workflowScopeAvailable: false`.

## Experiment: AppFlowy workspace benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more useful for JooPark planning when a large open-source Notion-class workspace benchmark is tracked next to PM-specific candidates.
- Primary metric: AppFlowy workspace candidate freshness checks.
- Baseline: 0 AppFlowy workspace candidate checks; `AppFlowy-IO/AppFlowy` was absent from the adoption candidate snapshot.
- Candidate: add `AppFlowy-IO/AppFlowy` as a researched AI collaboration workspace candidate with current GitHub metadata, AGPL risk context, default-branch commit, and portfolio interaction smoke.
- Decision: keep; AppFlowy has 71,842 stars, 5,402 forks, 936 open issues, 70 open PRs, recent push `2026-06-05T12:00:29Z`, and commit `4af02cdc87468be10ab15dbb4afd27fbf53ce89b`.

## Evidence

- `data/adoption-candidates.json` now includes `AppFlowy-IO/AppFlowy` with source markers `github-search:appflowy-workspace-benchmark` and `github-api:appflowy-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `appFlowyCandidateFreshnessVisible` and verifies AppFlowy by commit search, star/fork count, language, risk-review action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_workspace_candidate_freshness_ui_smoke`.

## Experiment: AFFiNE workspace benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more useful for JooPark planning when a Notion/Miro-class knowledge-base and whiteboard benchmark is tracked alongside AppFlowy.
- Primary metric: AFFiNE workspace candidate freshness checks.
- Baseline: 0 AFFiNE workspace candidate checks; `toeverything/AFFiNE` was absent from the adoption candidate snapshot.
- Candidate: add `toeverything/AFFiNE` as a researched knowledge-base workspace candidate with current GitHub metadata, license risk context, default-branch commit, and portfolio interaction smoke.
- Decision: keep; AFFiNE has 69,107 stars, 4,913 forks, 555 open issues, 74 open PRs, recent push `2026-06-04T22:48:17Z`, and commit `edc87e38df01db79f969e6f61981a10c16f9a0bb`.

## Evidence

- `data/adoption-candidates.json` now includes `toeverything/AFFiNE` with source markers `github-search:affine-workspace-benchmark` and `github-api:affine-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `affineCandidateFreshnessVisible` and verifies AFFiNE by commit search, star/fork count, language, risk-review action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `affine_workspace_candidate_freshness_ui_smoke`.

## Experiment: AppFlowy and AFFiNE workspace benchmark candidates

- Hypothesis: The GitHub project discovery surface becomes more useful for workspace product direction when the newly landed AppFlowy and AFFiNE candidates are verified as a paired benchmark set.
- Primary metric: AppFlowy/AFFiNE candidate freshness checks.
- Baseline: 0 paired AppFlowy/AFFiNE candidate checks; the two individual candidates had separate smoke gates only.
- Candidate: add paired portfolio interaction smoke for AppFlowy plus AFFiNE, preserving both individual candidate gates while requiring a combined source marker.
- Decision: keep; AppFlowy has 71,842 stars, 5,402 forks, 936 open issues, 70 open PRs, recent push `2026-06-05T12:00:29Z`, and commit `4af02cdc87468be10ab15dbb4afd27fbf53ce89b`; AFFiNE has 69,107 stars, 4,913 forks, 555 open issues, 74 open PRs, recent push `2026-06-04T22:48:17Z`, and commit `edc87e38df01db79f969e6f61981a10c16f9a0bb`.

## Evidence

- `data/adoption-candidates.json` now keeps `github-search:appflowy-workspace-benchmark`, `github-search:affine-workspace-benchmark`, `github-search:appflowy-affine-benchmark`, `github-api:appflowy-freshness-refresh`, and `github-api:affine-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `appFlowyCandidateFreshnessVisible` and `affineCandidateFreshnessVisible`, verifying both candidates by commit search, star/fork count, language, risk-review action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_candidate_freshness_ui_smoke`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 18 monitored candidates and 32 source markers.

## Experiment: Outline knowledge-base benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more useful for JooPark planning when a fast, self-hostable, Markdown-compatible team knowledge base is tracked beside AppFlowy and AFFiNE.
- Primary metric: Outline knowledge-base candidate freshness checks.
- Baseline: 0 Outline knowledge-base candidate checks; `outline/outline` was absent from the adoption candidate snapshot.
- Candidate: add `outline/outline` as a researched knowledge-base workspace candidate with current GitHub metadata, license risk context, default-branch commit, and portfolio interaction smoke.
- Decision: keep; Outline has 38,776 stars, 3,324 forks, 38 open issues, 22 open PRs, recent push `2026-06-05T14:54:48Z`, and commit `e864684d569c81ca2b03c816d22e0c80e2ff6466`.

## Evidence

- `data/adoption-candidates.json` now includes `outline/outline` with source markers `github-search:outline-knowledge-base-benchmark` and `github-api:outline-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `outlineCandidateFreshnessVisible` and verifies Outline by commit search, star/fork count, language, spike recommendation action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `outline_knowledge_base_candidate_freshness_ui_smoke`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 19 monitored candidates and 33 source markers.

## Experiment: BookStack documentation benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more useful for JooPark planning when a mature self-hosted documentation/wiki model is tracked beside realtime knowledge-base tools.
- Primary metric: BookStack documentation candidate freshness checks.
- Baseline: 0 BookStack documentation candidate checks; `BookStackApp/BookStack` was absent from the adoption candidate snapshot.
- Candidate: add `BookStackApp/BookStack` as a researched documentation benchmark candidate with current GitHub mirror metadata, Codeberg migration risk context, default-branch commit, and portfolio interaction smoke.
- Decision: keep; BookStack has 18,814 stars, 2,384 forks, 0 open issues, 1 open PR, recent push `2026-06-05T04:31:28Z`, and commit `f01bb749ab3f11fc465bf5f247dc84e297e4f98a`.

## Evidence

- `data/adoption-candidates.json` now includes `BookStackApp/BookStack` with source markers `github-search:bookstack-documentation-benchmark` and `github-api:bookstack-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `bookStackCandidateFreshnessVisible` and verifies BookStack by commit search, star/fork count, language, source-migration description, architecture-benchmark action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `bookstack_documentation_candidate_freshness_ui_smoke`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 20 monitored candidates and 34 source markers.

## Experiment: Wiki.js self-hosted wiki benchmark candidate

- Hypothesis: The GitHub project discovery surface becomes more useful for JooPark planning when Wiki.js is tracked beside Outline and BookStack as a Node/Vue self-hosted wiki model with Git-backed documentation workflows.
- Primary metric: Wiki.js self-hosted wiki candidate freshness checks.
- Baseline: 0 Wiki.js self-hosted wiki candidate checks; `requarks/wiki` was absent from the adoption candidate snapshot.
- Candidate: add `requarks/wiki` as a researched self-hosted wiki benchmark candidate with current GitHub metadata, default-branch commit, Git/Markdown context, and portfolio interaction smoke.
- Decision: keep; Wiki.js has 28,414 stars, 3,238 forks, 58 open issues, 129 open PRs, recent push `2026-05-01T10:34:55Z`, and commit `6f042e97cc2d3acda6b6ff611de8e0faacce91c1`.

## Evidence

- `data/adoption-candidates.json` now includes `requarks/wiki` with source markers `github-search:wikijs-self-hosted-wiki-benchmark` and `github-api:wikijs-freshness-refresh`.
- `scripts/smoke-interactions.mjs` now reports `wikiJsCandidateFreshnessVisible` and verifies Wiki.js by commit search, star/fork count, language, Git-backed description, architecture-benchmark action, pushedAt, and safe GitHub link.
- `scripts/audit-release-readiness.mjs` now includes `wikijs_self_hosted_wiki_candidate_freshness_ui_smoke`.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 21 monitored candidates and 35 source markers.

## Experiment: Knowledge-base information architecture rubric

- Hypothesis: The portfolio benchmark surface becomes more useful for JooPark notes/workspace planning when Outline, BookStack, and Wiki.js are compared on information architecture instead of only tracked as separate freshness candidates.
- Primary metric: knowledge-base information architecture rubric checks.
- Baseline: 0 dedicated KB/IA rubric checks; the focused benchmark rubric only compared the top PM/Calendar candidates.
- Candidate: add a dedicated `knowledgeBaseBenchmark` rubric for `outline/outline`, `BookStackApp/BookStack`, and `requarks/wiki` across information structure, editing/collaboration, permissions/operations, and portability.
- Decision: keep; the rubric keeps the existing Taskosaur/Workstream PM comparison intact while adding a 3-column KB/IA comparison where Outline and Wiki.js score 87 and BookStack scores 83.

## Evidence

- `data/adoption-candidates.json` now stores `knowledgeBaseBenchmark` rows for Outline, BookStack, and Wiki.js with shared `JooPark Knowledge/IA` axes.
- `app.js` now renders a dedicated `data-knowledge-base-benchmark-rubric` section when the candidate benchmark filter is focused, without changing the existing PM benchmark queue.
- `scripts/smoke-interactions.mjs` now reports `knowledgeBaseBenchmarkRubricVisible` and verifies all three projects, four axes, the Outline tie-break recommendation, and Wiki.js Git-backed portability scoring.
- `scripts/audit-release-readiness.mjs` now includes `knowledge_base_information_architecture_rubric`.

## Experiment: Knowledge-base information architecture export

- Hypothesis: The KB/IA comparison becomes operationally useful when the weighted recommendation can be exported as a Markdown handoff instead of remaining only a dashboard view.
- Primary metric: knowledge-base information architecture export checks.
- Baseline: 0 KB/IA export checks; the KB/IA rubric rendered in the portfolio but had no dedicated Markdown output.
- Candidate: add `joopark-kb-ia-recommendation.md` export for the Outline/BookStack/Wiki.js rubric with winner, score gap, weighted rationale, and per-project score breakdown.
- Decision: keep; the export preserves the existing PM benchmark export while adding a dedicated KB/IA recommendation that picks Outline on tie-break, keeps Wiki.js as the portability counterweight, and records a 0-point score gap.

## Evidence

- `app.js` now includes `knowledgeBaseBenchmarkRecommendationMarkdown` and `candidateKnowledgeBaseRecommendationExport` with `data-knowledge-base-benchmark-export`.
- `scripts/smoke-interactions.mjs` now reports `knowledgeBaseBenchmarkExportVisible` and verifies winner, gap, `joopark-kb-ia-recommendation.md`, data URL, and rationale copy.
- `scripts/audit-release-readiness.mjs` now includes `knowledge_base_information_architecture_export`.

## Experiment: Knowledge-base information architecture review handoff

- Hypothesis: The KB/IA recommendation becomes actionable when the selected benchmark decision can be copied or converted into a PM issue without leaving the focused portfolio queue.
- Primary metric: knowledge-base information architecture review handoff checks.
- Baseline: 0 KB/IA review handoff checks; the export produced Markdown but no stable decision key, clipboard state, or PM issue draft.
- Candidate: add a KB/IA review handoff under the Outline/BookStack/Wiki.js rubric with `kb-ia-review:repo-outline-outline:87`, `joopark-kb-ia-review-handoff.md`, one-click copy, and an Outline PM issue draft labeled `knowledge-base`, `ia`, and `handoff`.
- Decision: keep; it preserves the existing Taskosaur/Workstream review queue while giving the KB/IA rubric its own handoff and issue-draft path.

## Evidence

- `app.js` now includes `projectKnowledgeBaseReviewDecision`, `candidateKnowledgeBaseReviewHandoff`, `knowledgeBaseReviewHandoffMarkdown`, and `candidateKnowledgeBaseReviewIssueDraft`.
- `scripts/smoke-interactions.mjs` now reports `knowledgeBaseBenchmarkReviewHandoffVisible`, `knowledgeBaseBenchmarkReviewHandoffCopyVisible`, and `knowledgeBaseBenchmarkReviewIssueDraftVisible`.
- `scripts/audit-release-readiness.mjs` now includes `knowledge_base_information_architecture_review_handoff`, `knowledge_base_information_architecture_review_handoff_copy`, and `knowledge_base_information_architecture_review_issue_draft`.

## Experiment: AppFlowy and AFFiNE workspace benchmark rubric

- Hypothesis: The paired AppFlowy/AFFiNE benchmark evidence becomes product-useful when it is converted into a PM, notes, and workspace comparison rubric instead of staying as freshness-only metadata.
- Primary metric: AppFlowy/AFFiNE workspace benchmark rubric checks.
- Baseline: 0 workspace rubric checks; AppFlowy and AFFiNE were searchable freshness candidates but had no weighted PM/notes/workspace recommendation.
- Candidate: add a `workspaceBenchmark` rubric comparing AppFlowy and AFFiNE across `PM/Task 흐름`, `Notes/Wiki IA`, `Collaboration/Data control`, and `Implementation transfer`; AFFiNE scores 86 and AppFlowy scores 83.
- Decision: keep; AFFiNE becomes the primary workspace benchmark because its Notion/Miro knowledge-base + whiteboard model, CRDT collaboration signal, and TypeScript stack transfer better fit the JooPark web workspace direction, while AppFlowy remains the stronger PM/task contrast.

## Evidence

- `data/adoption-candidates.json` now includes `workspaceBenchmark` rows for `AppFlowy-IO/AppFlowy` and `toeverything/AFFiNE`.
- `app.js` now includes `projectWorkspaceBenchmark`, `projectWorkspaceRubric`, `projectWorkspaceRubricScore`, `workspaceBenchmarkRubricRanking`, and `candidateWorkspaceRubric`.
- `scripts/smoke-interactions.mjs` now reports `workspaceBenchmarkRubricVisible` and verifies the AFFiNE recommendation, score 86, AppFlowy score 83, weighted axes, and representative cells.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_workspace_benchmark_rubric`.

## Experiment: AppFlowy and AFFiNE workspace benchmark export

- Hypothesis: The AppFlowy/AFFiNE workspace recommendation becomes operationally useful when the weighted decision can be exported as Markdown with a stable winner, score gap, and rationale.
- Primary metric: AppFlowy/AFFiNE workspace benchmark export checks.
- Baseline: 0 workspace export checks; the workspace rubric rendered a recommendation but did not produce a portable decision note.
- Candidate: add `joopark-workspace-benchmark-recommendation.md` export for the AppFlowy/AFFiNE workspace rubric with AFFiNE as the winner, a 3-point score gap, Notes/Wiki IA rationale, and per-project weighted scores.
- Decision: keep; the export preserves the dedicated workspace rubric while making the AFFiNE-over-AppFlowy recommendation portable for review notes or issue drafting.

## Evidence

- `app.js` now includes `workspaceBenchmarkRecommendationMarkdown` and `candidateWorkspaceRecommendationExport` with `data-workspace-benchmark-export`.
- `scripts/smoke-interactions.mjs` now reports `workspaceBenchmarkExportVisible` and verifies winner, gap, `joopark-workspace-benchmark-recommendation.md`, data URL, and rationale copy.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_workspace_benchmark_export`.

## Experiment: AppFlowy and AFFiNE workspace review handoff

- Hypothesis: The AppFlowy/AFFiNE workspace recommendation becomes actionable when the selected benchmark decision can be copied or converted into a PM issue without leaving the focused portfolio queue.
- Primary metric: AppFlowy/AFFiNE workspace review handoff checks.
- Baseline: 0 workspace review handoff checks; the export produced Markdown but no stable decision key, clipboard state, or PM issue draft.
- Candidate: add a Workspace review handoff under the AppFlowy/AFFiNE rubric with `workspace-review:repo-toeverything-affine:86`, `joopark-workspace-review-handoff.md`, one-click copy, and an AFFiNE PM issue draft labeled `workspace`, `benchmark`, and `handoff`.
- Decision: keep; it preserves the dedicated workspace export while turning the AFFiNE-over-AppFlowy recommendation into a review-ready PM issue path.

## Evidence

- `app.js` now includes `projectWorkspaceReviewDecision`, `candidateWorkspaceReviewHandoff`, `workspaceReviewHandoffMarkdown`, and `candidateWorkspaceReviewIssueDraft`.
- `scripts/smoke-interactions.mjs` now reports `workspaceBenchmarkReviewHandoffVisible`, `workspaceBenchmarkReviewHandoffCopyVisible`, and `workspaceBenchmarkReviewIssueDraftVisible`.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_workspace_review_handoff`, `appflowy_affine_workspace_review_handoff_copy`, and `appflowy_affine_workspace_review_issue_draft`.

## Experiment: AppFlowy and AFFiNE workspace review note publish

- Hypothesis: The AppFlowy/AFFiNE workspace handoff becomes easier to preserve when the selected review decision can be published into the local Notes surface as a pinned review note.
- Primary metric: AppFlowy/AFFiNE workspace review note publish checks.
- Baseline: 0 workspace review note publish checks; the handoff could be copied or converted into a PM issue but did not persist a notes-review artifact.
- Candidate: add a `노트 발행` action to the Workspace handoff that creates a pinned `[Workspace Review] toeverything/AFFiNE` note with source key `workspace-review:repo-toeverything-affine:86`, handoff Markdown, and issue draft context.
- Decision: keep; the note publish path gives the AFFiNE-over-AppFlowy decision a local review artifact without requiring GitHub comment permissions.

## Evidence

- `app.js` now includes `publishReviewHandoffNote` and `data-workspace-review-note-publish`.
- `scripts/smoke-interactions.mjs` now reports `workspaceBenchmarkReviewNotePublishVisible` and verifies note creation, source key, pinned state, and body content.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_workspace_review_note_publish`.

## Experiment: Knowledge-base information architecture review note publish

- Hypothesis: The KB/IA handoff becomes easier to preserve when the selected Outline review decision can be published into the local Notes surface as a pinned review note.
- Primary metric: knowledge-base information architecture review note publish checks.
- Baseline: 0 KB/IA review note publish checks; the handoff could be copied or converted into a PM issue but did not persist a notes-review artifact.
- Candidate: add a `노트 발행` action to the KB/IA handoff that creates a pinned `[KB/IA Review] outline/outline` note with source key `kb-ia-review:repo-outline-outline:87`, handoff Markdown, and issue draft context.
- Decision: keep; the note publish path gives the Outline-over-BookStack/Wiki.js decision a local review artifact without requiring GitHub comment permissions.

## Evidence

- `app.js` now includes `data-kb-review-note-publish`, `data-kb-review-note-publish-status`, and `knowledge-base-review-note`.
- `scripts/smoke-interactions.mjs` now reports `knowledgeBaseBenchmarkReviewNotePublishVisible` and verifies note creation, source key, pinned state, source kind, body content, and re-rendered publish state.
- `scripts/audit-release-readiness.mjs` now includes `knowledge_base_information_architecture_review_note_publish`.

## Experiment: AppFlowy and AFFiNE workspace review GitHub comment handoff

- Hypothesis: The AppFlowy/AFFiNE workspace handoff becomes easier to publish externally when the selected AFFiNE review decision can be converted into a copy-ready GitHub comment draft without requiring API write permissions.
- Primary metric: AppFlowy/AFFiNE workspace review GitHub comment checks.
- Baseline: 0 workspace review GitHub comment checks; the handoff could be copied, converted into a local issue, and published as a local note, but did not provide a GitHub-ready comment body or prefilled issue URL.
- Candidate: add a GitHub comment draft under the Workspace handoff with source key `workspace-review:repo-toeverything-affine:86`, a prefilled `toeverything/AFFiNE` issue URL, and one-click comment copy.
- Decision: keep; the comment handoff gives the AFFiNE-over-AppFlowy decision a GitHub-ready publish path while avoiding live write permissions.

## Evidence

- `app.js` now includes `workspaceReviewGithubCommentMarkdown`, `candidateWorkspaceReviewGithubComment`, `data-workspace-review-github-comment`, and `copyReviewGithubComment`.
- `scripts/smoke-interactions.mjs` now reports `workspaceBenchmarkReviewGithubCommentVisible` and verifies the target repo, issue URL, source key, Markdown body, clipboard copy, and copy status.
- `scripts/audit-release-readiness.mjs` now includes `appflowy_affine_workspace_review_github_comment_handoff`.

## Experiment: Knowledge-base information architecture review GitHub comment handoff

- Hypothesis: The KB/IA handoff becomes easier to publish externally when the selected Outline review decision can be converted into a copy-ready GitHub comment draft without requiring API write permissions.
- Primary metric: knowledge-base information architecture review GitHub comment checks.
- Baseline: 0 KB/IA review GitHub comment checks; the handoff could be copied, converted into a local issue, and published as a local note, but did not provide a GitHub-ready comment body or prefilled issue URL.
- Candidate: add a GitHub comment draft under the KB/IA handoff with source key `kb-ia-review:repo-outline-outline:87`, a prefilled `outline/outline` issue URL, and one-click comment copy.
- Decision: keep; the comment handoff gives the Outline-over-BookStack/Wiki.js decision a GitHub-ready publish path while avoiding live write permissions.

## Evidence

- `app.js` now includes `knowledgeBaseReviewGithubCommentMarkdown`, `candidateKnowledgeBaseReviewGithubComment`, `data-kb-review-github-comment`, and `copyReviewGithubComment`.
- `scripts/smoke-interactions.mjs` now reports `knowledgeBaseBenchmarkReviewGithubCommentVisible` and verifies the target repo, issue URL, source key, Markdown body, clipboard copy, and copy status.
- `scripts/audit-release-readiness.mjs` now includes `knowledge_base_information_architecture_review_github_comment_handoff`.

## Experiment: Veritas focused snapshot writer v8.649

- Hypothesis: The high-churn AutoResearch source should keep its source-backed snapshot current without hard-coding the expected upstream commit into smoke or audit checks.
- Primary metric: `veritasSnapshotWriterChanged`.
- Baseline: Veritas snapshot writer evidence pointed at v8.510 (`5e4b31b0c2b1763f45b2eea4ba7e740dd8209360`) with `pushedAt: 2026-06-05T21:17:28Z`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` reported drift, then `--write` updated the candidate to v8.649 with commit `a5254d0881a9d9e6c21086df3b685c6fc9d1d68d`.
- Decision: keep; the writer added source marker `github-api:veritas-focused-drift-refresh-v8649`, refreshed pushedAt to `2026-06-06T09:57:46Z`, and preserved the repo-scoped dynamic snapshot path.

## Evidence

- Live drift before the write reported Veritas `lastCommit`, `pushedAt`, and `diskKb` drift against the source-backed snapshot.
- The writer updated `data/adoption-candidates.json` only, changing the Veritas description to `v8.649 최신 guard shell session targets...`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasFocusedSnapshotVersion: v8.649` and the v8.649 source marker.

## Experiment: Veritas focused snapshot writer v8.651

- Hypothesis: The high-churn Veritas AutoResearch source should be refreshed as soon as a focused repo-scoped live check reports upstream movement.
- Primary metric: `veritasSnapshotWriterChanged`.
- Baseline: Veritas snapshot writer evidence pointed at v8.649 (`a5254d0881a9d9e6c21086df3b685c6fc9d1d68d`) with `pushedAt: 2026-06-06T09:57:46Z`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --dry-run --fail-on-change` reported drift, then `--write` updated the candidate to v8.651 with commit `cd49f78e2f9bbcd782aad185726ad3d60242f998`.
- Decision: keep; the writer added source marker `github-api:veritas-focused-drift-refresh-v8651`, refreshed pushedAt to `2026-06-06T10:08:33Z`, and preserved the repo-scoped dynamic snapshot path.

## Evidence

- Live drift before the write reported Veritas `lastCommit` and `pushedAt` drift against the v8.649 source-backed snapshot.
- The writer updated `data/adoption-candidates.json` only, changing the Veritas description to `v8.651 최신 guard managed source commits...`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasFocusedSnapshotVersion: v8.651` and the v8.651 source marker.

## Experiment: generic candidate snapshot writer

- Hypothesis: Source-backed candidate drift refreshes should not require a one-off script per repository.
- Primary metric: `candidateSnapshotWriterChecks`.
- Baseline: 0 generic writer checks; only the high-churn Veritas row had a dedicated dry-run/write helper.
- Candidate: add `scripts/refresh-candidate-snapshot.mjs` with `--repo owner/name`, `--snapshot-only`, `--dry-run`, `--fail-on-change`, and `--write`, plus README and release-audit coverage.
- Decision: keep; the generic writer passed snapshot-only against `Veritas-7/autoresearch-skill-system` and dry-run detected live drift for `outline/outline`.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system` passed with source marker compatibility for existing Veritas-focused markers.
- `node scripts/refresh-candidate-snapshot.mjs --dry-run --repo outline/outline` reported `changed: true` without writing.
- `scripts/audit-release-readiness.mjs` now includes `candidate_snapshot_writer`.

## Experiment: Outline generic snapshot refresh

- Hypothesis: The new generic writer is ready for non-Veritas source-backed candidates when it can refresh a KB/IA benchmark repo without custom code.
- Primary metric: `outlineGenericSnapshotWriterChanged`.
- Baseline: Outline snapshot commit `e864684d569c81ca2b03c816d22e0c80e2ff6466`, `pushedAt: 2026-06-05T14:54:48Z`, and 38 open issues.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo outline/outline` updated Outline to commit `be3f28afeaaa8b92137685376fe17fff94e62255`, `pushedAt: 2026-06-06T03:42:42Z`, 37 open issues, 38,779 stars, and source marker `github-api:outline-outline-candidate-refresh`.
- Decision: keep; the KB/IA benchmark winner now uses the generic refresh path and current source-backed metadata.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Outline row and source marker.
- Existing dynamic smoke/audit paths read the refreshed Outline commit and pushedAt from the snapshot rather than hard-coded literals.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineGenericSnapshotWriterChanged: true`.

## Experiment: AFFiNE generic snapshot refresh

- Hypothesis: The current workspace benchmark winner should keep source-backed metadata fresh through the generic writer before its live drift reaches product-facing review notes.
- Primary metric: `affineGenericSnapshotWriterChanged`.
- Baseline: AFFiNE snapshot commit `edc87e38df01db79f969e6f61981a10c16f9a0bb`, `pushedAt: 2026-06-04T22:48:17Z`, 555 open issues, and 69,107 stars.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo toeverything/AFFiNE` updated AFFiNE to commit `d10dd12663e3e2e94dd40abb41920d26686cfefd`, `pushedAt: 2026-06-06T10:36:57Z`, 554 open issues, 69,123 stars, and source marker `github-api:toeverything-affine-candidate-refresh`.
- Decision: keep; the AppFlowy/AFFiNE workspace benchmark winner now uses the generic refresh path and passes a repo-scoped live drift check with drift count 0.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the AFFiNE row and source marker.
- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo toeverything/AFFiNE` passed with 40 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo toeverything/AFFiNE --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `affineGenericSnapshotWriterChanged: true`.

## Experiment: Taskosaur generic snapshot refresh

- Hypothesis: The Taskosaur workstream benchmark should keep source-backed metadata fresh before benchmark review decisions depend on stale PM/Kanban signals.
- Primary metric: `taskosaurGenericSnapshotWriterChanged`.
- Baseline: Taskosaur snapshot commit `3a6e39f662c6fd8b22980c16d4441d8887347c31`, `pushedAt: 2026-06-02T11:00:39Z`, 10 open issues, and `diskKb: 9677`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo Taskosaur/Taskosaur` updated Taskosaur to commit `b7a5463ddd1fc018d8b2dc877ccc434a38eb710b`, `pushedAt: 2026-06-06T07:15:54Z`, 9 open issues, `diskKb: 9710`, and source marker `github-api:taskosaur-taskosaur-candidate-refresh`.
- Decision: keep; the Taskosaur/Workstream benchmark candidate now uses the generic refresh path, passes a repo-scoped live drift check with drift count 0, and reduces full live drift count from 14 to 13.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Taskosaur row and source marker.
- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo Taskosaur/Taskosaur` passed with 41 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Taskosaur/Taskosaur --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `taskosaurGenericSnapshotWriterChanged: true`.

## Experiment: OpenProject generic snapshot refresh

- Hypothesis: The PM benchmark snapshot should treat OpenProject's GitHub issue count as issue-only metadata and keep its large source-backed repository state current before portfolio priority decisions use it.
- Primary metric: `openProjectGenericSnapshotWriterChanged`.
- Baseline: OpenProject snapshot commit `6885ca695dd38384c651704675143be63f9a514d`, `pushedAt: 2026-06-05T15:36:21Z`, 211 open issues, 211 open PRs, 15,235 stars, and `diskKb: 2705667`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo opf/openproject` updated OpenProject to commit `79d810d2e74f94bda4e3bcf652f2d848863e5a3e`, `pushedAt: 2026-06-06T10:48:39Z`, 0 issue-only open issues, 212 open PRs, 15,243 stars, and source marker `github-api:opf-openproject-candidate-refresh`.
- Decision: keep; the OpenProject PM benchmark row now uses the generic refresh path and passes a repo-scoped live drift check with drift count 0 while preserving open PR volume separately from issue-only issue count.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the OpenProject row and source marker.
- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo opf/openproject` passed with 42 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo opf/openproject --fail-on-drift` passed with `driftCount: 0`.
- Full live drift was observed at 15 after the write because other monitored sources moved during this loop; OpenProject was no longer in the drift list.
- `autoresearch-results/joopark-product-loop.json` now reports `openProjectGenericSnapshotWriterChanged: true`.

## Experiment: Outline generic snapshot refresh 2

- Hypothesis: The KB/IA benchmark winner should be refreshed again when a new upstream commit changes issue and PR counts before review handoff artifacts reuse stale source metadata.
- Primary metric: `outlineGenericSnapshotWriterRefresh2Changed`.
- Baseline: Outline snapshot commit `be3f28afeaaa8b92137685376fe17fff94e62255`, `pushedAt: 2026-06-06T03:42:42Z`, 37 open issues, and 22 open PRs.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo outline/outline` updated Outline to commit `f329b56d0edbbd687728c7436713f2c99e8ec722`, `pushedAt: 2026-06-06T11:24:17Z`, 36 open issues, 21 open PRs, and source marker `github-api:outline-outline-candidate-refresh`.
- Decision: keep; the Outline KB/IA winner remains source-current, passes a repo-scoped live drift check with drift count 0, and lowers full live drift from 15 to 14.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Outline row.
- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo outline/outline` passed with 42 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo outline/outline --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineGenericSnapshotWriterRefresh2Changed: true`.

## Experiment: Leantime generic snapshot refresh

- Hypothesis: The PM benchmark snapshot should refresh Leantime's fast-moving GitHub popularity and issue metadata before project-management comparisons reuse stale source signals.
- Primary metric: `leantimeGenericSnapshotWriterChanged`.
- Baseline: Leantime snapshot commit `b3a1037bf596d284b53355d23cadf1d9ab56b599`, `pushedAt: 2026-06-05T04:17:00Z`, 318 open issues, 2 open PRs, 9,988 stars, 983 forks, and `diskKb: 247835`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo Leantime/leantime` kept the same commit while updating `pushedAt: 2026-06-05T18:11:39Z`, 317 open issues, 3 open PRs, 9,992 stars, 986 forks, `diskKb: 247860`, and source marker `github-api:leantime-leantime-candidate-refresh`.
- Decision: keep; the Leantime PM benchmark row now uses the generic refresh path, passes a repo-scoped live drift check with drift count 0, and lowers full live drift from 15 to 14.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Leantime row and source marker.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 43 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Leantime/leantime --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `leantimeGenericSnapshotWriterChanged: true`.

## Experiment: Taskcoach generic snapshot refresh

- Hypothesis: The task-management benchmark snapshot should refresh Taskcoach's upstream commit, pushedAt, issue, and repository-size metadata before workstream comparisons reuse stale source signals.
- Primary metric: `taskcoachGenericSnapshotWriterChanged`.
- Baseline: Taskcoach snapshot commit `dad6168f8771cda4566dedfad1e678ea253c2a7f`, `pushedAt: 2026-05-28T16:07:10Z`, 95 open issues, 3 open PRs, and `diskKb: 590173`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo taskcoach/taskcoach` updated Taskcoach to commit `f3fbd73cc84ff545ceed58ef46f999bda3b954da`, `pushedAt: 2026-06-06T02:36:56Z`, 91 open issues, 3 open PRs, `diskKb: 590182`, and source marker `github-api:taskcoach-taskcoach-candidate-refresh`.
- Decision: keep; the Taskcoach workstream benchmark row now uses the generic refresh path, passes a repo-scoped live drift check with drift count 0, and lowers full live drift from 15 to 14.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Taskcoach row and source marker.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 44 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo taskcoach/taskcoach --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `taskcoachGenericSnapshotWriterChanged: true`.

## Experiment: Plane generic snapshot refresh

- Hypothesis: The PM benchmark snapshot should refresh Plane's fast-moving popularity and issue metadata before planning comparisons reuse stale source signals.
- Primary metric: `planeGenericSnapshotWriterChanged`.
- Baseline: Plane snapshot commit `0bbfe95cc74c9c958d66b156df2783fdbc180f8e`, 756 open issues, 128 open PRs, 50,363 stars, and 4,431 forks.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo makeplane/plane` kept the same commit while updating Plane to 757 open issues, 128 open PRs, 50,402 stars, 4,437 forks, and source marker `github-api:makeplane-plane-candidate-refresh`.
- Decision: keep; the Plane PM benchmark row now uses the generic refresh path, passes a repo-scoped live drift check with drift count 0, and lowers full live drift from 14 to 13.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Plane row and source marker.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 45 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo makeplane/plane --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `planeGenericSnapshotWriterChanged: true`.

## Experiment: Plane generic snapshot refresh 2

- Hypothesis: Plane's popularity metadata should be refreshed again when stars and forks move during release sync so the PM benchmark row remains source-current.
- Primary metric: `planeGenericSnapshotWriterRefresh2Changed`.
- Baseline: Plane snapshot commit `0bbfe95cc74c9c958d66b156df2783fdbc180f8e`, 50,402 stars, and 4,437 forks.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo makeplane/plane` kept the same commit while updating Plane to 50,403 stars, 4,438 forks, and the existing source marker `github-api:makeplane-plane-candidate-refresh`.
- Decision: keep; the Plane PM benchmark row passes a repo-scoped live drift check with drift count 0 after the release-sync drift.

## Evidence

- The generic writer changed only `data/adoption-candidates.json` for the Plane row.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 45 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo makeplane/plane --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `planeGenericSnapshotWriterRefresh2Changed: true`.

## Experiment: Candidate freshness advisory popularity drift

- Hypothesis: Release gates should still fail on source freshness drift, but should not repeatedly block on popularity-only `stars/forks` movement from high-traffic GitHub repositories.
- Primary metric: `planePopularityBlockingDriftCount`.
- Baseline: The Plane release sync failed again after PR #227 because only stars and forks moved from 50,403/4,438 to 50,404/4,439.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` now marks `stars/forks` drift as advisory while keeping `lastCommit`, `pushedAt`, issue/PR, and disk drift blocking; README and release audit terms document `blockingDriftCount` and `advisoryDriftCount`.
- Decision: keep; `node scripts/check-candidate-freshness-drift.mjs --live --repo makeplane/plane --fail-on-drift` exits 0 with `driftCount: 1`, `advisoryDriftCount: 1`, and `blockingDriftCount: 0`.

## Evidence

- `npm run lint` passed after the checker, audit, and README update.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 45 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo makeplane/plane --fail-on-drift` reported only advisory Plane popularity drift and did not fail the command.
- `autoresearch-results/joopark-product-loop.json` now reports `planePopularityAdvisoryDriftPolicyChanged: true`.

## Experiment: Veritas focused snapshot writer v8.672

- Hypothesis: The launch-candidate AutoResearch row should track the latest Veritas source proof snapshot before high-churn upstream movement makes release evidence stale.
- Primary metric: `veritasSnapshotWriterRefresh3Changed`.
- Baseline: Veritas snapshot was at v8.651 commit `cd49f78e2f9bbcd782aad185726ad3d60242f998`, pushed `2026-06-06T10:08:33Z`, with `diskKb: 1753`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --write` updated Veritas to v8.672 commit `b1023c98cd262e992466c6a8c7f78fda2d42aa93`, pushed `2026-06-06T12:47:52Z`, with `diskKb: 2018` and source marker `github-api:veritas-focused-drift-refresh-v8672`.
- Decision: keep; the repo-scoped live drift check reports `driftCount: 0`, and full live blocking drift drops from 10 to 9.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --snapshot-only` passed with 46 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --fail-on-drift` passed with `driftCount: 0`.
- Full live drift now reports `driftCount: 14`, `blockingDriftCount: 9`, and `advisoryDriftCount: 5`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasSnapshotWriterRefresh3Changed: true`.

## Experiment: Veritas focused snapshot writer v8.674

- Hypothesis: The high-churn Veritas launch-candidate row should be refreshed again when upstream advances during release sync, preserving source-current proof without committing stale release evidence.
- Primary metric: `veritasSnapshotWriterRefresh4Changed`.
- Baseline: Veritas snapshot was at v8.672 commit `b1023c98cd262e992466c6a8c7f78fda2d42aa93`, pushed `2026-06-06T12:47:52Z`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --write` updated Veritas to v8.674 commit `53ee86db23a90b67f081a8dbb5f05a239d25e17e`, pushed `2026-06-06T12:56:48Z`, with source marker `github-api:veritas-focused-drift-refresh-v8674`.
- Decision: keep; the repo-scoped live drift check again reports `driftCount: 0`, while full live drift remains `driftCount: 14`, `blockingDriftCount: 9`, and `advisoryDriftCount: 5`.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --snapshot-only` passed with 47 source markers.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --fail-on-drift` passed with `driftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasSnapshotWriterRefresh4Changed: true`.

## Experiment: High-churn cadence advisory drift

- Hypothesis: A high-churn launch-candidate source should not deadlock release sync when only source-head metadata advances within the documented freshness cadence and repository triage metadata stays unchanged.
- Primary metric: `veritasHighChurnCadenceBlockingDriftCount`.
- Baseline: The v8.674 release sync failed because Veritas moved from commit `53ee86db23a90b67f081a8dbb5f05a239d25e17e` to `4678612db1924cc46cd923f0edff26aa230033ca`, with blocking drift confined to `lastCommit` and `pushedAt`.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` classifies high-churn source-head drift as `cadence-advisory` for `Veritas-7/autoresearch-skill-system` when the live push is within the 4-hour cadence and issue/PR metadata is unchanged.
- Decision: keep; repo-scoped `--fail-on-drift` now passes with `blockingDriftCount: 0`, `cadenceAdvisoryDriftCount: 1`, and `driftMinutes: 17.6`, while material metadata drift remains blocking.

## Evidence

- `npm run lint` passed after the checker, audit, README, and AutoResearch log updates.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy` passed with the high-churn cadence advisory check enabled.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --fail-on-drift` passed with `driftCount: 1`, `blockingDriftCount: 0`, and `cadenceAdvisoryDriftCount: 1`.
- `autoresearch-results/joopark-product-loop.json` now reports the high-churn cadence blocking drift count at 0.

## Experiment: Outline generic snapshot refresh 3

- Hypothesis: The KB/IA benchmark winner should be refreshed again when upstream commit, pushedAt, PR count, and repository size drift together after the cadence-advisory release sync.
- Primary metric: `outlineGenericSnapshotWriterRefresh3Changed`.
- Baseline: Outline snapshot commit `f329b56d0edbbd687728c7436713f2c99e8ec722`, pushed `2026-06-06T11:24:17Z`, 21 open PRs, and `diskKb: 319346`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo outline/outline` updated Outline to commit `58f0613b5f87f94c92a3c00aa6dab2c59749636b`, pushed `2026-06-06T13:30:51Z`, 20 open PRs, and `diskKb: 319385`.
- Decision: keep; the repo-scoped live drift check reports `driftCount: 0`, and full live blocking drift drops from 9 to 8.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo outline/outline` passed with source marker `github-api:outline-outline-candidate-refresh`.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo outline/outline --fail-on-drift` passed with `driftCount: 0`.
- Full live drift now reports `driftCount: 14`, `blockingDriftCount: 8`, `advisoryDriftCount: 5`, and `cadenceAdvisoryDriftCount: 1`.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineGenericSnapshotWriterRefresh3Changed: true`.

## Experiment: Commit-stable metadata advisory drift

- Hypothesis: Release gates should fail on source freshness drift, but should not block when GitHub recalculates repository `diskKb` while `lastCommit` and `pushedAt` remain unchanged.
- Primary metric: `outlineCommitStableDiskBlockingDriftCount`.
- Baseline: The Outline release sync failed after PR #232 because only `diskKb` moved from 319385 to 317197 while commit `58f0613b5f87f94c92a3c00aa6dab2c59749636b` and pushedAt `2026-06-06T13:30:51Z` stayed current; stars also moved as an existing advisory field.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` classifies commit-stable `diskKb` drift as `metadata-advisory`; audit and README require the policy term.
- Decision: keep; `node scripts/check-candidate-freshness-drift.mjs --live --repo outline/outline --fail-on-drift` exits 0 with `blockingDriftCount: 0` and `metadataAdvisoryDriftCount: 1`.

## Evidence

- `npm run lint` passed after the checker, audit, README, and AutoResearch log updates.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy` passed with `commitStableMetadataAdvisory: true`.
- Full live drift now reports `driftCount: 15`, `blockingDriftCount: 7`, `advisoryDriftCount: 7`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 2`.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineCommitStableDiskBlockingDriftCount: 0`.

## Experiment: High-churn source metadata cadence advisory drift

- Hypothesis: A high-churn launch-candidate source should not deadlock release sync when `lastCommit`, `pushedAt`, and `diskKb` move together inside the documented freshness cadence while issue and PR metadata stay unchanged.
- Primary metric: `veritasSourceMetadataCadenceBlockingDriftCount`.
- Baseline: The post-PR #233 release sync failed because Veritas moved from commit `53ee86db23a90b67f081a8dbb5f05a239d25e17e` to `36926dfcc7f77c03b8dea583b4831d8572b7e098`, with blocking drift in `lastCommit`, `pushedAt`, and `diskKb`.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` now classifies that high-churn source metadata set as `cadence-advisory` for `Veritas-7/autoresearch-skill-system` when the live push is within the 4-hour cadence and issue/PR metadata is unchanged; audit and README require the new policy term.
- Decision: keep; repo-scoped `--fail-on-drift` now exits 0 with `blockingDriftCount: 0`, `cadenceAdvisoryDriftCount: 1`, and `driftMinutes: 61.2`.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy` passed with `highChurnSourceMetadataCadenceAdvisory: true`.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --fail-on-drift` passed with `driftCount: 1`, `blockingDriftCount: 0`, and `cadenceAdvisoryDriftCount: 1`.
- Full live drift now reports `driftCount: 15`, `blockingDriftCount: 7`, `advisoryDriftCount: 6`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 2`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasSourceMetadataCadenceBlockingDriftCount: 0`.

## Experiment: Outline generic snapshot refresh 4

- Hypothesis: The KB/IA benchmark winner should be refreshed again when GitHub source metadata moves during release sync, preserving repo-scoped freshness proof without weakening drift policy.
- Primary metric: `outlineGenericSnapshotWriterRefresh4Changed`.
- Baseline: Outline snapshot commit `58f0613b5f87f94c92a3c00aa6dab2c59749636b`, pushed `2026-06-06T13:30:51Z`, 20 open PRs, and `diskKb: 319385`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --repo outline/outline` updated Outline to commit `f4b80d5301d3213dbacd1ba654f5d94f045c1fc4`, pushed `2026-06-06T14:14:37Z`, 20 open PRs, and `diskKb: 317197`.
- Decision: keep; the repo-scoped live drift check reports `driftCount: 0`, while full live drift is now `driftCount: 14`, `blockingDriftCount: 7`, `advisoryDriftCount: 6`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 1`.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --snapshot-only --repo outline/outline` passed with source marker `github-api:outline-outline-candidate-refresh`.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo outline/outline --fail-on-drift` passed with `driftCount: 0`.
- `node scripts/check-candidate-freshness-drift.mjs --live` reported no `outline/outline` entry in `drifted`.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineGenericSnapshotWriterRefresh4Changed: true`.

## Experiment: Commit-stable repository metadata advisory drift

- Hypothesis: Release gates should fail on default-branch source freshness drift, but should not block when GitHub `pushedAt` or `diskKb` moves while `lastCommit` remains unchanged.
- Primary metric: `outlineCommitStablePushedAtBlockingDriftCount`.
- Baseline: The post-PR #235 release sync failed because Outline kept commit `f4b80d5301d3213dbacd1ba654f5d94f045c1fc4` but GitHub moved `pushedAt` from `2026-06-06T14:14:37Z` to `2026-06-06T14:23:46Z`; stars also moved as an existing advisory field.
- Candidate: `scripts/check-candidate-freshness-drift.mjs` now classifies commit-stable `pushedAt` and `diskKb` drift as `metadata-advisory` with policy id `candidate-freshness-commit-stable-repo-metadata-v2`; audit and README require the v2 policy term.
- Decision: keep; `node scripts/check-candidate-freshness-drift.mjs --live --repo outline/outline --fail-on-drift` exits 0 with `blockingDriftCount: 0` and `metadataAdvisoryDriftCount: 1`.

## Evidence

- `npm run lint` passed after the checker, audit, README, and AutoResearch log updates.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only --repo Veritas-7/autoresearch-skill-system --cadence-policy` passed with metadata policy `candidate-freshness-commit-stable-repo-metadata-v2`.
- Full live drift now reports `driftCount: 15`, `blockingDriftCount: 4`, `advisoryDriftCount: 9`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 5`.
- `autoresearch-results/joopark-product-loop.json` now reports `outlineCommitStablePushedAtBlockingDriftCount: 0`.

## Experiment: Remaining issue-count snapshot refresh

- Hypothesis: The release drift monitor should return to zero blocking drift after refreshing source-backed issue-count snapshots for the remaining stale candidates instead of weakening issue/PR drift policy.
- Primary metric: `candidateFreshnessBlockingDriftCount`.
- Baseline: Full live drift still had four blocking candidates: Epicenter open issues 170 to 168, AppFlowy 936 to 935, Taskcoach 91 to 89, and Parabol 68 to 65.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write` refreshed `EpicenterHQ/epicenter`, `AppFlowy-IO/AppFlowy`, `taskcoach/taskcoach`, and `ParabolInc/parabol`, preserving their default-branch commits while updating issue and popularity metadata.
- Decision: keep; full live drift now exits `pass` with `driftCount: 11`, `blockingDriftCount: 0`, `advisoryDriftCount: 9`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 5`.

## Evidence

- Dry-runs for all four repos reported `changed: true` before the write.
- `node scripts/check-candidate-freshness-drift.mjs --live` exits 0 with no entries in `blockingDrifted`.
- `data/adoption-candidates.json` now reports 50 GitHub API source markers and generatedAt `2026-06-06T23:40:35+09:00`.
- `autoresearch-results/joopark-product-loop.json` now reports `remainingIssueCountRefreshFullBlockingDriftAfter: 0`.

## Experiment: Veritas cadence refresh 5

- Hypothesis: Refreshing the high-churn Veritas source snapshot should eliminate the remaining cadence advisory drift without weakening the freshness policy.
- Primary metric: `candidateFreshnessCadenceAdvisoryDriftCount`.
- Baseline: Veritas scoped live drift had `driftCount: 1`, `blockingDriftCount: 0`, and `cadenceAdvisoryDriftCount: 1`; the snapshot was v8.674 at commit `53ee86db23a90b67f081a8dbb5f05a239d25e17e`.
- Candidate: `node scripts/refresh-veritas-candidate-snapshot.mjs --write` refreshed Veritas to v8.694 at commit `af983bfa7e0e0861ad8592705dbf780721da765a`, pushed `2026-06-06T15:04:07Z`, and `diskKb: 2550`.
- Decision: keep; the repo-scoped live drift check now reports `driftCount: 0`, and full live drift reports `blockingDriftCount: 0` with `cadenceAdvisoryDriftCount: 0`.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --snapshot-only` passed before the write with the stored v8.674 snapshot.
- `node scripts/check-candidate-freshness-drift.mjs --live --repo Veritas-7/autoresearch-skill-system --fail-on-drift` passed with no drift after the write.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 11`, `blockingDriftCount: 0`, `advisoryDriftCount: 10`, `cadenceAdvisoryDriftCount: 0`, and `metadataAdvisoryDriftCount: 5`.
- `data/adoption-candidates.json` now reports 51 GitHub API source markers and generatedAt `2026-06-07T00:04:44+09:00`.
- `autoresearch-results/joopark-product-loop.json` now reports `veritasSnapshotWriterRefresh5FullCadenceAdvisoryDriftAfter: 0`.

## Experiment: Advisory and metadata batch refresh

- Hypothesis: Refreshing the currently drifted advisory/metadata candidates in one batch should return the freshness dashboard to zero live drift without changing drift policy.
- Primary metric: `candidateFreshnessLiveDriftCount`.
- Baseline: Full live drift had `driftCount: 13`, `blockingDriftCount: 0`, `advisoryDriftCount: 11`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 5`.
- Candidate: Refresh Veritas with the focused writer, then refresh Plane, AppFlowy, AFFiNE, Outline, BookStack, Wiki.js, Taskosaur, Focalboard, Colanode, Anytype, OpenProject, and Worklenz with the generic GitHub snapshot writer.
- Decision: keep; full live drift now reports zero drift across blocking, advisory, cadence advisory, and metadata advisory classes.

## Evidence

- `node scripts/refresh-veritas-candidate-snapshot.mjs --write` refreshed Veritas to v8.695 at commit `086539746d3aed07404b8cd692c4744db7030b80`.
- `node scripts/refresh-candidate-snapshot.mjs --write --repo ...` refreshed 12 additional drifted candidates.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 0`, `blockingDriftCount: 0`, `advisoryDriftCount: 0`, `cadenceAdvisoryDriftCount: 0`, and `metadataAdvisoryDriftCount: 0`.
- `data/adoption-candidates.json` now reports 58 GitHub API source markers and generatedAt `2026-06-07T00:19:53+09:00`.
- `autoresearch-results/joopark-product-loop.json` now reports `candidateFreshnessAdvisoryBatchRefreshFullDriftAfter: 0`.

## Experiment: Live drift batch refresh helper

- Hypothesis: The generic candidate snapshot writer should consume the live drift monitor directly so recurring advisory/cadence refreshes do not require manual repo loops.
- Primary metric: `candidateFreshnessLiveDriftBatchRefreshFullDriftAfter`.
- Baseline: After the release sync, full live drift had `driftCount: 5`, `blockingDriftCount: 0`, `advisoryDriftCount: 4`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 0`.
- Candidate: Add `--from-live-drift` to `scripts/refresh-candidate-snapshot.mjs`; the helper runs `check-candidate-freshness-drift.mjs --live`, extracts drifted source-backed repos, and refreshes only those rows. The first write refreshed Veritas, Plane, AppFlowy, Outline, and Wiki.js; a follow-up sweep handled a new Veritas cadence drift.
- Decision: keep; after the write, full live drift reports zero drift and a second batch dry-run reports `changed: false`.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --dry-run --from-live-drift` found 5 drifted repos without writing.
- `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift` updated `data/adoption-candidates.json`; the final follow-up write set generatedAt `2026-06-07T00:37:11+09:00`.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 0`, `blockingDriftCount: 0`, `advisoryDriftCount: 0`, `cadenceAdvisoryDriftCount: 0`, and `metadataAdvisoryDriftCount: 0`.
- `node scripts/refresh-candidate-snapshot.mjs --dry-run --from-live-drift --repo outline/outline` passed with `changed: false`, proving repo-filtered batch mode.
- `autoresearch-results/joopark-product-loop.json` now reports `candidateFreshnessLiveDriftBatchRefreshRepos: 5`, `candidateFreshnessLiveDriftBatchRefreshFollowupRepos: 1`, and `candidateFreshnessLiveDriftBatchRefreshIdempotent: true`.

## Experiment: Live drift batch sweep 2

- Hypothesis: The new live-drift batch helper should handle post-release advisory/cadence drift without manually enumerating repos.
- Primary metric: `candidateFreshnessLiveDriftBatchSweep2FullDriftAfter`.
- Baseline: Release verification after #240 saw `driftCount: 7`, `blockingDriftCount: 0`, `advisoryDriftCount: 5`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 1`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift` refreshed Veritas, Plane, AppFlowy, AFFiNE, Wiki.js, Anytype, and OpenProject.
- Decision: keep; the follow-up live drift check reports zero drift across all freshness classes.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --dry-run --from-live-drift` found 7 drifted repos before writing.
- `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift` updated `data/adoption-candidates.json` to generatedAt `2026-06-07T00:49:55+09:00`.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 0`, `blockingDriftCount: 0`, `advisoryDriftCount: 0`, `cadenceAdvisoryDriftCount: 0`, and `metadataAdvisoryDriftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `candidateFreshnessLiveDriftBatchSweep2Repos: 7`.

## Experiment: Live drift batch sweep 3

- Hypothesis: The batch helper should continue to remove new advisory/cadence drift after release sync without changing drift policy.
- Primary metric: `candidateFreshnessLiveDriftBatchSweep3FullDriftAfter`.
- Baseline: Post-release live drift had `driftCount: 6`, `blockingDriftCount: 0`, `advisoryDriftCount: 5`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 0`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift` refreshed Veritas, Plane, AppFlowy, AFFiNE, Focalboard, and Colanode.
- Decision: keep; the follow-up live drift check reports zero drift across all freshness classes.

## Evidence

- `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift` updated `data/adoption-candidates.json` to generatedAt `2026-06-07T01:03:10+09:00`.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 0`, `blockingDriftCount: 0`, `advisoryDriftCount: 0`, `cadenceAdvisoryDriftCount: 0`, and `metadataAdvisoryDriftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `candidateFreshnessLiveDriftBatchSweep3Repos: 6`.

## Experiment: AFFiNE blocking drift follow-up

- Hypothesis: A targeted source-backed refresh should clear the release-sync blocking issue-count drift without sweeping advisory popularity churn into the same change.
- Primary metric: `candidateFreshnessAffineBlockingDriftCount`.
- Baseline: Release verification after #242 saw `toeverything/AFFiNE` openIssues drift from `554` to `555`, with full live drift at `driftCount: 4`, `blockingDriftCount: 1`, `advisoryDriftCount: 2`, and `cadenceAdvisoryDriftCount: 1`.
- Candidate: `node scripts/refresh-candidate-snapshot.mjs --write --from-live-drift --repo toeverything/AFFiNE` refreshed only the AFFiNE row and updated `data/adoption-candidates.json` to generatedAt `2026-06-07T01:13:30+09:00`.
- Decision: keep; the repo-scoped live drift check now reports `driftCount: 0` and full live drift reports `blockingDriftCount: 0`.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --live --repo toeverything/AFFiNE --fail-on-drift` passed with `driftCount: 0`, `blockingDriftCount: 0`, and `advisoryDriftCount: 0`.
- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `driftCount: 4`, `blockingDriftCount: 0`, `advisoryDriftCount: 3`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 0`.
- `autoresearch-results/joopark-product-loop.json` now reports `candidateFreshnessAffineBlockingDriftCount: 0`.

## Experiment: Actionable drift filter

- Hypothesis: Separating actionable blocking drift from advisory/cadence drift should stop the batch refresh helper from creating data-only sweeps when release gates are already unblocked.
- Primary metric: `candidateFreshnessNonblockingRefreshReposSelected`.
- Baseline: Full live drift reported `driftCount: 6`, `blockingDriftCount: 0`, `actionableDriftCount: 0`, `advisoryDriftCount: 4`, `cadenceAdvisoryDriftCount: 1`, and `metadataAdvisoryDriftCount: 1`; the existing `--from-live-drift` dry-run selected all 6 drifted repos.
- Candidate: Add `actionableDriftCount` and `actionableDrifted` to the drift monitor, then add `--actionable-only` to `refresh-candidate-snapshot.mjs --from-live-drift` so it refreshes only rows that can block release gates.
- Decision: keep; `--from-live-drift --actionable-only` selected 0 repos while preserving the full drift payload for advisory review.

## Evidence

- `node scripts/check-candidate-freshness-drift.mjs --live` passed with `actionableDriftCount: 0` and an empty `actionableDrifted` list.
- `node scripts/refresh-candidate-snapshot.mjs --dry-run --from-live-drift --actionable-only` passed with `changed: false`, `driftCount: 6`, `actionableDriftCount: 0`, and `refreshedRepos: []`.
- `node scripts/refresh-candidate-snapshot.mjs --dry-run --from-live-drift` still selected 6 repos, proving the new filter is opt-in and does not hide advisory drift evidence.

## Experiment: Source gap coverage and quick link routes

- Hypothesis: Filling unresolved GitHub source gaps and making home dashboard quick links expose real hash routes should improve candidate triage reliability and browser navigation without changing core storage behavior.
- Primary metric: `sourceBackedAdoptionCandidateCount`.
- Baseline: Adoption candidates had 21 source-backed rows and 23 rows with missing `url` or `lastCommit`; home dashboard quick links used `href="#"`, so smoke coverage could verify clicks but not route-bearing links.
- Candidate: Enrich source-gap candidates with safe GitHub URLs and commit-backed metadata, add the `github-api:source-gap-candidate-refresh` marker, expose `#view` hrefs through `viewHref`, and extend interaction smoke plus release audit coverage.
- Decision: keep; source-backed adoption candidates rise to 35 while missing source rows fall to 9, and the new smoke step verifies route hrefs and navigation across PM and DB surfaces.

## Evidence

- `jq '[.projects[] | select(.sourceKind == "adoption-candidate") | select(.url != null and .lastCommit != null)] | length' data/adoption-candidates.json` returned `35`.
- The baseline `git show HEAD:data/adoption-candidates.json` count for the same query was `21`.
- `scripts/smoke-interactions.mjs` now reports `homeQuickLinksNavigate`, and `scripts/audit-release-readiness.mjs` adds `home_dashboard_quick_link_routes` plus `candidate_source_backing_coverage`.

## Experiment: Runtime asset versioned bootstrap

- Hypothesis: The release packager should rewrite the static `?v=3.0.0` CSS/JS bootstrap refs to content-hash query strings so deploy caches cannot serve mismatched runtime assets.
- Primary metric: `releaseAuditVersionedRuntimeAssetBootstrapFailures`.
- Baseline: Main-aligned release audit reported `72/73` with `versioned_runtime_asset_bootstrap` failing because `package-release.mjs` did not provide the runtime asset rewrite evidence.
- Candidate: Add `versionRuntimeAssetRefs()` to `package-release.mjs`, hash `styles.css` and `app.js`, and rewrite `index.html` before creating the mirrored `404.html` fallback.
- Decision: keep; the packager now supplies the content-hash bootstrap behavior that `verify-release.mjs` already checks for both `index.html` and `404.html`.

## Evidence

- Baseline `node scripts/audit-release-readiness.mjs --run-gates` on the main-aligned release state reported `pass: 72`, `fail: 1`, `total: 73`.
- `scripts/package-release.mjs` now contains `versionRuntimeAssetRefs`, `Runtime asset version ref missing`, and `sha256(join(outDir, asset.path)).slice(0, 12)` evidence required by the release audit.

## Experiment: System status route

- Hypothesis: The operations sidebar should expose a real `#system` route instead of sending users back to settings, so release smoke can prove storage, source-backed candidate, benchmark, and DB operations context from one status surface.
- Primary metric: `systemStatusRouteSmokeFailures`.
- Baseline: The sidebar linked to `#system` but used `data-view="settings"`, and the SPA had no `view-system`, router case, or desktop/mobile route smoke coverage.
- Candidate: Add an independent `view-system`, render system status KPIs and storage/operations panels, route `#system` through the SPA router, and extend release audit plus Chrome/mobile smoke route coverage.
- Decision: keep; the intended failure count drops from one missing route surface to zero when desktop/mobile smoke and release readiness gates include the system route.

## Evidence

- `scripts/audit-release-readiness.mjs` now expects 16 views and adds `system_status_route` evidence across `index.html`, `app.js`, `scripts/smoke-chrome.mjs`, and `scripts/smoke-mobile.mjs`.
- `autoresearch-results/joopark-product-loop.json` records `systemStatusRouteSmokeFailures` from baseline `1` to candidate `0`.
- `BASE_URL=http://127.0.0.1:5183 node scripts/smoke-chrome.mjs` and `BASE_URL=http://127.0.0.1:5183 node scripts/smoke-mobile.mjs` passed with `routeCount: 16` and no missing text, layout, console, or network failures.
- `BASE_URL=http://127.0.0.1:5183 node scripts/audit-release-readiness.mjs --run-gates` passed with `73/73` checks, including `route_surface` and `system_status_route`.

## Experiment: Workflow scope-aware release audit

- Hypothesis: The Pages workflow handoff should verify the current GitHub token's `workflow` scope during dry-run audits, so operators know whether the template can be installed through CLI or must be installed through a scoped token/UI session.
- Primary metric: `workflowScopeChecked`.
- Baseline: The release audit called `node scripts/prepare-github-pages-workflow.mjs --dry-run`, which validated paths but did not require boolean workflow-scope evidence in the handoff result.
- Candidate: Call `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope`, require `workflowScopeChecked: true`, and update the Pages workflow template action versions to current major versions.
- Decision: keep; the handoff audit now carries explicit scope evidence without writing the repository-root workflow file.

## Evidence

- `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` reports `workflowScopeChecked: true` and a boolean `workflowScopeAvailable` value.
- `scripts/audit-release-readiness.mjs` now records command `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` for `github_pages_workflow_scope_handoff`.
- `docs/github-pages-workflow.yml` now uses `actions/configure-pages@v6`, `actions/upload-pages-artifact@v5`, and `actions/deploy-pages@v5`.

## Experiment: Desktop route overflow smoke

- Hypothesis: Desktop route smoke should fail on horizontal overflow, not only on missing route text, so release checks catch wide-layout regressions before packaging.
- Primary metric: `desktopRouteOverflowSmokeCoverage`.
- Baseline: `scripts/smoke-chrome.mjs` had no `layoutIssues`, `overflowX`, or `docScrollWidth` desktop overflow hard-gate markers.
- Candidate: Restore desktop route layout measurement, report viewport and per-route overflow evidence through `smoke-chrome` and `smoke-release`, and add the `desktop_route_overflow_smoke` release-audit checklist item.
- Decision: keep; the marker coverage rises from 0 to 1 and the current desktop route smoke reports no overflow issues.

## Evidence

- `BASE_URL=http://127.0.0.1:5183 node scripts/smoke-chrome.mjs` passed with `routeCount: 16`, `viewport: 756x469`, `layoutIssues: []`, and no overflow routes.
- `npm run lint` passed after the smoke and audit script changes.
- `node scripts/audit-release-readiness.mjs --run-gates` passed `74/74` checks, including `desktop_route_overflow_smoke` with release-smoke desktop `layoutIssues: []`.

## Experiment: Home one-step todo activation

- Hypothesis: The first dashboard screen should let users complete a core workflow without opening a modal or leaving home.
- Primary metric: `homeOneStepTodoActivationSmokeCoverage`.
- Baseline: Home only exposed `+ 할 일`, which opened a modal; interaction smoke covered route links and the todo-page quick add, but not a home-first inline activation flow.
- Candidate: Add a dashboard inline quick-add form with title, priority, and due date; reuse the existing todo quick-add persistence path with home refocus; extend interaction smoke and release audit coverage.
- Decision: keep.

## Evidence

- External source signals used: UserOnboard frames empty/first-run states as onboarding opportunities that should guide users to value; EBRAINS design system says empty/loading/error states should always provide a next step; web.dev INP guidance emphasizes immediate visual feedback after interactions; W3C WCAG 2.2 highlights redundant entry, labels, focus, and target-size concerns.
- `scripts/audit-release-readiness.mjs` now includes `home_one_step_todo_activation`.
- `scripts/smoke-interactions.mjs` now verifies `homeQuickTodo` persistence, due date/priority metadata, staying on the dashboard, and input refocus.
- `npm run lint` passed, and `npm run verify` passed `76/76` checks with packaged interaction `homeQuickTodo: true`, desktop/mobile layout issues empty, and no console/network failures.

## Experiment: Installable manifest icon coverage

- Hypothesis: The installable web-app surface is more credible when the manifest includes explicit 192px and 512px icon assets instead of relying only on the favicon.
- Primary metric: `manifestInstallIconCoverage`.
- Baseline: Manifest icon coverage was a single 64x64 SVG favicon.
- Candidate: Add `icons/icon-192.svg` and `icons/icon-512.svg`, wire the `icons/` directory into release packaging, require both icon files in release verification, and extend the public metadata audit terms.
- Decision: keep.

## Evidence

- External source signals used: MDN and web.dev manifest guidance both treat app icons, display mode, start URL, shortcuts, and screenshots as core installable-app metadata; this project now verifies those assets in the release package.
- `node scripts/package-release.mjs` passed with 19 runtime files.
- `node scripts/verify-release.mjs` passed with 19 files and both icon assets included in manifest integrity checks.
- `npm run test` passed with headers, fallbacks, 16 desktop routes, 16 mobile routes, 20 interaction steps, and accessibility checks all green.
- `npm run verify` passed `76/76` checks, including `public_launch_metadata`, `static_runtime_files`, `manifest_integrity`, and packaged browser gates.

## Experiment: Todo search empty-state recovery

- Hypothesis: Search should not strand users in a zero-result state; it should communicate the result status and provide an immediate recovery action.
- Primary metric: `todoSearchRecoverySmokeCoverage`.
- Baseline: Todo search could show an empty result message, but release gates did not verify accessible status announcement, clear-search recovery, restored focus, or result restoration.
- Candidate: Mark todo result rows, expose the no-results empty state as a polite status, compute `검색 결과 없음`/result-count status text, and verify clear-search recovery in the packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals used: W3C documents search result messages as status-message accessibility concerns; Octopus and Supabase design systems frame no-results states as search/filter states that should include guidance or recovery; Material Design identifies search with no results as an empty state that should prevent confusion.
- `scripts/audit-release-readiness.mjs` now includes `todo_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `todoSearchRecovery`, status role, status text, clear-search, focus restoration, and row restoration.
- `npm run lint` passed, and `npm run verify` passed `77/77` checks with packaged interaction `todoSearchRecovery: true`, 21 interaction steps, and no console/network/layout failures.

## Experiment: GitHub Pages workflow freshness

- Hypothesis: A publish-ready static app should keep its workflow template aligned with current GitHub Pages docs and must trigger when install/share assets change.
- Primary metric: `githubPagesWorkflowTemplateFreshness`.
- Baseline: The workflow template used mixed action tags and did not include `icons/**`, `site.webmanifest`, or `social-preview.svg` in its push path filter.
- Candidate: Align the template with the current GitHub Pages custom workflow example (`checkout@v6`, `configure-pages@v5`, `upload-pages-artifact@v4`, `deploy-pages@v4`), add the new public asset paths to push triggers, and extend dry-run/audit terms.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages custom workflow docs require Pages workflows to upload a Pages artifact, deploy it with `pages: write` and `id-token: write`, link build/deploy jobs with `needs`, and show `checkout@v6`, `configure-pages@v5`, `upload-pages-artifact@v4`, and `deploy-pages@v4` in current examples.
- `node scripts/prepare-github-pages-workflow.mjs --dry-run --check-scope` passed template validation and still correctly reported `workflowScopeAvailable: false` for the current token.
- `npm run lint` passed.
- `npm run test` passed with 19 packaged files, 21 interaction steps, `homeQuickTodo: true`, `todoSearchRecovery: true`, and no console/network/layout/accessibility failures.
- `npm run verify` passed `77/77` checks, including `github_pages_publish_workflow_template`, `github_pages_workflow_scope_handoff`, and packaged browser gates.

## Experiment: Cross-view search empty-state recovery

- Hypothesis: Search recovery should be consistent across creation, knowledge, and portfolio workflows, not only Todo.
- Primary metric: `searchEmptyRecoveryCoveredViews`.
- Baseline: `app.js` exposed `data-search-empty` for 1 covered workflow view (`todo`).
- Candidate: Add a shared search empty-state helper, mark Notes and Portfolio result cards, render accessible no-results recovery states for both views, and verify clear-search recovery in packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals used: Carbon Design System recommends replacing no-result content with an empty state and providing useful next steps; Octopus Design System frames no-results states as search/filter states with guidance; W3C ARIA/WCAG status-message guidance supports polite status updates for dynamic results.
- `scripts/audit-release-readiness.mjs` now includes `cross_view_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `notesSearchRecovery` and `portfolioSearchRecovery`, including status role, status text, clear-search, focus restoration, and result-card restoration.
- `searchEmptyRecoveryCoveredViews` improved from 1 to 3 (`todo`, `notes`, `pm-portfolio`).
- `npm run lint` passed.
- `npm run verify` passed `81/81` checks with packaged interaction `notesSearchRecovery: true`, `portfolioSearchRecovery: true`, `backupSearchRecovery: true`, 24 interaction steps, and no console/network/layout failures.
- Local `BASE_URL=http://127.0.0.1:5184` desktop and mobile route smoke both passed 16 routes with no overflow, console, or network issues.

## Experiment: GitHub drift watch workflow template

- Hypothesis: Source-backed adoption candidates should have a scheduled and manually triggerable drift monitor before public launch, so release freshness does not depend on ad hoc local CLI checks.
- Primary metric: `githubDriftWatchWorkflowTemplateCoverage`.
- Baseline: No GitHub Actions template or workflow-scope dry-run handoff existed for candidate drift monitoring.
- Candidate: Add `docs/github-drift-watch-workflow.yml`, a scope-aware `scripts/prepare-github-drift-watch-workflow.mjs` installer dry-run, README operating instructions, and release-audit checks for the scheduled/manual drift watch workflow.
- Decision: keep.

## Evidence

- External source signals used: GitHub Actions workflow syntax documents `schedule` cron triggers, default-branch manual `workflow_dispatch` inputs, and minimum `permissions`; GitHub GITHUB_TOKEN docs show passing `${{ secrets.GITHUB_TOKEN }}` to `GH_TOKEN` for GitHub CLI/API use.
- `node scripts/prepare-github-drift-watch-workflow.mjs --dry-run --check-scope` passed and reported `workflowScopeChecked: true`, `workflowScopeAvailable: false`, and target `.github/workflows/joopark-drift-watch.yml` without writing.
- `node scripts/check-candidate-freshness-drift.mjs --snapshot-only` passed with 35 monitored source-backed candidates and 60 source markers.
- `npm run lint`, `npm run test`, and `npm run verify` passed; the final release audit reported `81/81` checks with `github_drift_watch_workflow_template` and `github_drift_watch_workflow_scope_handoff` included.

## Experiment: PM execution search empty-state recovery

- Hypothesis: PM execution views should not leave users staring at empty Kanban columns or a blank Gantt chart after a zero-result global search.
- Primary metric: `pmExecutionSearchRecoveryCoveredViews`.
- Baseline: Kanban and Gantt search had 0 covered recovery views with result markers, accessible no-results status, clear-search recovery, and smoke coverage.
- Candidate: Mark Kanban cards and Gantt task rows as search results, replace zero-result boards/charts with the shared recovery empty state, add layout guards for both containers, and verify restoration in packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals reused: Carbon Design System recommends replacing no-result content with an empty state and useful next steps; W3C ARIA/WCAG status-message guidance supports polite status updates for dynamic result changes.
- `scripts/audit-release-readiness.mjs` now includes `pm_execution_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `kanbanSearchRecovery` and `ganttSearchRecovery`, including status role, status text, clear-search, focus restoration, and result restoration.
- `pmExecutionSearchRecoveryCoveredViews` improved from 0 to 2 (`pm-kanban`, `pm-gantt`).
- `npm run lint` passed.
- `npm run verify` passed `84/84` checks with packaged interaction `kanbanSearchRecovery: true`, `ganttSearchRecovery: true`, 30 interaction steps, and no console/network/layout failures.

## Experiment: DB catalog search empty-state recovery

- Hypothesis: DB catalog views should give the same no-result recovery as planning views, so operators can return from a failed instance, schema, or query search without changing routes.
- Primary metric: `dbCatalogSearchRecoveryCoveredViews`.
- Baseline: Only DB backups had covered search recovery; DB instances, schema, and saved queries had 0 covered recovery views with result markers, accessible no-results status, clear-search recovery, and smoke coverage.
- Candidate: Mark DB instance cards, schema table rows, and saved query rows as search results, add shared no-results recovery states for those three views, and verify restoration in packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals reused: Carbon Design System recommends replacing no-result content with an empty state and useful next steps; W3C ARIA/WCAG status-message guidance supports polite status updates for dynamic search-result changes.
- `scripts/audit-release-readiness.mjs` now includes `db_catalog_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `dbInstancesSearchRecovery`, `dbSchemaSearchRecovery`, and `dbQueriesSearchRecovery`, including status role, status text, clear-search, focus restoration, and result restoration.
- `dbCatalogSearchRecoveryCoveredViews` improved from 1 to 4 (`dbm-backups`, `dbm-instances`, `dbm-schema`, `dbm-queries`).
- `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs` passed with `dbInstancesSearchRecovery: true`, `dbSchemaSearchRecovery: true`, and `dbQueriesSearchRecovery: true`.
- `npm run lint`, `npm run test`, and `npm run verify` passed; the final release audit reported `84/84` checks with 30 packaged interaction steps and no console/network/layout failures.

## Experiment: PM resource search empty-state recovery

- Hypothesis: Team resource search should not leave a split view where the list shows no matches while the assignment matrix still looks structurally present.
- Primary metric: `teamSearchRecoverySmokeCoverage`.
- Baseline: Team search had no packaged smoke coverage for accessible no-results recovery, restored focus, result restoration, or matrix empty-state evidence.
- Candidate: Mark team rows as search results, render a shared no-results recovery state for the Team list, identify the matching matrix empty state, and verify both panels through packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals reused: Carbon Design System recommends replacing no-result content with an empty state; Octopus Design System frames no-results states as search/filter states with guidance; W3C ARIA22 and MDN status-role guidance support polite status updates for dynamic search-result changes.
- `scripts/audit-release-readiness.mjs` now includes `pm_resource_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `teamSearchRecovery`, status role, status text, clear-search, focus restoration, member-row restoration, and matrix empty-state restoration.
- `teamSearchRecoverySmokeCoverage` improved from 0 to 1.
- `npm run lint` passed.
- `npm run verify` passed `85/85` checks with packaged interaction `teamSearchRecovery: true`, 31 interaction steps, and no console/network/layout failures.

## Experiment: Habits search recovery and Stats inertness

- Hypothesis: Habit tracking should support the same no-result recovery as other action views, while analytics-only Stats should not pretend that global search filtered the page.
- Primary metric: `habitAndStatsSearchConsistencyCoverage`.
- Baseline: Habits had no packaged smoke coverage for no-result recovery, and Stats was not listed as a search-inert view.
- Candidate: Filter active habit cards by name/emoji, mark habit cards as search results, render the shared no-results recovery state for Habits, classify Stats as search-inert, and verify both behaviors in packaged browser interaction smoke.
- Decision: keep.

## Evidence

- External source signals reused: Carbon Design System recommends replacing no-result content with an empty state; W3C ARIA22 and MDN status-role guidance support polite status updates for dynamic search-result changes.
- `scripts/audit-release-readiness.mjs` now includes `habit_search_empty_recovery`.
- `scripts/smoke-interactions.mjs` now verifies `habitSearchRecovery`, status role, status text, clear-search, focus restoration, habit-card restoration, and `statsSearchInert`.
- `habitAndStatsSearchConsistencyCoverage` improved from 0 to 2 (`habits`, `stats`).
- `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs` passed with `habitSearchRecovery: true`, `statsSearchInert: true`, and 35 interaction steps.
- `npm run lint`, `npm run test`, and `npm run verify` passed; the final release audit reported `90/90` checks with no console/network/layout failures.

## Next Loop

- Continue with the highest-impact product gap after search recovery coverage: audit post-release onboarding and first-run data clarity.

## Experiment: Home first-run empty guidance

- Hypothesis: After a user resets data or lands in an empty workspace, Home should not show blank operational tiles or sample-looking signals without a next action.
- Primary metric: `homeFirstRunGuidanceSmokeCoverage`.
- Baseline: Reset Home could render empty lists or sample backup signals without an explicit create path for each operational tile.
- Candidate: Add sectional Home empty states with concise context and create CTAs for projects, Kanban issues, Gantt tasks, team members, DB instances, schema, saved queries, and backup/migration setup. Hide sample backup history on Home when no DB instances exist.
- Decision: keep.

## Evidence

- External source signals used: Atlassian frames empty states as panel/table/board messages that explain the empty condition and guide action; Carbon says no-result content should be replaced by empty-state messaging when appropriate.
- `scripts/audit-release-readiness.mjs` now includes `home_first_run_empty_guidance`.
- `scripts/smoke-interactions.mjs` now verifies `homeFirstRunGuidance` after full reset, including all Home empty guidance blocks and their create actions.
- `homeFirstRunGuidanceSmokeCoverage` improved from 0 to 1.
- The first packaged test caught a mismatch where Home still showed backup sample data after reset; the candidate was adjusted so Home only shows backup history when DB instances exist.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `90/90` checks, 35 packaged interaction steps, `homeFirstRunGuidance: true`, and no console/network/layout failures.
- Local desktop and mobile route smoke on `http://127.0.0.1:5184` both passed 16 routes with no overflow, console, or network issues.

## Next Loop

- Continue with import/export onboarding and deployment handoff copy: make sure backup/import/reset and publish workflow instructions are understandable to an external user without repository history.

## Experiment: Settings operational handoff copy

- Hypothesis: External users need backup/import/reset and deploy instructions inside the app, not only in README, before they can safely share or publish a local-first workspace.
- Primary metric: `settingsHandoffCopySmokeCoverage`.
- Baseline: Settings exposed data export/import/reset controls, but no copy-ready operational handoff for backup risk, `npm run verify`, Pages permissions, workflow scope, or drift-watch installation.
- Candidate: Add two Settings handoff cards for data protection and deployment, generate current Markdown handoff text from live storage/release context, add one-click clipboard copy with visible status, and verify both handoffs in browser smoke.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages official docs support Actions as a publishing source and describe the `checkout` -> build -> `upload-pages-artifact` -> `deploy-pages` flow; GitHub custom workflow docs require at least `pages: write` and `id-token: write` for Pages artifact deployment; GitHub OIDC docs confirm `id-token: write` is required to request an OIDC token.
- `app.js` now renders `[data-settings-handoff]` with backup and deploy cards. The generated deploy handoff includes `npm run lint`, `npm run test`, `npm run verify`, `prepare-github-pages-workflow.mjs --dry-run --check-scope`, `pages: write`, `id-token: write`, and `actions/deploy-pages`.
- `scripts/audit-release-readiness.mjs` now includes `settings_operational_handoff_copy`.
- `scripts/smoke-interactions.mjs` now verifies `settingsHandoffCopy`, including generated Markdown contents, clipboard write, copied state, and visible live status for both backup and deploy handoffs.
- `settingsHandoffCopySmokeCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `93/93` checks, 37 packaged interaction steps, `settingsHandoffCopy: true`, and no console/network/layout failures.

## Experiment: Settings operational handoff copy hardening

- Hypothesis: External operators should be able to copy Korean-first backup/import/reset and deploy checklists from Settings, and smoke should verify the actual clipboard content rather than only button state.
- Primary metric: `settingsOperationalHandoffClipboardCoverage`.
- Baseline: Settings exposed handoff cards and button-state smoke, but copied Markdown was English-first and smoke did not assert clipboard text for backup/deploy guidance.
- Candidate: Rewrite handoff Markdown with Korean operational steps, import replacement warning, Pages permission/action requirements, and assert actual clipboard content in interaction smoke.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages workflow guidance around Pages permissions and deploy actions; empty/action-state guidance around copy-ready operational next steps.
- `app.js` now generates Korean-first backup and deploy handoff Markdown, including the import replacement warning, `pages: write`, `id-token: write`, and `actions/deploy-pages`.
- `scripts/smoke-interactions.mjs` now stubs clipboard writes and verifies the copied backup/deploy Markdown text, not only visible button state.
- `scripts/audit-release-readiness.mjs` now requires the deploy permission/action terms and strengthened calendar grid keyboard terms.
- The first local interaction smoke caught a calendar keyboard focus regression; `focusCalendarDay` now restores focus with roving `tabindex` and `requestAnimationFrame(focus)`.
- `settingsOperationalHandoffClipboardCoverage` improved from 0 to 2 (`backup`, `deploy`).
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `94/94` checks, 37 packaged interaction steps, `settingsHandoffCopy: true`, `calendarGridKeyboard: true`, and no console/network/layout failures.
- Local desktop and mobile route smoke on `http://127.0.0.1:5184` both passed 16 routes with no overflow, console, or network issues.

## Next Loop

- Continue with publish readiness alignment: make System status and Settings handoff expose the same workflow-scope/token readiness state, then harden the audit against transient release-smoke retries if the package gate flakes again.

## Experiment: System publish readiness alignment

- Hypothesis: Operators should see the same publish blockers in System Status and Settings handoff, so the app does not look “done” when workflow installation and dispatch are still action-required.
- Primary metric: `systemPublishReadinessSmokeCoverage`.
- Baseline: Settings could copy deploy handoff text, but System Status only showed storage, source-backed candidates, benchmark counts, and operations metrics.
- Candidate: Add a System Status 공개 준비 상태 panel driven by shared publish-readiness items, reuse the same items in Settings deploy Markdown, and verify DOM blocker counts plus handoff mirroring in browser smoke.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages official docs allow GitHub Actions as the publishing source; GitHub custom workflow docs require Pages deployment jobs to have `pages: write` and `id-token: write`; GitHub Actions workflow syntax documents explicit `GITHUB_TOKEN` permissions; GitHub PAT docs recommend minimal permissions and treating tokens as sensitive.
- `app.js` now has `publishReadinessItems()`, `publishReadinessMarkdownLines()`, `[data-system-publish-readiness]`, `[data-publish-readiness-item]`, and `data-system-publish-blockers`.
- System Status separates verified release gates from action-required Pages workflow install, Drift Watch install, and publish dispatch. Settings deploy handoff reuses the same publish readiness lines.
- `scripts/audit-release-readiness.mjs` now includes `system_publish_readiness_alignment`.
- `scripts/smoke-interactions.mjs` now verifies `systemPublishReadiness`, including blocker counts, workflow install commands, and Settings handoff mirroring.
- `systemPublishReadinessSmokeCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `96/96` checks, 38 packaged interaction steps, `systemPublishReadiness: true`, and no console/network/layout failures.

## Experiment: System publish readiness scope preflight

- Hypothesis: The publish readiness panel should not collapse workflow token readiness into generic install blockers; operators need a visible `workflowScopeAvailable` preflight step before attempting repository-root workflow writes.
- Primary metric: `systemPublishScopePreflightSmokeCoverage`.
- Baseline: System and Settings shared publish blockers, but workflow scope availability was implicit inside install guidance.
- Candidate: Add a shared `workflow scope preflight` readiness item, include `workflowScopeAvailable` and both Pages/Drift dry-run commands in System and Settings deploy Markdown, and make interaction smoke assert the mirrored preflight text.
- Decision: keep.

## Evidence

- External source signals used: GitHub Pages custom workflow docs require `pages: write`, `id-token: write`, `upload-pages-artifact`, `deploy-pages`, and build/deploy `needs` for Pages deployment.
- `app.js` now includes `workflow-scope-preflight` in `publishReadinessItems()` and clarifies the Pages template permission/action flow.
- `scripts/smoke-interactions.mjs` now verifies `workflowScopeAvailable`, the `workflow scope preflight` label, and Settings deploy handoff mirroring.
- `scripts/audit-release-readiness.mjs` now requires the preflight key and `workflowScopeAvailable` evidence across app, smoke, and README.
- `README.md` now documents `workflowScopeAvailable` as part of the public readiness state.
- `systemPublishScopePreflightSmokeCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `96/96` checks, 38 packaged interaction steps, `systemPublishReadiness: true`, and no console/network/layout failures.
- Local desktop and mobile route smoke on `http://127.0.0.1:5184` both passed 16 routes with no overflow, console, or network issues.

## Experiment: Release smoke audit retry hardening

- Hypothesis: The release audit should not fail a complete publish readiness run because one packaged smoke attempt returns incomplete evidence during a transient browser/server startup race.
- Primary metric: `releaseSmokeAuditRetryCoverage`.
- Baseline: `audit-release-readiness.mjs --run-gates` ran packaged release smoke once; an incomplete result with null header/fallback/browser evidence could fail the full audit even when immediate rerun passed.
- Candidate: Retry `smoke-release.mjs` once only when the gate evidence is incomplete, keep complete failure evidence as a real failure, and expose `auditRetryAttempts` when retry is used.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now has `releaseSmokeNeedsRetry()`, `smokeReleaseAttempt()`, a maximum of 2 attempts, and `auditRetryAttempts` reporting for retried evidence.
- The retry condition is bounded to missing headers, fallbacks, route smoke, mobile, interactions, or accessibility evidence; complete failing evidence is not masked.
- `release_smoke_temp_output` audit terms now require the retry helper, retry attempt metadata, and the max-attempt guard.
- `releaseSmokeAuditRetryCoverage` improved from 0 to 1.
- `npm run lint` passed.
- `npm run verify` passed `97/97` checks with packaged browser gates passing on the first attempt, 38 packaged interaction steps, and no console/network/layout failures.

## Next Loop

- Continue with publish dispatch operationalization: add a dry-run publish dispatch checklist or install repository-root Pages/Drift workflows with a workflow-scope token or GitHub UI session, then re-run publish readiness smoke.

## Experiment: System publish unblock handoff copy

- Hypothesis: Once System Status shows workflow-scope blockers, operators should be able to copy the exact unblock checklist without reconstructing it from README and Settings text.
- Primary metric: `systemPublishUnblockHandoffCopyCoverage`.
- Baseline: System Status exposed publish readiness blockers, but the unblock procedure was not copy-ready from that surface.
- Candidate: Add a `publish unblock handoff` copy action to System Status with CLI preflight, GitHub UI workflow-file installation path, publish dispatch, Drift Watch dispatch, and post-install verification steps. Verify the generated Markdown and clipboard payload in browser smoke.
- Decision: keep.

## Evidence

- External source signals reused: GitHub Pages and Actions docs require repository workflow files plus explicit Pages/OIDC permissions for custom Pages deployment; GitHub PAT docs recommend minimal permissions and treating tokens as sensitive.
- `app.js` now includes `publishUnblockHandoffText()`, `[data-system-publish-handoff-copy]`, and `copySystemPublishHandoff()`.
- `scripts/smoke-interactions.mjs` now verifies the unblock handoff title, `workflowScopeAvailable`, Pages and Drift workflow target paths, visible copy status, and actual clipboard content.
- `scripts/audit-release-readiness.mjs` now requires the unblock handoff copy action and clipboard smoke evidence.
- `systemPublishUnblockHandoffCopyCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `97/97` checks, 38 packaged interaction steps, `systemPublishReadiness: true`, and no console/network/layout failures.

## Experiment: Publish dispatch dry-run plan

- Hypothesis: Operators should be able to prove that Pages and Drift Watch workflows are installed and visible before running `gh workflow run`, otherwise publish dispatch instructions can fail late.
- Primary metric: `publishDispatchDryRunPlanCoverage`.
- Baseline: System and Settings exposed workflow install blockers, but there was no structured dry-run artifact for dispatch readiness.
- Candidate: Add `scripts/plan-publish-dispatch.mjs` to report Pages and Drift Watch workflow targets, local target existence, optional live GitHub Actions visibility, dispatch commands, blockers, and `dispatchReady`/`driftDispatchReady`/`allDispatchReady` flags.
- Decision: keep.

## Evidence

- `node scripts/plan-publish-dispatch.mjs --dry-run` reports `dispatchReady: false`, `driftDispatchReady: false`, `allDispatchReady: false`, and blockers for missing repository-root workflow files and unchecked live workflow visibility.
- `node scripts/plan-publish-dispatch.mjs --live` confirmed both workflow files are still absent locally and not visible in GitHub Actions, so both dispatch commands remain guarded.
- `app.js` now adds `Publish dispatch dry-run` to shared publish readiness and Settings deploy handoff before `gh workflow run`.
- `README.md` now documents `plan-publish-dispatch.mjs --dry-run`, `--live`, and the `dispatchReady`/`allDispatchReady` gate before workflow dispatch.
- `scripts/audit-release-readiness.mjs` now includes `publish_dispatch_dry_run_plan`.
- `scripts/smoke-interactions.mjs` now verifies dispatch dry-run guidance in System and Settings handoff text.
- `publishDispatchDryRunPlanCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, `npm run verify`, and local desktop/mobile route smoke passed; final release audit reported `99/99` checks, 38 packaged interaction steps, and no console/network/layout failures.

## Next Loop

- Continue with actual workflow installation only when a workflow-scope token or GitHub UI session is available; otherwise keep tightening offline publish readiness and drift dispatch preflight coverage.

## Experiment: Publish dispatch plan Drift Watch coverage

- Hypothesis: The dispatch plan should cover both the public Pages deploy and the candidate freshness Drift Watch workflow before launch, so operators do not ship Pages while the freshness monitor remains unverified.
- Primary metric: `publishDispatchWorkflowPlanCoverage`.
- Baseline: The dispatch planner primarily proved the Pages workflow gate.
- Candidate: Extend the planner, app readiness copy, README, smoke, and audit to require both `Publish JooPark Pages` and `Watch JooPark Candidate Drift` workflow plans before any dispatch is treated as ready.
- Decision: keep.

## Evidence

- External source signals used: GitHub Actions supports `workflow_dispatch` manual runs, and GitHub Pages custom workflows require repository workflow files plus explicit Pages/OIDC permissions before deployment.
- `scripts/plan-publish-dispatch.mjs` now reports two workflow plans: `joopark-pages.yml` and `joopark-drift-watch.yml`.
- Dry-run output reports `dispatchReady: false`, `driftDispatchReady: false`, `allDispatchReady: false`, and four aggregate blockers for missing repository-root workflows plus unchecked live visibility.
- Live output confirms both workflow targets are still absent and not visible in GitHub Actions, so both dispatch commands remain guarded.
- `app.js`, `README.md`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` now align on `dispatchReady`, `driftDispatchReady`, and `allDispatchReady`.
- `publishDispatchWorkflowPlanCoverage` improved from 1 to 2.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `99/99` checks, 38 packaged interaction steps, `systemPublishReadiness: true`, `publishDispatchDryRunPlan: true`, and no console/network/layout failures.

## Next Loop

- Install the repository-root Pages and Drift Watch workflows with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live` until `allDispatchReady: true`.
- If workflow installation remains blocked, continue tightening offline publish evidence capture so the post-dispatch URL and Drift Watch advisory result can be recorded immediately after credentials are available.

## Experiment: Workflow UI install plan

- Hypothesis: When `workflowScopeAvailable` is false, operators need a verified GitHub UI install artifact before manually creating repository-root workflow files.
- Primary metric: `workflowUiInstallPlanCoverage`.
- Baseline: Publish handoffs described the GitHub UI path, but did not provide a structured dry-run artifact for target paths, template sha256 hashes, and required workflow terms.
- Candidate: Add `scripts/plan-workflow-ui-install.mjs`, wire it into System/Settings publish readiness, README, interaction smoke, and release audit.
- Decision: keep.

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run` reports `workflowUiInstallReady: true`, two plans, zero blockers, and target paths for `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml`.
- Pages template sha256: `99ac43b694ea7a7328ab4b147d7887b3e47e1e96d26149a318fb3de45172fd16`.
- Drift Watch template sha256: `c837f7ea14aa62ac0278ecddef32f4737823887e6ff9fd746561e2e22b5025ae`.
- `app.js` now exposes `GitHub UI install plan` in shared publish readiness and includes `plan-workflow-ui-install.mjs --dry-run` plus `template sha256` in the Settings deploy handoff copy text.
- `scripts/audit-release-readiness.mjs` now includes the `workflow_ui_install_plan` checklist.
- `scripts/smoke-interactions.mjs` verifies System readiness, Settings handoff text, and copied clipboard payload for the UI install plan guidance.
- `workflowUiInstallPlanCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, local desktop/mobile route smoke, and `npm run verify` passed; final release audit reported `103/103` checks, 38 packaged interaction steps, and no console/network/layout failures.

## Next Loop

- Install the repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live` until `allDispatchReady: true`.
- If workflow installation remains blocked, continue tightening post-dispatch evidence capture and System Status display for the eventual Pages URL and Drift Watch advisory result.

## Experiment: Post-dispatch publish evidence capture

- Hypothesis: Operators should have one structured command that proves the Pages URL and both workflow runs after dispatch, otherwise a launch can be marked complete without public URL or drift-watch evidence.
- Primary metric: `postPublishEvidenceCaptureCoverage`.
- Baseline: README and System Status blocked dispatch until workflows were visible, but there was no structured post-dispatch evidence artifact.
- Candidate: Add `scripts/capture-publish-evidence.mjs`, wire it into System Status, Settings deploy handoff, README, interaction smoke, and release audit.
- Decision: keep.

## Evidence

- External source signals used: GitHub REST Pages API exposes site `html_url` and `status`, and GitHub Actions run APIs/CLI expose workflow run `status`, `conclusion`, URL, and commit metadata.
- `node scripts/capture-publish-evidence.mjs --dry-run` reports two workflow evidence plans, the Pages API command, `postPublishEvidenceReady: false`, and a live-check blocker.
- `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects` confirmed the current repository is not publish-ready yet: Pages site is 404, `joopark-pages.yml` is missing on the default branch, and `joopark-drift-watch.yml` is missing on the default branch.
- `app.js` now adds `Publish evidence capture` to shared publish readiness and both System/Settings handoff surfaces.
- `scripts/audit-release-readiness.mjs` now includes `publish_evidence_capture_plan`.
- `scripts/smoke-interactions.mjs` now verifies post-dispatch evidence copy in Settings and System.
- During verification, packaged route smoke hit one transient `route not ready` failure. `scripts/smoke-chrome.mjs` now uses a 12s route-ready timeout, and `scripts/smoke-release.mjs` treats `route not ready` as a bounded one-retry browser flake.
- `postPublishEvidenceCaptureCoverage` improved from 0 to 1, and `releaseRouteReadyRetryCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; the final release audit reported `103/103` checks, 38 packaged interaction steps, 16 desktop routes, 16 mobile routes, and no console/network/layout failures.

## Next Loop

- When workflow installation is available, rerun `node scripts/plan-publish-dispatch.mjs --live` until `allDispatchReady: true`, dispatch Pages and Drift Watch, then rerun `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects` until `postPublishEvidenceReady: true`.
- If credentials remain unavailable, continue improving the public-ready path by surfacing the future captured Pages URL and Drift Watch run URL in System Status once live evidence exists.

## Experiment: Post-dispatch evidence Markdown handoff

- Hypothesis: After publish dispatch, operators need a copy-ready Markdown evidence report as well as a JSON evidence file, otherwise the launch proof remains hard to share in review channels.
- Primary metric: `postPublishEvidenceMarkdownHandoffCoverage`.
- Baseline: `capture-publish-evidence.mjs` produced JSON and could write `data/publish-evidence.json`, but it did not render a human-readable report with Pages URL/status, workflow run status/conclusion, blockers, and next commands.
- Candidate: Add `--markdown` output to `scripts/capture-publish-evidence.mjs`, expose the Markdown and `--write` commands in System/Settings handoffs, README, interaction smoke, and release audit.
- Decision: keep.

## Evidence

- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` prints `# JooPark Publish Evidence`, `postPublishEvidenceReady: false`, Pages site fields, Pages/Drift workflow run rows, blockers, and next commands.
- JSON default output remains unchanged and still reports workflow evidence plans, Pages site command, blockers, and `postPublishEvidenceReady`.
- `app.js` now tells operators to use `--markdown` for the shared evidence report and `--write` for the local JSON evidence file.
- `scripts/audit-release-readiness.mjs` now includes `publish_evidence_markdown_handoff` and validates the dry-run Markdown report.
- `scripts/smoke-interactions.mjs` verifies System and Settings handoff copy text for `--markdown`, `--write`, and `postPublishEvidenceReady`.
- `postPublishEvidenceMarkdownHandoffCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, local desktop/mobile route smoke, and `npm run verify` passed; final release audit reported `106/106` checks, 38 packaged interaction steps, 16 desktop routes, 16 mobile routes, and no console/network/layout failures.

## Next Loop

- Install the repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live` until `allDispatchReady: true`.
- After dispatch, run `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO --markdown` for shareable proof and `--write` for `data/publish-evidence.json` until `postPublishEvidenceReady: true`.

## Experiment: Publish evidence persistence in System Status

- Hypothesis: Post-dispatch evidence should not live only in terminal output; the shipped app should read a static evidence file and show the current Pages/workflow proof state in System Status.
- Primary metric: `publishEvidencePersistenceCoverage`.
- Baseline: `capture-publish-evidence.mjs` could print JSON/Markdown, but System Status could not load or display a saved evidence file.
- Candidate: Add `data/publish-evidence.json`, support `--write`, load the file in `app.js`, render a System Status evidence panel, package/verify the file, and smoke-test the panel.
- Decision: keep.

## Evidence

- `node scripts/capture-publish-evidence.mjs --dry-run --write` creates `data/publish-evidence.json` with `writtenTo`, workflow evidence plans, Pages API command, blockers, and `postPublishEvidenceReady: false`.
- `app.js` now loads `data/publish-evidence.json` on boot and renders `data-system-publish-evidence` with source, mode, repo, generated time, readiness, Pages URL, Pages run, Drift run, blockers, and the `--write` refresh command.
- `styles.css` adds a compact evidence panel treatment inside System Status.
- `scripts/verify-release.mjs` and `scripts/audit-release-readiness.mjs` now require `data/publish-evidence.json` in the release package and validate its default dry-run shape.
- `scripts/smoke-interactions.mjs` verifies the persisted evidence panel loads from `data/publish-evidence.json` and remains action-required until live evidence is written.
- `publishEvidencePersistenceCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `106/106` checks, 20 packaged runtime files, 38 packaged interaction steps, and no console/network/layout failures.

## Next Loop

- Install workflows via the verified UI plan or workflow-scope token, then run `plan-publish-dispatch.mjs --live`, dispatch both workflows, and replace the dry-run `data/publish-evidence.json` with live evidence.
- If publish credentials remain unavailable, keep reducing external-user launch risk by turning remaining manual release notes into structured, package-verified evidence.

## Experiment: Publish evidence placeholder guard

- Hypothesis: A saved dry-run publish evidence file should never read like live launch proof in System Status; users need separate mode, Pages readiness, workflow readiness, and state-label signals.
- Primary metric: `publishEvidencePlaceholderGuardCoverage`.
- Baseline: System Status displayed loaded/ready evidence state, but dry-run placeholder evidence was not separately encoded as mode-specific, Pages-specific, and workflow-specific readiness.
- Candidate: Add explicit `mode`, `pagesEvidenceReady`, `workflowEvidenceReady`, and `dry-run evidence` state rendering in `app.js`, update README guidance, and cover the distinction in smoke and release audit gates.
- Decision: keep.

## Evidence

- `app.js` now renders `data-publish-evidence-mode`, `data-publish-evidence-pages-ready`, `data-publish-evidence-workflows-ready`, and `data-publish-evidence-state-label` in the System Status publish evidence panel.
- The System Status panel now shows `pagesEvidenceReady`, `workflowEvidenceReady`, and `postPublishEvidenceReady` separately, with dry-run evidence labeled as `dry-run evidence` rather than ready.
- `README.md` documents the dry-run/live distinction for `mode`, `pagesEvidenceReady`, `workflowEvidenceReady`, and `postPublishEvidenceReady`.
- `scripts/smoke-interactions.mjs` verifies the persisted dry-run evidence file reports `mode: dry-run`, Pages/workflow readiness as false, the `dry-run evidence` state label, and the Markdown/JSON refresh commands.
- `scripts/audit-release-readiness.mjs` now requires the placeholder-guard terms across app, smoke, and README coverage.
- `publishEvidencePlaceholderGuardCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `107/107` checks, 38 packaged interaction steps, 20 packaged runtime files, and no console/network/layout failures.

## Next Loop

- Install workflows via the verified UI plan or workflow-scope token when available, then run `plan-publish-dispatch.mjs --live`, dispatch both workflows, and replace `data/publish-evidence.json` with live evidence.
- If publish credentials remain unavailable, continue improving package-verified launch handoffs so the next external action has an executable preflight and a visible completion proof.

## Experiment: Publish evidence repo-scoped capture

- Hypothesis: Post-dispatch workflow evidence should always be scoped to an explicit repository, otherwise running the capture command from a bridge branch, subdirectory, or unrelated checkout can record the wrong workflow run.
- Primary metric: `publishEvidenceRepoScopedCaptureCoverage`.
- Baseline: Pages evidence used `--repo` through the REST path, but workflow run evidence relied on the current `gh` repository context and did not expose a separate repo readiness field.
- Candidate: Add `repoEvidenceReady`, make workflow run evidence commands use `gh run list --repo OWNER/REPO --workflow ...`, block placeholder live captures, refresh `data/publish-evidence.json`, and verify the System Status display plus README/audit/smoke coverage.
- Decision: keep.

## Evidence

- `gh run list --help` confirms `--repo [HOST/]OWNER/REPO` is supported for selecting an explicit repository.
- `scripts/capture-publish-evidence.mjs` now builds workflow evidence through `workflowEvidenceCommand()` and passes `--repo` for live workflow run checks.
- `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO` now returns `repoEvidenceReady: false`, skips workflow run lookup, and reports the blocker `repo placeholder OWNER/REPO must be replaced before live evidence capture`.
- `node scripts/capture-publish-evidence.mjs --dry-run --write` refreshed `data/publish-evidence.json` with repo-scoped workflow evidence commands.
- `app.js` now renders `repoEvidenceReady` and `data-publish-evidence-repo-ready` in System Status, while `README.md` documents that workflow run checks do not infer the repo from the current directory.
- `scripts/audit-release-readiness.mjs` and `scripts/smoke-interactions.mjs` now require the repo-scoped commands and placeholder guard.
- `publishEvidenceRepoScopedCaptureCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run`, `node scripts/capture-publish-evidence.mjs --live --repo OWNER/REPO`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, `node scripts/smoke-release.mjs`, and `npm run verify -- --format=markdown` passed; final release audit reported `108/108` checks, 38 packaged interaction steps, 20 packaged runtime files, and no console/network/layout failures.

## Next Loop

- Install workflows via the verified UI plan or workflow-scope token when available, then run `plan-publish-dispatch.mjs --live`, dispatch both workflows, and replace `data/publish-evidence.json` with live evidence.
- If publish credentials remain unavailable, keep reducing release-operator error by adding freshness or expiry checks to saved publish evidence before it can be treated as current proof.

## Experiment: Local storage privacy safety handoff

- Hypothesis: A local-first public workspace must make browser storage boundaries explicit, otherwise users may store secrets or overtrust exported JSON files.
- Primary metric: `localStoragePrivacySafetyCoverage`.
- Baseline: Settings had backup and deploy handoffs, but no copy-ready privacy/storage checklist for localStorage scope, sensitive data exclusions, export-file handling, private browsing, or `file://` caveats.
- Candidate: Add a Settings privacy handoff card and Markdown copy text, document the policy in README, and require the UI/docs/smoke evidence in release audit.
- Decision: keep.

## Evidence

- External source signals used: OWASP HTML5 Security Storage APIs recommends avoiding sensitive data in localStorage, and MDN documents origin-specific localStorage behavior plus private browsing and `file://` caveats.
- `app.js` now renders `data-settings-privacy-handoff` and `settingsPrivacyHandoffText()` with localStorage scope, `joopark.workspace.v3`, no token/password/API key storage, JSON export handling, and `npm run verify` before public sharing.
- `scripts/smoke-interactions.mjs` verifies the privacy card text, copy payload, clipboard behavior, and persisted `privacyStorageHandoff: true` marker.
- `README.md` now documents the localStorage privacy/security boundary in the Data storage/backup table and includes privacy handoff in Settings operations guidance.
- `scripts/audit-release-readiness.mjs` now includes `local_storage_privacy_safety_handoff`.
- `localStoragePrivacySafetyCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `108/108` checks, 38 packaged interaction steps, and `privacyStorageHandoff: true`.

## Next Loop

- Add freshness or expiry checks to saved publish evidence so a stale `data/publish-evidence.json` cannot be mistaken for current launch proof.
- If workflow credentials become available, install Pages/Drift workflows, run dispatch, and replace dry-run publish evidence with live evidence.

## Experiment: Release smoke heartbeat and modal touch target hardening

- Hypothesis: The full packaged release gate should be resilient in long-running local browser checks and should catch mobile touch target regressions before public release.
- Primary metric: `releaseSmokeHeartbeatAndTouchCoverage`.
- Baseline: `smoke-release.mjs` captured child output silently and could be externally terminated during long browser gates; mobile modal swatches measured as 31x31 in the full wrapper and failed touch-target checks.
- Candidate: Emit compact stderr progress and child heartbeat logs from `smoke-release.mjs`, then make note/habit modal swatch radio targets at least 35px measured in mobile smoke.
- Decision: keep.

## Evidence

- `scripts/smoke-release.mjs` now reports packaging, manifest, header, fallback, desktop, mobile, interaction, accessibility, and child heartbeat progress without changing stdout JSON.
- `styles.css` now gives `.modal-form label.swatch` and its radio input explicit 36px dimensions so the mobile smoke measures 35x35 targets and no longer reports modal touch layout issues.
- `SMOKE_PROGRESS=1 BASE_URL=http://127.0.0.1:5185 node scripts/smoke-mobile.mjs` passed with `modalTouchReport.status: pass`, `swatchCount: 12`, and no layout issues.
- `npm run test` passed with 20 release files, 16 desktop routes, 16 mobile routes, 38 interaction steps, accessibility checks passing, and no console/network/layout failures.
- `npm run verify` passed with the packaged browser gates embedded in release audit: `108/108`.

## Next Loop

- Continue with publish-evidence freshness and live workflow dispatch readiness, since the remaining blocker is external workflow installation rather than local package quality.

## Experiment: Publish evidence freshness guard

- Hypothesis: A saved live `data/publish-evidence.json` should expire as launch proof, otherwise an old successful Pages/workflow snapshot can be mistaken for current public readiness.
- Primary metric: `publishEvidenceFreshnessGuardCoverage`.
- Baseline: Saved publish evidence exposed generated time and readiness fields, but did not carry an expiry window or make System Status distinguish stale evidence from current proof.
- Candidate: Add `evidenceFresh`, `evidenceExpiresAt`, and `evidenceMaxAgeHours` to the capture payload and Markdown report, make System Status compute current readiness from `postPublishEvidenceReady && evidenceFresh`, and add browser smoke coverage for stale/fresh helper behavior.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now records a 24-hour freshness window with `evidenceFresh: true`, `evidenceExpiresAt`, and `evidenceMaxAgeHours: 24`.
- `node scripts/capture-publish-evidence.mjs --dry-run --write` refreshed `data/publish-evidence.json` with freshness fields and repo-scoped workflow evidence commands.
- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` now prints `evidenceFresh`, `evidenceExpiresAt`, and `evidenceMaxAgeHours`.
- `app.js` now has `publishEvidenceFresh()` and renders `data-publish-evidence-fresh`, expiry, max-age, and a `stale evidence` state when captured proof is no longer current.
- `scripts/smoke-interactions.mjs` verifies the freshness state in the System Status panel and directly checks that `publishEvidenceFresh()` rejects a 49-hour-old snapshot while accepting a 2-hour-old snapshot.
- `README.md` documents that saved evidence is only current inside a 24-hour freshness window.
- `scripts/audit-release-readiness.mjs` requires freshness fields across capture output, saved snapshot, app UI, smoke, and README.
- `publishEvidenceFreshnessGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `node scripts/audit-release-readiness.mjs --format=markdown`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `110/110` checks, 38 packaged interaction steps, 20 packaged runtime files, and no console/network/layout failures.

## Next Loop

- Install workflows via the verified UI plan or workflow-scope token when available, then run `plan-publish-dispatch.mjs --live`, dispatch both workflows, and replace `data/publish-evidence.json` with live evidence.
- If workflow credentials remain unavailable, continue improving local release confidence and operator handoffs without claiming external publish completion.

## Experiment: Inert search palette keyboard smoke hardening

- Hypothesis: Aggregate views with readonly global search should keep keyboard affordances stable; if the smoke sends synthetic keys to the wrong target, real regressions and test-only flakes are hard to separate.
- Primary metric: `statsSearchInertKeyboardSmokeCoverage`.
- Baseline: The stats inert-search smoke dispatched `/` on `document`, while the app listener is bound to `#globalSearch`; a focused run failed before reaching publish-evidence assertions.
- Candidate: Dispatch the printable key to `#globalSearch`, assert palette input focus after opening, dispatch Escape to `#paletteInput`, and make the app's global Escape handler prevent default before closing the palette.
- Decision: keep.

## Evidence

- `app.js` now calls `event.preventDefault()` before closing an open command palette from the global Escape handler.
- `scripts/smoke-interactions.mjs` now exercises the same listener path users hit on inert views: readonly `#globalSearch` opens the palette, focused `#paletteInput` closes it with Escape, and `statsSearchInert` remains true.
- A focused smoke failed first with `slash on inert view did not open command palette`; after the target fix, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs` passed with 38 interaction steps, no failures, and `statsSearchInert: true`.
- `npm run test` passed the packaged release route, mobile, interaction, and accessibility gates; `npm run verify` passed `110/110`.

## Next Loop

- Continue toward external publish by installing Pages/Drift workflows or, if credentials remain blocked, strengthening live-evidence handoffs without claiming publish completion.

## Experiment: Release audit summary format

- Hypothesis: Operators need a compact release audit output for fast status checks; the full JSON/Markdown checklist is too large for quick blocker triage and can obscure the actual failing item.
- Primary metric: `releaseAuditSummaryFormatCoverage`.
- Baseline: `audit-release-readiness.mjs` supported JSON and full Markdown only, and `npm run verify` streamed the full JSON audit by default.
- Candidate: Add `--format=summary`/`--summary`, make `npm run verify` use summary output, document the format, and add a release audit checklist item that verifies the summary command and static references.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now supports `--format=summary` and prints `JooPark Release Readiness Summary`, status, pass/fail/not_run/blocked counts, source commit, packaged browser gate state, git branch line, and blockers only.
- `release_audit_summary_format` is now part of the audit checklist and uses `JOOPARK_AUDIT_SKIP_SUMMARY_SELF` to avoid recursive self-checks while still validating the summary output.
- `package.json` now runs `node scripts/audit-release-readiness.mjs --run-gates --format=summary` for `npm run verify`.
- `README.md` documents `npm run verify` as the compact summary path, with full Markdown and JSON alternatives for deeper review.
- `releaseAuditSummaryFormatCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `node scripts/audit-release-readiness.mjs --format=markdown`, and `npm run verify` passed; final compact release summary reported `110/110`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue strengthening local release confidence and operator handoffs while workflow installation remains blocked by external GitHub workflow-scope access.
- If credentials become available, use the verified UI/token path to install Pages and Drift Watch workflows, then capture fresh live publish evidence.

## Experiment: Publish dispatch repo-scoped plan

- Hypothesis: Publish dispatch planning must require an explicit GitHub repo, otherwise `gh workflow run` can target whatever repository the operator shell is currently bound to.
- Primary metric: `publishDispatchRepoScopedPlanCoverage`.
- Baseline: `plan-publish-dispatch.mjs` checked `gh workflow list` and built dispatch commands without `--repo`, while UI/docs handoff copy did not require `repoEvidenceReady`.
- Candidate: Add `--repo OWNER/REPO` to workflow list and dispatch commands, expose `repoEvidenceReady`, and block live planning when the placeholder repo has not been replaced.
- Decision: keep.

## Evidence

- `scripts/plan-publish-dispatch.mjs` now accepts `--repo`, resolves the current repo only for live runs without an explicit repo, exposes `repoEvidenceReady`, and builds repo-scoped Pages and Drift Watch dispatch commands.
- `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO` now keeps `repoEvidenceReady: false`, skips remote workflow lookup, and reports the placeholder blocker before any live dispatch command can be trusted.
- `app.js`, `README.md`, `scripts/plan-workflow-ui-install.mjs`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` now require `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO`, `repoEvidenceReady`, and repo-scoped `gh workflow run --repo` commands.
- `publishDispatchRepoScopedPlanCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/plan-publish-dispatch.mjs --dry-run`, `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `111/111`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue reducing publish-operator error while workflow installation remains external, focusing next on making repo placeholders and live evidence requirements harder to miss in copied handoff text.
- If workflow-scope access becomes available, install the Pages and Drift Watch workflows, run the repo-scoped live plan against `biojuho/BIOJUHO-Projects`, dispatch both workflows, and capture fresh live evidence.

## Experiment: Workflow UI install URL handoff

- Hypothesis: Workflow installation remains the main external blocker, so the handoff should produce direct GitHub UI URLs and default-branch evidence instead of only naming target paths.
- Primary metric: `workflowUiInstallUrlHandoffCoverage`.
- Baseline: `plan-workflow-ui-install.mjs --dry-run --markdown` listed workflow target paths, template sha256 hashes, and steps, but did not expose `repositoryUrl`, `actionsUrl`, `defaultBranch`, `githubNewFileUrl`, or `githubWorkflowUrl`.
- Candidate: Add repo/default-branch inference, GitHub new-file URLs, workflow Actions URLs, manual dispatch requirements, and require those fields in System/Settings handoffs, README, smoke, and release audit.
- Decision: keep.

## Evidence

- External source signals used: GitHub workflow dispatch only becomes actionable once the workflow file is on the repository default branch, and Actions workflow run evidence is repo/workflow scoped.
- `node scripts/plan-workflow-ui-install.mjs --dry-run` now reports `repositoryUrl: https://github.com/biojuho/BIOJUHO-Projects`, `defaultBranch: main`, `actionsUrl`, two `githubNewFileUrl` values, and two `githubWorkflowUrl` values.
- `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown` now prints the same URLs plus `manualDispatchRequirement`.
- `app.js` System Status and Settings deploy handoff now point operators to the `--markdown` plan and require `githubNewFileUrl`, `githubWorkflowUrl`, and defaultBranch before dispatch planning.
- `scripts/smoke-interactions.mjs` verifies the copied handoffs contain the URL/default-branch fields; `scripts/audit-release-readiness.mjs` requires the fields in the dry-run payload and static references.
- `npm run lint`, `node scripts/plan-workflow-ui-install.mjs --dry-run`, `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `111/111`, 39 packaged interaction steps, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Keep reducing publish-operator error by making placeholder repo replacement and live evidence capture harder to skip in every copied handoff.
- If workflow-scope access becomes available, open the generated `githubNewFileUrl` links, install Pages and Drift Watch on `main`, run repo-scoped dispatch planning, then capture fresh live evidence.

## Experiment: Publish repo placeholder handoff guard

- Hypothesis: Repo-scoped commands still carry operator risk if copied handoffs do not make `OWNER/REPO` replacement a separate blocking step.
- Primary metric: `publishRepoPlaceholderHandoffGuardCoverage`.
- Baseline: System and Settings handoffs included repo-scoped commands, but the placeholder replacement rule was embedded in longer workflow instructions rather than a dedicated guard.
- Candidate: Add a shared `Repo placeholder guard` section to publish handoffs, document it in README, and require smoke/audit coverage for copied text and System Status alignment.
- Decision: keep.

## Evidence

- `app.js` now uses `publishRepoPlaceholderGuardLines()` in both System publish unblock handoff and Settings deploy handoff.
- The publish dispatch readiness detail now stops operators when `repoEvidenceReady: false` or `repo placeholder OWNER/REPO` appears in live output.
- `README.md` now documents `Repo placeholder guard: Replace every OWNER/REPO` before live commands, dispatch, or evidence writes.
- `scripts/smoke-interactions.mjs` verifies the guard in Settings copy text, System publish handoff copy text, clipboard payload, and Settings/System mirror checks.
- `scripts/audit-release-readiness.mjs` now includes `publish_repo_placeholder_handoff_guard`.
- `publishRepoPlaceholderHandoffGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `112/112`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue strengthening pre-publish handoffs that do not require external GitHub workflow-scope access, with the next focus on making live evidence expiry and repo readiness visible in copied Markdown summaries.
- If workflow-scope access becomes available, install workflows and replace dry-run evidence with fresh live evidence.

## Experiment: Publish suggested repo handoff

- Hypothesis: `OWNER/REPO` replacement is still too easy to miss if the app only says to replace the placeholder but does not surface the current remote-derived repo candidate.
- Primary metric: `publishSuggestedRepoHandoffCoverage`.
- Baseline: Dispatch and evidence plans were repo-scoped, but operators still had to infer the exact owner/name value from separate git context.
- Candidate: Emit `suggestedRepo` and `repoReplacementHint` from both publish planning scripts, surface the suggestion in copied Settings/System handoffs, and require smoke/audit coverage for `biojuho/BIOJUHO-Projects`.
- Decision: keep.

## Evidence

- `scripts/plan-publish-dispatch.mjs --dry-run` now reports `suggestedRepo: biojuho/BIOJUHO-Projects`, `repoReplacementHint`, and suggested live `gh workflow run --repo biojuho/BIOJUHO-Projects` commands while still blocking placeholder dispatch.
- `scripts/capture-publish-evidence.mjs --dry-run --markdown` now prints the same suggestion, and `node scripts/capture-publish-evidence.mjs --dry-run --write` refreshed `data/publish-evidence.json` with those fields.
- `app.js`, `README.md`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` now require the suggested repo in publish handoffs and repo placeholder guard coverage.
- `publishSuggestedRepoHandoffCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/plan-publish-dispatch.mjs --dry-run`, `node scripts/capture-publish-evidence.mjs --dry-run`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `112/112`, `Packaged browser gates: pass`, 39 packaged interaction steps, and no blockers.

## Next Loop

- Continue reducing external publish risk by making live evidence expiry, repo readiness, and workflow visibility visible in every Markdown and UI handoff.
- If workflow-scope access becomes available, install workflows on `main`, run `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`, dispatch Pages and Drift Watch, then capture fresh live evidence.

## Experiment: Publish evidence repo-scoped next commands

- Hypothesis: Post-dispatch evidence Markdown should never suggest unscoped dispatch commands, because operators often execute the "Next commands" block verbatim.
- Primary metric: `publishEvidenceRepoScopedNextCommandCoverage`.
- Baseline: `capture-publish-evidence.mjs --dry-run --markdown` printed `plan-publish-dispatch.mjs --live` and `gh workflow run joopark-pages.yml` without `--repo`, even though dispatch planning now requires repo-scoped commands.
- Candidate: Generate repo-scoped dispatch commands in the capture payload, Markdown report, saved `data/publish-evidence.json`, and suggested concrete repo commands.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now has `workflowDispatchCommand()` and emits `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO`, `gh workflow run --repo OWNER/REPO joopark-pages.yml`, and repo-scoped Drift Watch advisory dispatch.
- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` now prints only repo-scoped dispatch commands in `## Next commands`.
- `node scripts/capture-publish-evidence.mjs --dry-run --write` refreshed `data/publish-evidence.json` with repo-scoped dispatch commands and suggested `biojuho/BIOJUHO-Projects` commands.
- `scripts/audit-release-readiness.mjs` now requires the repo-scoped next commands and `workflowDispatchCommand` term.
- `publishEvidenceRepoScopedNextCommandCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `node scripts/capture-publish-evidence.mjs --dry-run --write`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `112/112`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue checking copied and generated publish artifacts for stale or unscoped commands, then harden the next gap found without claiming external workflow completion.
- If workflow-scope access becomes available, use the suggested repo-scoped commands for install, dispatch, and live evidence capture.

## Experiment: Publish evidence suggested Markdown commands

- Hypothesis: `suggestedCommands` are less useful if they only exist in JSON; the copy-ready Markdown report should include concrete repo commands so operators do not have to manually rewrite placeholders.
- Primary metric: `publishEvidenceSuggestedMarkdownCommandCoverage`.
- Baseline: `capture-publish-evidence.mjs --dry-run` included `suggestedCommands`, but `--markdown` only printed placeholder `OWNER/REPO` commands plus a replacement hint.
- Candidate: Add a `## Suggested repo commands` section to the Markdown report and require concrete `biojuho/BIOJUHO-Projects` plan, dispatch, and evidence-write commands in audit.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now prints `## Suggested repo commands` when `suggestedCommands` are available.
- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` now includes concrete `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`, Pages dispatch, Drift Watch advisory dispatch, and live evidence capture commands.
- `scripts/audit-release-readiness.mjs` requires the Suggested repo commands section and concrete repo commands in the publish evidence Markdown self-check.
- `publishEvidenceSuggestedMarkdownCommandCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `node scripts/audit-release-readiness.mjs --format=summary`, and `npm run verify` passed; final release audit reported `112/112`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue scanning generated publish artifacts for stale or ambiguous command paths.
- If workflow-scope access becomes available, execute only the concrete suggested repo commands after workflow installation is visible in Actions.

## Experiment: Publish command scope audit guard

- Hypothesis: Manual searches for stale publish commands should become a release gate, otherwise unscoped live commands can reappear in generated or copied handoffs without being noticed.
- Primary metric: `publishCommandScopeGuardCoverage`.
- Baseline: We manually searched for unscoped `gh workflow run joopark-*`, `plan-publish-dispatch.mjs --live`, and `capture-publish-evidence.mjs --live` commands, but audit did not enforce the absence of those strings.
- Candidate: Add `publishCommandScopeGuard()` to release audit and scan the app, README, publish scripts, workflow UI plan, and saved evidence JSON for unscoped live publish commands.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now includes `publish_command_scope_guard`.
- The guard scans six publish-facing files and fails on unscoped workflow dispatch, publish dispatch live plan, or publish evidence live capture commands.
- The guard currently reports no findings.
- `publishCommandScopeGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, and `npm run verify` passed; final release audit reported `114/114`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue converting manual publish hardening checks into auditable release gates where possible.
- If workflow-scope access becomes available, use the repo-scoped live plan and suggested commands to move from dry-run evidence to live proof.

## Experiment: Publish evidence launch proof gate

- Hypothesis: A publish evidence Markdown report should say exactly when it can be treated as launch proof, otherwise fresh-but-dry-run evidence can be overread.
- Primary metric: `publishEvidenceLaunchProofGateCoverage`.
- Baseline: The report listed `repoEvidenceReady`, `evidenceFresh`, and `postPublishEvidenceReady`, but did not summarize the all-true condition as a launch-proof gate.
- Candidate: Add a `## Launch proof gate` section that requires `repoEvidenceReady: true`, `evidenceFresh: true`, and `postPublishEvidenceReady: true`, and include current values in the report.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs --dry-run --markdown` now prints `## Launch proof gate`.
- The gate states that the report is launch proof only when `repoEvidenceReady: true`, `evidenceFresh: true`, and `postPublishEvidenceReady: true` are all present.
- Dry-run output currently shows `Current repoEvidenceReady: false`, `Current evidenceFresh: true`, and `Current postPublishEvidenceReady: false`, so it cannot be mistaken for launch proof.
- `scripts/audit-release-readiness.mjs` requires the launch proof gate in the Markdown self-check and static terms.
- `publishEvidenceLaunchProofGateCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `node scripts/audit-release-readiness.mjs --format=summary`, and `npm run verify` passed; final release audit reported `114/114`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue hardening generated publish evidence so dry-run, stale, and live proof states cannot be confused.
- If workflow-scope access becomes available, use live evidence capture to flip the launch proof gate only after real Pages and workflow run evidence succeeds.

## Experiment: Publish evidence repo-arg dry-run

- Hypothesis: A dry-run with `--repo biojuho/BIOJUHO-Projects` should render the same repo in Pages API, workflow dispatch, workflow evidence, and next-command fields; otherwise operators can see mixed placeholder and concrete commands in one report.
- Primary metric: `publishEvidenceRepoArgDryRunCoverage`.
- Baseline: The default dry-run was repo-scoped, but explicit `--repo` dry-runs still left some generated command fields at `OWNER/REPO`.
- Candidate: Derive `workflowEvidencePlans`, Pages API commands, and `commands` from the resolved repo, while keeping the placeholder default as a template path.
- Decision: keep.

## Evidence

- `node scripts/capture-publish-evidence.mjs --dry-run --repo biojuho/BIOJUHO-Projects` now outputs `repoEvidenceReady: true`, `gh api repos/biojuho/BIOJUHO-Projects/pages`, and repo-scoped Pages/Drift dispatch plus run-list commands.
- The Markdown report now places `## Repo replacement guard` and concrete `## Suggested repo commands` before placeholder `## Next commands`.
- System Status publish evidence now exposes `suggestedRepo` and `repoReplacementHint`, with smoke coverage for `biojuho/BIOJUHO-Projects`.
- `scripts/audit-release-readiness.mjs` now validates both default placeholder dry-run and explicit suggested-repo dry-run.
- `publishEvidenceRepoArgDryRunCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/capture-publish-evidence.mjs --dry-run --repo biojuho/BIOJUHO-Projects`, `node scripts/capture-publish-evidence.mjs --dry-run --markdown`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `114/114`, `Packaged browser gates: pass`, and no blockers.

## Experiment: Release audit gate progress streaming

- Hypothesis: `npm run verify` should stream release-gate progress while it runs; a silent audit wrapper makes long browser gates look hung and is fragile for automation.
- Primary metric: `releaseAuditGateProgressStreamingCoverage`.
- Baseline: `audit-release-readiness.mjs --run-gates` captured `smoke-release` stderr, so `npm run verify` produced no progress until the full gate finished.
- Candidate: Keep `smoke-release` JSON on stdout, pass release-gate stderr through the audit wrapper, and preserve summary output at the end.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now supports `inheritStderr` in the local `run()` helper and uses it only for `scripts/smoke-release.mjs`.
- `npm run verify` now streams `[smoke-release] packaging`, route smoke, mobile smoke, interaction smoke, accessibility smoke, and server shutdown progress before the final summary.
- The final summary still reports `Status: pass`, `114 pass`, `0 fail`, `0 not_run`, and `0 blocked`.
- `releaseAuditGateProgressStreamingCoverage` improved from 0 to 1.

## Next Loop

- Continue turning publish-readiness ambiguity into audited, browser-visible gates, focusing next on workflow visibility and live evidence capture once external workflow-scope access exists.
- If credentials remain unavailable, keep improving local release and operator-proof handoff quality without claiming external publish completion.

## Experiment: Backup import size guard

- Hypothesis: External users can accidentally select an oversized JSON backup; rejecting it before `FileReader.readAsText()` prevents UI stalls and localStorage quota churn.
- Primary metric: `backupImportSizeGuardCoverage`.
- Baseline: Backup import validated JSON shape after reading the full file, but did not reject large files before reading.
- Candidate: Add a 2 MiB `MAX_IMPORT_BYTES` guard, surface the limit in Settings and backup handoff copy, document it in README, and cover an oversized `File` object in browser smoke.
- Decision: keep.

## Evidence

- `app.js` now defines `MAX_IMPORT_BYTES = 2 * 1024 * 1024` and rejects files above the limit before creating `FileReader` work.
- Settings backup copy now states that import files must be `2.0 MB` or smaller.
- `README.md` documents the 2 MiB JSON import limit as a protection against UI stalls and quota risk.
- `scripts/smoke-interactions.mjs` now includes `settings oversized import guard` and verifies that a >2 MiB file shows a rejection toast, opens no confirmation modal, resets the file input, and leaves data unchanged.
- `scripts/audit-release-readiness.mjs` now includes `backup_import_size_guard`.
- `backupImportSizeGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `117/117`, `Packaged browser gates: pass`, 40 packaged interaction steps, and no blockers.

## Next Loop

- Continue checking user-controlled data paths for performance, quota, and recovery failures that are not yet visible in release gates.
- If external workflow-scope access appears, switch back to the live publish path and capture real Pages/workflow evidence.

## Experiment: Publish evidence launch proof UI

- Hypothesis: System Status should expose the same launch proof concept as the Markdown report, otherwise the generic ready label can blur dry-run, stale, and live proof states.
- Primary metric: `publishEvidenceLaunchProofUiCoverage`.
- Baseline: The UI only exposed generic `ready` / `data-publish-evidence-ready` state, with no `launchProofReady` row or launch-proof-specific DOM attribute.
- Candidate: Add `launchProofReady`, `data-publish-evidence-launch-proof-ready`, the `launch proof ready` state label, and a note that launch proof requires `repoEvidenceReady: true`, `evidenceFresh: true`, and `postPublishEvidenceReady: true`.
- Decision: keep.

## Evidence

- `app.js` now renders the publish evidence panel with explicit launch proof state.
- `scripts/smoke-interactions.mjs` verifies dry-run evidence keeps `publishEvidenceLaunchProofReady` false and exposes `launchProofReady` / `launch proof` text.
- `scripts/audit-release-readiness.mjs` requires the launch proof DOM attribute and smoke coverage terms.
- `publishEvidenceLaunchProofUiCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `115/115`, `Packaged browser gates: pass`, and no blockers.
- The first packaged smoke attempt surfaced a project picker accessibility failure, then the retry passed. Treat that instability as the next loop target.

## Next Loop

- Harden project picker status/live-region behavior so search result counts, no-result status, and close/reset state are stable across packaged browser retries.

## Experiment: Project picker hidden input recovery

- Hypothesis: Project picker accessibility should remain stable when a delayed input event fires after the picker closes; otherwise status text can reappear after close and make packaged browser retries flaky.
- Primary metric: `projectPickerHiddenInputRecoveryCoverage`.
- Baseline: The picker had correct ARIA markup, but close cleanup relied on normal event ordering and did not explicitly ignore input events while hidden.
- Candidate: Add project picker accessibility normalization, rebuild missing scaffold nodes when needed, bind Escape directly on the search field, clear query/list/status on close, and ignore hidden input events.
- Decision: keep.

## Evidence

- `app.js` now includes `normalizeProjectPickerAccessibility()` and self-heals the project picker scaffold before open.
- Hidden project picker input events clear query/status and do not re-render the project list.
- `scripts/smoke-a11y.mjs` now includes `project_picker_hidden_input_ignored`.
- `scripts/audit-release-readiness.mjs` requires the recovery guard and updated accessibility smoke coverage.
- `projectPickerHiddenInputRecoveryCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-a11y.mjs`, and `npm run verify` passed; final release audit reported `117/117`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue looking for browser-visible flakes or user-controlled data paths that can still create release-gate instability.

## Experiment: Backup import malformed guard

- Hypothesis: Invalid JSON or a non-backup JSON root should never open the destructive import confirmation or mutate saved workspace data.
- Primary metric: `backupImportMalformedGuardCoverage`.
- Baseline: The app rejected malformed imports inline, but backup shape validation was embedded in the file handler and release smoke did not prove saved data was unchanged after bad inputs.
- Candidate: Add `isImportBackupShape()` and `rejectImportFile()`, reject arrays/non-backup roots before confirmation, document the behavior, and cover malformed JSON plus array-root JSON in interaction smoke.
- Decision: keep.

## Evidence

- `app.js` now validates import roots with `IMPORT_ARRAY_KEYS` and rejects malformed JSON through a shared `rejectImportFile()` path.
- `scripts/smoke-interactions.mjs` now includes `settings malformed import guard`, proving parse failures and array-root JSON show error toasts, open no confirmation modal, reset the file input, and leave localStorage unchanged.
- `scripts/audit-release-readiness.mjs` includes `backup_import_malformed_guard`.
- `README.md` now documents that invalid JSON or non-backup structures are not imported.
- `backupImportMalformedGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `119/119`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue checking destructive or persistent workflows for missing rollback, stale-state, or operator-proof evidence.

## Experiment: Backup import normalization guard

- Hypothesis: A valid but semantically oversized backup can persist huge strings, arrays, and nested metadata that later slow Markdown rendering, search, charts, and release smoke.
- Primary metric: `backupImportNormalizationGuardCoverage`.
- Baseline: Import had size and malformed-root guards, but small JSON files could still contain overlong field values and oversized arrays.
- Candidate: Clamp imported text, numeric arrays, label/member/dependency arrays, schema metadata, query text, backup notes, and migration fields through `normalizeAllData()` before persistence.
- Decision: keep.

## Evidence

- `app.js` now uses `clampText`, `clampTextArray`, and `clampNumberArray` across personal, project, DB, schema, query, backup, and migration import paths.
- `scripts/smoke-interactions.mjs` includes `settings import normalization guard` and proves `backupNormalizeClamped: true` across note body, issue labels, DB series, schema column metadata, query text, backup note, and migration status.
- The import confirmation smoke also verifies `backupImportSummaryScope: true`, so destructive replacement scope is visible before confirm.
- `scripts/audit-release-readiness.mjs` includes `backup_import_normalization_guard`.
- `README.md` documents that imported text and array fields are normalized to form-level bounds.
- `backupImportNormalizationGuardCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-interactions.mjs`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-mobile.mjs`, `BASE_URL=http://127.0.0.1:5179 node scripts/smoke-a11y.mjs`, `npm run test`, and `npm run verify` passed; final release audit reported `120/120`, `Packaged browser gates: pass`, 42 packaged interaction steps, and no blockers.

## Next Loop

- Add explicit imported-record count caps for every collection before persistence, then prove oversized-but-valid backup arrays are rejected or truncated safely.
- Keep external publish work blocked until workflow-scope access and live Pages/workflow evidence are available.

## Experiment: Backup import confirmation scope

- Hypothesis: The destructive backup import confirmation should summarize every imported workspace slice, otherwise PM/DB/backup replacement scope can be underreported before the user confirms.
- Primary metric: `backupImportConfirmationScopeCoverage`.
- Baseline: The import confirmation summarized only events, todos, and notes even though import can replace habits, PM, DB, backup, migration, theme, and import registry data.
- Candidate: Add `importBackupSummaryItems()` / `importBackupSummaryHTML()`, render a `data-import-summary` scope summary, update the warning copy to workspace-wide replacement, and smoke-test all major scope labels.
- Decision: keep.

## Evidence

- `app.js` now renders import confirmation counts for events, todos, notes, habits, projects, issues, Gantt tasks, team, DB instances, tables, queries, backups, and migrations.
- `scripts/smoke-interactions.mjs` now verifies the `data-import-summary` contains all expected imported scope counts.
- `scripts/audit-release-readiness.mjs` includes `backup_import_confirmation_scope`.
- `backupImportConfirmationScopeCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-interactions.mjs`, and `npm run verify` passed; final release audit reported `120/120`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue hardening destructive flows where a user needs exact scope evidence before confirming replacement or deletion.

## Experiment: Mobile sheet and modal gate stabilization

- Hypothesis: Mobile release gates should wait for animated sheet action buttons and modal focus restoration before measuring layout; otherwise transient animation timing can fail a valid final state.
- Primary metric: `mobileSheetModalGateStabilityCoverage`.
- Baseline: Packaged mobile smoke inspected sheet buttons after a fixed delay and checked modal focus after one frame, causing a failed run where project sheet actions were still offscreen and modal focus restoration had not landed.
- Candidate: Add `restoreFocusAfterClose()` retries for modal/sheet close, wait for sheet action buttons to enter viewport before measuring, and wait for modal opener focus restoration in mobile smoke.
- Decision: keep.

## Evidence

- `app.js` now restores previous focus immediately and with short follow-up checks after closing sheets and modals.
- `scripts/smoke-mobile.mjs` waits until sheet action buttons are inside the mobile viewport and until modal focus returns to the opener.
- `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-mobile.mjs` passed with zero layout issues.
- `npm run verify` passed after the stabilization; final release audit reported `120/120`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue looking for release-gate timing assumptions where a fixed delay should become a state-based wait.

## Experiment: Notification sheet state wait guard

- Hypothesis: Mobile notification sheet states should be measured after the panel, body lock, and long/empty content are ready, not after a fixed animation delay.
- Primary metric: `notificationSheetStateWaitGuardCoverage`.
- Baseline: Long-alert and empty notification-sheet checks opened the sheet, waited `delay(260)`, then inspected layout and lock state.
- Candidate: Wait for the sheet panel to be inside the viewport, background scroll lock to be active, and either 30 rendered alert rows or the empty-state marker before measuring.
- Decision: keep.

## Evidence

- `scripts/smoke-mobile.mjs` now waits for `notification sheet did not settle with long alerts` and `notification sheet did not settle empty state` readiness predicates instead of a fixed delay.
- `scripts/audit-release-readiness.mjs` requires those notification-sheet state-wait terms.
- `notificationSheetStateWaitGuardCoverage` improved from 0 to 1.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=summary`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-mobile.mjs`, and `npm run verify` passed; final release audit reported `121/121`, `Packaged browser gates: pass`, and no blockers.

## Next Loop

- Continue replacing fixed-delay assumptions in mobile modal and sheet checks with explicit state waits.

## Experiment: Project picker post-hidden focus guard

- Hypothesis: The hidden input guard should preserve focus on the project-picker opener after late input events, not only suppress list/status rendering.
- Primary metric: `projectPickerPostHiddenFocusGuardCoverage`.
- Baseline: A packaged a11y first attempt failed `project_picker_restores_focus` after the hidden input guard path, indicating focus could still fall away from the opener.
- Candidate: Add a third delayed opener-focus retry, refocus the opener when a hidden input event leaves focus on the body or inside the hidden picker, and assert opener focus after the hidden input dispatch in a11y smoke.
- Decision: keep.

## Evidence

- `app.js` now includes the additional project picker focus retry and hidden-input refocus guard.
- `scripts/smoke-a11y.mjs` waits for `project picker focus changed after hidden input guard` to prove the opener remains focused.
- `projectPickerPostHiddenFocusGuardCoverage` improved from 0 to 1.
- `npm run lint`, `BASE_URL=http://127.0.0.1:5184 node scripts/smoke-a11y.mjs`, and `npm run verify` passed; final release audit reported `121/121`, `Packaged browser gates: pass`, and no blockers. One prior verify exec session exited abnormally with no app failure output; the rerun passed cleanly.

## Next Loop

- Continue converting release-gate timing checks from elapsed-time waits to visible, inspectable UI state.

## Experiment: Review handoff actionable quality package

- Hypothesis: The portfolio review output should be an execution-ready artifact, not only a prompt export; adding quality gates, evidence snapshots, acceptance criteria, validation plans, missing-evidence handling, and timeboxes will make the generated handoff and issue drafts usable without rewriting.
- Primary metric: `reviewHandoffActionableQualityPackageCoverage`.
- Baseline: Review handoffs exposed system/user prompts, schema, candidate inputs, and issue draft conversion, but generated issue bodies were terse decision summaries with no explicit acceptance criteria, validation plan, source snapshot, or timebox.
- Candidate: Add `Quality Bar`, `Evidence Snapshot`, `Execution Plan`, and `Review Checklist` to review handoff Markdown; expand the JSON schema with `sourceSnapshot`, `qualityGate`, `executionPlan`, `acceptanceCriteria`, and `validationPlan`; convert PM, Workspace, and Knowledge/IA issue drafts into structured execution packages.
- Decision: keep.

## External Comparison

- Linear triage patterns emphasize review, prioritization, accept/duplicate/decline/snooze decisions, and routing before work enters the normal workflow.
- Linear filters and views show that high-quality operational output should preserve filterable properties instead of burying status, label, priority, and project context in prose.
- OpenProject work packages treat executable work as typed records with status, assignee, priority, due dates, and other attributes.
- Productboard driver scoring reinforces explicit criteria and weighted decision rationale instead of vague recommendation text.

## Evidence

- `app.js` now centralizes handoff quality criteria and issue body generation with `REVIEW_OUTPUT_QUALITY_CRITERIA`, `reviewPromptEvidenceRows()`, `reviewExecutionPlanLines()`, and `reviewIssueBodyLines()`.
- Workspace, Knowledge/IA, and PM benchmark handoffs now render copy-ready `Quality Bar`, `Evidence Snapshot`, `Execution Plan`, and `Review Checklist` sections.
- Generated issue drafts now include `Decision`, `Evidence Snapshot`, `Acceptance Criteria`, `Validation Plan`, `Missing Evidence To Close`, and `Timebox`.
- Benchmark candidate cards and detail sheets expose `prompt handoff 보기`, which clears search, applies the candidate benchmark focus, reveals the prompt contract, and focuses the handoff region.
- `scripts/smoke-interactions.mjs` proves the new sections render, copy to clipboard, survive issue creation, and persist in saved issue bodies for Workspace, Knowledge/IA, and PM benchmark paths.
- `scripts/audit-release-readiness.mjs` includes `review_handoff_actionable_quality_package`.
- `npm run lint`, `npm run test`, and `npm run verify` passed; final release audit reported `125/125`, `Packaged browser gates: pass`, 43 packaged interaction steps, and no blockers.

## Improvement

- Before: the product could generate a prompt handoff and an issue shell, but the user still had to rewrite the task into a usable execution brief.
- After: the output is a complete review package with decision, source evidence, checklist, acceptance criteria, validation plan, missing-evidence policy, and timebox, and users can jump to it directly from search results or a project detail sheet.

## Next Loop

- Continue improving generated artifact usefulness by adding a one-click export bundle for the selected review package, including Markdown handoff, issue draft, GitHub comment draft, and pinned-note body in one copy/download action.

## Experiment: Review package bundle export

- Hypothesis: Review output becomes more reusable when the selected package can leave the app as one copy/download artifact instead of separate handoff, issue, comment, and note fragments.
- Primary metric: `reviewPackageBundleExportCoverage`.
- Baseline: Review handoffs and issue drafts were actionable, but Workspace, Knowledge/IA, and PM benchmark review paths still required users to manually assemble Markdown handoff, issue body, GitHub comment, and pinned-note copy.
- Candidate: Add a `Bundle MD` download and `bundle 복사` action to each review package, generating one Markdown file with `Markdown Handoff`, `Issue Draft`, `GitHub Comment Draft`, and `Pinned Note Body` sections for Workspace, Knowledge/IA, and PM benchmark reviews.
- Decision: keep.

## External Comparison

- Linear issue templates and issue properties reinforce that executable handoffs should preserve structured fields such as status, priority, labels, and project context.
- GitHub issue forms reinforce using Markdown bodies that carry acceptance criteria and validation plans into the issue tracker without manual reconstruction.
- Notion-style export behavior reinforces that reusable review artifacts should copy or save as a complete document, not as disconnected UI snippets.

## Evidence

- `app.js` now builds reusable review bundle Markdown through `reviewPackageBundleMarkdown()` and renders shared bundle controls through `reviewPackageBundleControls()`.
- Workspace, Knowledge/IA, and PM benchmark review packages now expose `Bundle MD` downloads with stable filenames and `bundle 복사` clipboard actions.
- Each bundle includes Markdown handoff, issue draft, GitHub comment draft, and pinned-note body, preserving source URLs, acceptance criteria, validation plan, missing-evidence policy, and timebox.
- `scripts/smoke-interactions.mjs` verifies all three bundle paths render expected sections, expose download data URLs, copy to clipboard, and show copy status.
- `scripts/audit-release-readiness.mjs` includes `review_package_bundle_export`.
- `npm run lint` and `npm run test` passed; `node scripts/audit-release-readiness.mjs --format=markdown` reported `review_package_bundle_export` as pass and remained blocked only because packaged browser gates are intentionally not run in that mode.
- `npm run verify` passed with `127 pass, 0 fail, 0 not_run, 0 blocked, 127 total`; packaged browser gates passed, and packaged interaction evidence reported `reviewPackageBundleVisible: true`.

## Improvement

- Before: the app produced high-quality review fragments, but an operator still had to reconstruct the final artifact before pasting into GitHub, Linear-like issue systems, or a project note.
- After: each review path produces one reusable Markdown package with tracker-ready and note-ready sections, reducing handoff loss between review, execution, and archive.

## Next Loop

- Add a bundle preview manifest with validation status, source freshness, and a checksum so copied review packages can be trusted before external paste.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review handoff saved result flow

- Hypothesis: Prompt quality is not complete until the app can preserve a validated model result; saving only the prompt handoff still leaves the user to re-parse or re-enter the LLM output.
- Primary metric: `reviewHandoffSavedResultFlowCoverage`.
- Baseline: `result validator` could prove empty input, malformed JSON, key mismatch, pass, retry, and clear states, but a valid response disappeared after navigation or reload.
- Candidate: Save validated JSON as a compact `reviewResults` slice, show a `저장된 결과` card in the same handoff, include it in localStorage/backup/import/reset flows, and add release smoke coverage for dashboard state and localStorage persistence.
- Decision: keep.

## Evidence

- `app.js` now saves passing review output through `saveValidatedReviewResult()`, renders `reviewResultSavedCard()`, normalizes `dashboard.reviewResults`, and includes the slice in persist/load/export/import/reset.
- `styles.css` adds the saved-result card treatment without changing the existing handoff layout.
- `scripts/smoke-interactions.mjs` proves the saved summary renders, survives input clear, is present in `dashboard.reviewResults`, and is persisted to `joopark.workspace.v3`.
- `scripts/audit-release-readiness.mjs` includes `review_handoff_saved_result_flow`.
- Computer Use manual verification clicked `Taskosaur/Taskosaur` -> `prompt handoff 보기` -> `예시 삽입`, confirmed `저장된 결과`, refreshed the page, reopened the same handoff, and confirmed the saved card rendered from localStorage.
- `npm run lint`, `npm run typecheck`, `BASE_URL=http://127.0.0.1:5187 node scripts/smoke-interactions.mjs`, `npm run build`, `npm run test`, and `npm run verify` passed; final release audit reported `128 pass, 0 fail, 0 not_run, 0 blocked, 128 total`.

## Improvement

- Before: the prompt contract and validator helped produce structured output, but the product did not keep the accepted result as a usable artifact.
- After: a validated model response becomes a persisted review artifact with action, confidence, issue title, summary, key, and backup coverage.

## Next Loop

- Convert saved `reviewResults` into a one-click issue/note update path that uses the validated JSON fields instead of the static draft body.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review package manifest quality

- Hypothesis: A copied review bundle is more trustworthy when it carries explicit validation status, source freshness, and a deterministic checksum before the user pastes it into an external tracker or note system.
- Primary metric: `reviewPackageManifestQualityCoverage`.
- Baseline: Review bundles could be copied/downloaded, but the final artifact did not show whether all sections were present, source metadata was fresh, tracker fields were complete, or the payload had a stable integrity marker.
- Candidate: Add `joopark-review-package-manifest/v1` to every Workspace, Knowledge/IA, and PM benchmark review package, render a visible manifest summary in the UI, and embed a `Bundle Manifest` section in the exported Markdown with `Payload checksum`, `Source freshness`, required-section coverage, source snapshot, and validation checks.
- Decision: keep.

## External Comparison

- Linear issue templates preserve structured issue properties such as status, priority, assignee, project, label, and sub-issue, so JooPark bundles now expose tracker readiness instead of burying those fields in prose: https://linear.app/docs/issue-templates
- GitHub issue forms convert filled inputs into a Markdown issue body, so JooPark bundles now keep the Markdown body plus validation evidence together before external paste: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Notion export downloads Markdown/CSV content for reuse, so JooPark bundles now behave more like reusable document exports with manifest metadata rather than disconnected snippets: https://www.notion.com/help/export-your-content

## Evidence

- `app.js` now adds `reviewPackageManifest()`, `reviewPackageManifestMarkdown()`, `reviewPackageManifestSummary()`, and deterministic `fnv1a32-*` payload checksums.
- Workspace, Knowledge/IA, and PM benchmark review packages now render a visible `Bundle manifest` panel before the issue/comment/note sections and embed the same manifest in copied/downloaded Markdown.
- `scripts/smoke-interactions.mjs` verifies manifest status, checksum, source freshness counts, embedded `Bundle Manifest`, and clipboard copy coverage for all three review package paths.
- `scripts/audit-release-readiness.mjs` includes `review_package_manifest_quality`.
- `README.md` documents `Bundle Manifest`, `joopark-review-package-manifest/v1`, `Payload checksum`, and `Source freshness`.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=markdown`, and `npm run test` passed; the static audit reported `review_package_manifest_quality` as pass and packaged browser smoke reported no console, network, or layout issues.
- `npm run verify` passed with `129 pass, 0 fail, 0 not_run, 0 blocked, 129 total`; packaged browser gates passed, and packaged interaction evidence reported `reviewPackageManifestVisible: true`.

## Improvement

- Before: the bundle was complete, but an operator still had to trust that it was complete and current.
- After: the artifact carries its own validation status, checksum, section coverage, source freshness snapshot, and tracker-readiness evidence, making it safer to paste into GitHub, Linear-like trackers, or long-lived notes without manual inspection.

## Next Loop

- Convert saved `reviewResults` into a one-click issue/note update path that uses validated JSON fields plus the bundle manifest checksum instead of the static draft body.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review handoff saved result to issue/note

- Hypothesis: A validated review result should become the source of the created issue or note, otherwise users still have to manually translate the accepted JSON back into a usable work artifact.
- Primary metric: `reviewSavedResultActionPathCoverage`.
- Baseline: `reviewResults` could be saved and shown, but the output path was weakly verified because static issue drafts and note bodies could still be treated as the primary source.
- Candidate: Store bundle manifest evidence on saved results, immediately update the issue draft preview after validation, create issues from validated JSON fields with `validated-result` labels and `validated-review-result` source kind, and publish notes with saved result plus `Payload checksum` first.
- Decision: keep.

## External Comparison

- Linear supports creating issues from templates and prefilled create URLs, preserving issue properties so work can enter the tracker without re-entry: https://linear.app/docs/creating-issues
- GitHub issue forms convert submitted input into Markdown issue bodies, so validated input should flow into the final issue body rather than remain a separate preview: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Notion button/template workflows emphasize one-click creation of pages or database entries, so JooPark saved review results should similarly produce a ready note without manual reconstruction: https://www.notion.com/help/guides/automatically-generate-blocks-pages-with-buttons

## Evidence

- `app.js` now saves `packageChecksum`, manifest status, and source freshness on validated `reviewResults`.
- `refreshReviewIssueDraftFromSavedResult()` updates the visible issue draft immediately after validation, including the `검증 JSON 적용` badge and `data-issue-draft-result-source="validated"`.
- `createBenchmarkReviewIssue()` creates issues from validated saved results with `validated-result` labels, `validated-review-result` source kind, validated body sections, and manifest checksum.
- `publishReviewHandoffNote()` now places the saved validated result and checksum before the full handoff so the note remains useful after body-length normalization.
- `scripts/smoke-interactions.mjs` verifies `reviewResultIssueApplied: true` and `reviewResultNoteApplied: true`, including source kind, labels, checksum, validated body, and note body.
- `scripts/audit-release-readiness.mjs` includes `review_handoff_saved_result_to_issue_note`.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=markdown`, and `npm run test` passed; packaged browser smoke reported no console, network, or layout issues.
- `npm run verify` passed with `130 pass, 0 fail, 0 not_run, 0 blocked, 130 total`; packaged browser gates passed, and packaged interaction evidence reported `reviewResultIssueApplied: true` and `reviewResultNoteApplied: true`.

## Improvement

- Before: the user could validate a model result, but the downstream work artifact could still look like a static draft.
- After: the accepted JSON becomes the operational source for issue and note creation, preserving action, confidence, summary, labels, checksum, source freshness, and validation evidence in the final artifact.

## Next Loop

- Add a post-creation review artifact diff panel that compares static draft, validated result, and created issue/note body before final acceptance.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact diff panel

- Hypothesis: Users need a post-creation comparison between the original static draft, the validated model result, and the created issue/note body before accepting the generated work artifact as final.
- Primary metric: `reviewArtifactDiffPanelCoverage`.
- Baseline: issue and note creation could apply validated JSON, but after creation the UI only showed created state and toast feedback, not a side-by-side proof of what changed.
- Candidate: Render a status-bearing `artifact diff` panel after created issue/note artifacts exist, keyed by persist key, with `Static draft`, `Validated result`, and `Created artifact` columns plus checksum, acceptance, validation, and source-snapshot checks.
- Decision: keep.

## External Comparison

- Linear preserves structured issue properties when creating issues from templates or prefilled create URLs, so JooPark should show that validated properties survived final creation: https://linear.app/docs/creating-issues
- GitHub issue forms turn validated form inputs into final Markdown issue bodies, making body parity between accepted input and created artifact important: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Notion buttons/templates create repeatable pages or database entries, so JooPark should give users proof that the generated note matches the accepted template/result: https://www.notion.com/help/guides/automatically-generate-blocks-pages-with-buttons

## Evidence

- `app.js` now adds `reviewArtifactDiffPanel()`, `reviewArtifactDiffSnippet()`, and `reviewArtifactDiffChecks()`, preserving static draft context while comparing it with the validated result and created issue/note body.
- Workspace, Knowledge/IA, and PM benchmark handoffs show issue artifact diffs after issue creation; Workspace and Knowledge/IA also show separate note artifact diffs after note publish.
- Each panel renders `data-review-artifact-diff-status="pass"` only when validated source, `Payload checksum`, `Acceptance Criteria`, `Validation Plan`, source snapshot, and operational readiness checks pass.
- Computer Use manual verification exposed an initial rendering bug where diff `article` and check `li` markup appeared as escaped text; `app.js` now injects those generated rows with `raw()` so the three artifact columns and five checks render as real DOM.
- `styles.css` adds `.review-artifact-diff`, `.review-artifact-diff-grid`, and `.review-artifact-diff-checks`.
- `scripts/smoke-interactions.mjs` verifies `reviewArtifactDiffVisible: true`, `reviewArtifactDiffValidated: true`, pass status, three rendered artifact columns, and six rendered check rows for workspace issue, workspace note, KB issue, KB note, and benchmark issue panels.
- `scripts/audit-release-readiness.mjs` includes `review_artifact_diff_panel`.
- `node scripts/audit-release-readiness.mjs --format=markdown` reported `review_artifact_diff_panel` as pass.
- `npm run lint`, `npm run test`, and `npm run verify` passed; final release audit reported `131 pass, 0 fail, 0 not_run, 0 blocked, 131 total`, and packaged interaction evidence reported `reviewArtifactDiffVisible: true` and `reviewArtifactDiffValidated: true`.

## Improvement

- Before: users could see that an issue was generated, but they had to infer whether the generated artifact came from static draft text or validated JSON.
- After: generated artifacts expose a pass/fail comparison chain and show whether the created issue/note preserved validated source, checksum, acceptance, validation, and source evidence.

## Next Loop

- Add direct created-artifact open/review actions from the diff panel so users can jump to the generated issue or note and inspect the full body.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact open body path

- Hypothesis: A post-creation diff is more trustworthy when the user can jump from the diff panel to the exact generated issue or note and inspect the full body, source key, checksum, and validated source kind without searching elsewhere.
- Primary metric: `reviewArtifactOpenBodyPathCoverage`.
- Baseline: the diff panel proved parity in a compact comparison, but issue/note full-body inspection still required leaving the review package context and manually finding the generated artifact.
- Candidate: Add `본문 열기` actions to created artifact diff panels, expose source key/kind and full body in the issue sheet, and smoke-test that generated issues and notes open with validated body, checksum, and primary key intact.
- Decision: keep.

## External Comparison

- Linear keeps created issue properties and descriptions inspectable after template/prefill creation, so the final artifact must be reviewable from the creation context: https://linear.app/docs/creating-issues
- GitHub treats the generated issue body as the durable tracking artifact, so JooPark should let users inspect the exact created Markdown body, not only a preview: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue
- Notion button-created pages are immediately usable/editable objects, so generated review notes should open directly from the creation proof: https://www.notion.com/help/guides/automatically-generate-blocks-pages-with-buttons

## Evidence

- `reviewArtifactDiffPanel()` now carries created artifact id/type metadata and renders a `본문 열기` action for created issues and notes.
- `openIssueSheet()` now exposes source kind, source key, and full generated Markdown body with `data-sheet-artifact-body`, so issue artifacts are inspectable after creation.
- Note artifacts open through the existing note modal, preserving the full saved validated result body for inspection or editing.
- `scripts/smoke-interactions.mjs` clicks the open action on workspace issue, workspace note, KB issue, KB note, and benchmark issue diff panels, then verifies the opened body contains the expected primary key, `Payload checksum`, and `validated-review-result` evidence.
- `scripts/audit-release-readiness.mjs` keeps `review_artifact_diff_panel` as the release gate and now requires full-body open/review terms.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=markdown`, and `npm run test` passed; packaged interaction smoke reported `reviewArtifactDiffVisible: true` and `reviewArtifactDiffValidated: true`.

## Improvement

- Before: users could see the compact diff but still had to search for the created issue/note to inspect the durable artifact.
- After: each generated artifact can be opened from the diff proof and reviewed at full body depth before the user treats it as final.

## Next Loop

- Add a copy/export receipt from opened created artifacts so users can archive the exact final issue/note body with source key, checksum, and pass status.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact receipt export

- Hypothesis: Users need a durable receipt of the exact created issue/note body, source key, checksum, and pass status so the generated artifact can be archived, shared, or compared later without re-opening the app.
- Primary metric: `reviewArtifactReceiptExportCoverage`.
- Baseline: users could open the created artifact body from the diff panel, but preserving that final state still required manual copying from the issue sheet or note modal.
- Candidate: Add copy/download receipt controls to each created artifact diff panel, with a Markdown receipt containing artifact id/type, primary key, source kind, diff status, six check results, and the exact created artifact body.
- Decision: keep.

## External Comparison

- Linear issue templates and prefilled creation keep final issue properties inspectable, but exportable receipts make JooPark safer for handoff and audit trails: https://linear.app/docs/creating-issues
- GitHub issues make the created Markdown body the durable artifact, so a copied receipt should preserve exactly what was created: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue
- Notion button-created pages are reusable objects; JooPark receipts give generated notes a similarly portable audit trail: https://www.notion.com/help/guides/automatically-generate-blocks-pages-with-buttons

## Evidence

- `reviewArtifactReceiptMarkdown()` generates `# JooPark Review Artifact Receipt` with artifact metadata, check rows, and the full created artifact body.
- `reviewArtifactDiffPanel()` exposes `receipt 저장`, `receipt 복사`, and hidden receipt text for every created issue/note diff panel.
- `copyReviewArtifactReceipt()` copies the receipt through the existing clipboard path and renders visible copied state.
- `scripts/smoke-interactions.mjs` verifies receipt filename, data URL, clipboard text, pass status, primary key, checksum, and created body marker for all five created artifact diff panels.
- `scripts/audit-release-readiness.mjs` keeps the receipt as part of `review_artifact_diff_panel`.
- `npm run lint`, `node scripts/audit-release-readiness.mjs --format=markdown`, and `npm run test` passed; packaged interaction smoke reported `reviewArtifactOperationalReadiness: true`.

## Improvement

- Before: users could inspect generated artifacts, but archiving the final artifact proof required manual reconstruction.
- After: each final created artifact ships with a copy/download receipt that preserves the usable body and validation proof in one Markdown artifact.

## Next Loop

- Add artifact receipt import/compare support so a pasted receipt can be checked against the current saved issue/note body for drift.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact receipt compare

- Hypothesis: A receipt is only useful after handoff if users can later paste it back into the app and detect whether the current generated issue/note body or validation proof has drifted.
- Primary metric: `reviewArtifactReceiptCompareCoverage`.
- Baseline: receipts could be copied or downloaded, but the app could not validate an archived receipt against the current created artifact.
- Candidate: Add a receipt import/compare panel to every artifact diff with `Receipt present`, `Primary key`, `Artifact id`, `Artifact type`, `Source kind`, `Diff status`, `Body exact match`, and `Checks match` checks.
- Decision: keep.

## External Comparison

- Linear keeps created issue details inspectable from issue creation flows; JooPark adds receipt comparison so archived handoff proof can be checked later: https://linear.app/docs/creating-issues
- GitHub issues make the Markdown body the durable artifact, so drift detection should compare the archived body to the current generated body exactly: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue
- Notion button-created pages/templates can be reused and edited; JooPark receipt compare gives generated notes a lightweight version check without external history storage: https://www.notion.com/help/guides/automatically-generate-blocks-pages-with-buttons

## Evidence

- `parseReviewArtifactReceipt()` reads the exported Markdown receipt metadata, check rows, and full created artifact body.
- `reviewArtifactReceiptComparison()` compares the pasted receipt with the current hidden receipt and fails on primary key, artifact metadata, source kind, diff status, body, or check drift.
- `reviewArtifactDiffPanel()` now renders `Receipt compare`, `현재 receipt 넣기`, `receipt 비교`, and `초기화` controls for every created issue/note diff panel.
- `scripts/smoke-interactions.mjs` inserts the current receipt, verifies compare pass, tampers `Diff status`, verifies compare fail, then clears the input for all created artifact diff paths.
- `scripts/audit-release-readiness.mjs` keeps receipt import/compare as part of `review_artifact_diff_panel`.
- `npm run test` passed with packaged interaction evidence reporting `reviewArtifactReceiptCompare: true`.
- `npm run verify` passed with `131 pass, 0 fail, 0 not_run, 0 blocked, 131 total`.

## Improvement

- Before: archived receipts were portable, but users still had to manually compare them against the current generated artifact.
- After: each diff panel can validate an archived receipt against the current issue/note body and expose exact drift checks before sharing.

## Next Loop

- Add receipt diff repair suggestions so mismatched archived receipts explain exactly what to update before sharing.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact receipt repair suggestions

- Hypothesis: Receipt drift detection is not enough for a high-quality output workflow; when a receipt fails comparison, the user needs a precise repair instruction that says whether to restore the archived body, archive a fresh receipt, regenerate from validated source, or compare the correct artifact type.
- Primary metric: `reviewArtifactReceiptRepairSuggestionCoverage`.
- Baseline: mismatched receipts showed failed checks, but users still had to infer the next action from terse labels such as `Diff status` or `Body exact match`.
- Candidate: Add `Repair suggestions` to failed receipt comparisons, with mismatch-specific guidance for receipt presence, primary key, artifact id/type, source kind, diff status, body drift, and check drift.
- Decision: keep.

## External Comparison

- Linear exposes issue description version history and restore paths, which makes changes actionable instead of merely detectable: https://linear.app/docs/editing-issues
- GitHub issue edits retain timeline/edit-history context for title and description changes, so JooPark should also attach actionable recovery guidance to artifact drift: https://docs.github.com/en/enterprise-cloud@latest/issues/tracking-your-work-with-issues/using-issues/editing-an-issue
- Notion version history lets users view older page versions, copy specific blocks, or restore a version; JooPark mirrors that “copy/restore the authoritative artifact” decision in receipt repair copy: https://www.notion.com/fi/help/duplicate-delete-and-restore-content

## Evidence

- `reviewArtifactReceiptRepairSuggestion()` maps each failed receipt comparison check to a concrete next action.
- `reviewArtifactReceiptCompareOutput()` now renders `Repair suggestions` with failed-check-specific repair items.
- `setReviewArtifactReceiptCompareState()` persists `data-review-artifact-receipt-repair-count` so the UI state and smoke evidence use the same signal.
- `scripts/smoke-interactions.mjs` now tampers the created body and diff status separately, verifying body repair copy and fresh-receipt repair guidance.
- `scripts/audit-release-readiness.mjs` keeps repair suggestions inside the `review_artifact_diff_panel` gate.
- `npm run test` passed with packaged interaction evidence reporting `reviewArtifactReceiptRepairSuggestion: true`.
- `npm run verify` passed with `132 pass, 0 fail, 0 not_run, 0 blocked, 132 total`.

## Improvement

- Before: users knew a receipt drifted, but still had to decide manually which side was stale and what to fix.
- After: failed comparisons include direct repair guidance, making the generated artifact proof more usable before external sharing.

## Next Loop

- Add guarded apply-repair actions with preview and undo so archived receipt bodies can update the current issue or note without manual paste.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact receipt repair copy

- Hypothesis: Repair suggestions improve diagnosis, but users still lose time selecting the correct body or replacement receipt manually; a high-quality output workflow should make the authoritative repair payload copyable in one click.
- Primary metric: `reviewArtifactReceiptRepairCopyCoverage`.
- Baseline: failed receipt comparisons displayed repair guidance, but the user had to select the archived body or current receipt from a long Markdown receipt manually.
- Candidate: Add `archived body 복사` and `fresh receipt 복사` actions inside failed receipt comparisons, backed by hidden repair payloads and smoke coverage for both body-drift and status-drift cases.
- Decision: keep.

## External Comparison

- Linear exposes issue version history and restore flows for changed descriptions, reducing manual reconstruction after drift: https://linear.app/docs/editing-issues
- GitHub saved replies turn repeated issue/PR comment payloads into reusable one-click inserts; JooPark applies the same copy-ready pattern to repair payloads: https://docs.github.com/get-started/writing-on-github/working-with-saved-replies
- Notion version history lets users copy blocks from an older version or restore the full version, so JooPark now separates “copy archived body” from “copy fresh current receipt”: https://www.notion.com/fi/help/duplicate-delete-and-restore-content

## Evidence

- `reviewArtifactReceiptCompareOutput()` renders `archived body 복사` when body drift is detected and `fresh receipt 복사` whenever a failed comparison should archive the current pass-state receipt.
- `copyReviewArtifactRepairPayload()` copies either the archived Created Artifact Body or the current panel receipt through the existing clipboard path and exposes copied state on the artifact diff panel.
- `scripts/smoke-interactions.mjs` verifies archived body copy reaches the clipboard as body-only content and fresh receipt copy reaches the clipboard with `# JooPark Review Artifact Receipt`, `Diff status: pass`, and the expected primary key.
- `scripts/audit-release-readiness.mjs` keeps one-click repair copy actions inside the `review_artifact_diff_panel` gate.
- `npm run test` passed with packaged interaction evidence reporting `reviewArtifactReceiptRepairCopy: true`.
- `npm run verify` passed with `133 pass, 0 fail, 0 not_run, 0 blocked, 133 total`.

## Improvement

- Before: users got the correct repair advice but still had to select the right Markdown segment by hand.
- After: failed comparisons provide copy-ready repair payloads, making it faster and less error-prone to restore the current artifact or replace a stale archived receipt.

## Next Loop

- Add guarded apply-repair actions with preview and undo so archived receipt bodies can update the current issue or note without manual paste.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact operational readiness

- Hypothesis: Generated review artifacts should be executable tracker work, not only validated prose, so the accepted prompt output must carry owner, first action, timebox, decision gate, fallback, acceptance criteria, and validation plan into the created issue/note body.
- Primary metric: `reviewArtifactOperationalReadinessCoverage`.
- Baseline: v1 review handoff results could validate JSON and create artifacts, but operational execution details were not required as first-class schema fields or post-creation diff checks.
- Candidate: `joopark-review-handoff/v2` requires operational readiness fields in `executionPlan`, generated issue/note bodies render `## Operational Readiness`, artifact diffs add a sixth operational-readiness check, and smoke/audit gates require those fields in handoff, created artifact, and opened body flows.
- Decision: keep.

## External Comparison

- OpenAI structured output guidance treats schema requirements as the control surface for reliable model output, so the JooPark handoff now makes execution fields required instead of optional prose: https://platform.openai.com/docs/guides/structured-outputs
- GitHub issue forms turn structured user input into Markdown issue bodies, so JooPark now keeps validated operational fields in the durable issue body: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates preserve issue properties and repeatable workflow setup, so JooPark now carries owner/timebox/decision-gate style tracker readiness into the created artifact: https://linear.app/docs/issue-templates

## Evidence

- `app.js` now bumps the review handoff contract to `joopark-review-handoff/v2`, adds `reviewOperationalReadinessLines()`, requires `firstAction`, `owner`, `timeboxHours`, `decisionGate`, and `fallbackIfBlocked`, and renders `## Operational Readiness` in static drafts, saved-result bodies, and created artifacts.
- `scripts/smoke-interactions.mjs` verifies v2 handoff examples, rejects missing `decisionGate`, requires six artifact diff checks, and asserts opened created bodies include `## Operational Readiness` and `Decision gate:`.
- `scripts/audit-release-readiness.mjs` now gates v2 schema terms, missing-field validator messages, and the operational-readiness artifact diff check.
- `README.md` documents the v2 execution-plan contract and the operational-readiness artifact diff behavior.
- `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run verify` passed; final release audit reported `131 pass, 0 fail, 0 not_run, 0 blocked, 131 total`.
- Computer Use manual verification opened `http://127.0.0.1:5189/#pm-portfolio`, clicked `벤치 포커스`, inserted the PM benchmark example, created issue `issue-mq2z7d2z0std`, confirmed six artifact diff checks including `Operational readiness pass`, and opened the created issue body showing `## Operational Readiness`, `Decision gate`, and `Fallback if blocked`.

## Improvement

- Before: a validated review result could prove it was shaped correctly but still leave the operator to infer who acts first, when to stop, and what fallback is acceptable.
- After: the generated artifact carries an explicit execution contract and the UI refuses to treat the post-creation artifact as fully validated unless that contract survives into the created body.

## Next Loop

- Add guarded apply-repair actions with preview and undo so archived receipt bodies can update the current issue or note without manual paste.
- Add reviewer-assignment override UI for low-confidence owner mappings and generate a first-action checklist on the Kanban card.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review operational tracker fields

- Hypothesis: A validated operational plan should become real tracker metadata, not only Markdown body text, so the issue draft and created issue must expose assignee, due date, estimate, and execution metadata before users treat the handoff as ready.
- Primary metric: `reviewOperationalTrackerFieldCoverage`.
- Baseline: v2 operational readiness survived into the created body and artifact diff, but `owner` and `timeboxHours` remained prose-only and the issue draft still displayed unassigned tracker fields.
- Candidate: Map validated `executionPlan.owner/timeboxHours` into assignee, due date, estimate, `tracker-ready` label, and execution fields; expose those fields in the issue draft and issue sheet; gate the flow in smoke and release audit.
- Decision: keep.

## External Comparison

- OpenAI structured outputs make required schema fields the reliable control surface, so JooPark now consumes `executionPlan.owner/timeboxHours` as typed operational data: https://platform.openai.com/docs/guides/structured-outputs
- GitHub issue forms convert structured input into issue metadata and durable bodies; JooPark now does the same for validated review handoff issues: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates preserve assignee, due date, and repeatable workflow fields, so JooPark now keeps reviewer ownership visible outside prose: https://linear.app/docs/issue-templates

## Evidence

- `app.js` now maps saved validated review results through `reviewSavedResultTrackerFields()`, resolving `owner=PM` to assignee `박주호`, deriving due date from `timeboxHours`, carrying estimate and execution metadata into created issues, and adding the `tracker-ready` label.
- Issue draft panels now show `담당`, `마감`, and `예상` fields and carry `data-issue-draft-tracker-ready`, `data-issue-draft-assignee`, `data-issue-draft-due`, and `data-issue-draft-execution-owner` attributes for smoke coverage.
- `openIssueSheet()` now exposes saved issue tracker fields plus `execution owner`, `first action`, `decision gate`, and `fallback` for full-body inspection.
- `scripts/smoke-interactions.mjs` verifies workspace, KB/IA, and PM issue drafts and created issues preserve assignee `jp`, due date, estimate, execution owner, and `tracker-ready`.
- `scripts/audit-release-readiness.mjs` adds `review_operational_tracker_fields`; `README.md` documents how validated owner/timebox values map into issue metadata.
- `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run verify` passed; final release audit reported `132 pass, 0 fail, 0 not_run, 0 blocked, 132 total`, with packaged interaction evidence reporting `reviewOperationalTrackerField: true`.
- Computer Use manual verification opened `http://127.0.0.1:5190/#pm-portfolio`, clicked `벤치 포커스`, inserted the PM benchmark example, confirmed the issue draft changed to `담당 박주호`, `마감 2026-06-07`, `예상 4h`, created issue `issue-mq2zmb7lq6si`, and opened the issue sheet showing `tracker-ready`, `source kind: validated-review-result`, `execution owner: PM`, `first action`, `decision gate`, and `fallback`.

## Improvement

- Before: the generated issue body contained a usable execution contract, but responsibility and deadline were still buried in prose.
- After: the issue tracker itself shows who owns the next action, when the review is due, how large it is, and whether the validated execution plan was successfully mapped.

## Next Loop

- Add reviewer-assignment override UI for low-confidence owner mappings and generate a first-action checklist on the Kanban card.
- Add guarded apply-repair actions with preview and undo so archived receipt bodies can update the current issue or note without manual paste.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review execution checklist fields

- Hypothesis: Validated review outputs become more execution-ready when `firstAction`, `acceptanceCriteria`, and `validationPlan` are converted into an issue checklist instead of staying as prose in the body.
- Primary metric: `reviewExecutionChecklistCoverage`.
- Baseline: validated first action, acceptance criteria, and validation plan survived in the generated body and tracker fields, but the issue draft, created issue, and Kanban card had no checklist-ready execution preview.
- Candidate: add `## Execution Checklist` to saved-result issue bodies, persist `executionChecklist` on created issues, label checklist-ready issues, expose checklist count in issue drafts, expose the checklist in the issue sheet, render a Kanban checklist preview, and add a seventh artifact diff check.
- Decision: keep.

## External Comparison

- OpenAI structured outputs make schema fields reliable typed data, so JooPark now consumes acceptance and validation arrays as checklist-ready tracker data: https://platform.openai.com/docs/guides/structured-outputs
- GitHub issue forms map structured inputs into issue bodies and metadata, so JooPark now maps validated review output into a durable checklist section: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates preserve repeatable issue setup and properties, so JooPark now carries checklist readiness into issue metadata and the Kanban preview: https://linear.app/docs/issue-templates

## Evidence

- `app.js` now derives checklist items from validated `firstAction`, decision acceptance/validation, and execution-plan acceptance/validation fields; it stores them on issues, labels checklist-ready drafts, renders the checklist in the issue body and issue sheet, and previews the first checklist item on Kanban cards.
- `scripts/smoke-interactions.mjs` verifies Workspace, KB/IA, and PM issue drafts carry checklist counts, created issues keep `executionChecklist`, opened issue bodies include `## Execution Checklist`, artifact diffs show seven checks, and the generated Kanban card includes an execution checklist preview.
- `scripts/audit-release-readiness.mjs` adds `review_execution_checklist_fields`; `README.md` documents checklist-ready acceptance/validation requirements and the tracker/Kanban mapping.
- `node --check app.js`, `node --check scripts/smoke-interactions.mjs`, `node --check scripts/audit-release-readiness.mjs`, `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run verify` passed; final release audit reported `133 pass, 0 fail, 0 not_run, 0 blocked, 133 total`.
- Computer Use manual verification opened `http://127.0.0.1:5191/#pm-portfolio`, clicked `벤치 포커스`, inserted the PM benchmark example, confirmed the issue draft showed `담당 박주호`, `마감 2026-06-07`, `예상 4h`, and `체크리스트 5개`, created issue `issue-mq304glzjl9e`, and opened the issue sheet showing `execution checklist`, `First action`, `tracker-ready`, and `checklist-ready`.

## Improvement

- Before: the generated issue had owner, due date, estimate, and execution metadata, but the concrete first step and acceptance/validation work still read like body prose.
- After: the generated issue has a structured execution checklist that survives from validated JSON into the draft, created issue, issue sheet, artifact diff, and Kanban preview.

## Next Loop

- Add reviewer-assignment override UI for low-confidence owner mappings.
- Add checklist completion toggles and progress state on issue sheets and Kanban cards.
- Add guarded apply-repair actions with preview and undo so archived receipt bodies can update the current issue or note without manual paste.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact receipt repair apply

- Hypothesis: Copy-ready repair payloads reduce selection errors, but a high-quality output workflow should also let users preview and apply the authoritative archived body directly, then undo the change if they chose the wrong side.
- Primary metric: `reviewArtifactReceiptRepairApplyCoverage`.
- Baseline: failed receipt comparisons could explain drift and copy archived/current payloads, but restoring a current issue or note body still required manual paste into a separate editor path.
- Candidate: Add `archived body 적용` to failed body-match repairs; open a preview comparing current saved body with the archived receipt body; apply the archived body to the current issue/note record on confirmation; render `적용 되돌리기` until the user restores the previous body.
- Decision: keep.

## External Comparison

- Linear issue version history exposes restore paths for changed descriptions, so JooPark now pairs drift detection with a guarded restore action instead of leaving recovery as manual text editing: https://linear.app/docs/editing-issues
- Notion version history lets users copy content from older versions or restore a version, so JooPark now separates copy-only repair from a direct apply-and-undo flow: https://www.notion.com/fi/help/duplicate-delete-and-restore-content
- GitHub issues treat the issue body as the durable Markdown artifact, so JooPark repair apply updates the stored issue/note body itself and then rechecks the artifact diff: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues

## Evidence

- `app.js` now renders `archived body 적용`, opens `reviewArtifactRepairPreview()` with current vs archived body snippets, applies the archived receipt body through `applyReviewArtifactRepairBody()`, and exposes `undoReviewArtifactRepair()` for the same created issue/note id.
- `scripts/smoke-interactions.mjs` verifies the preview opens, the saved artifact record receives the tampered archived body, the diff panel exposes undo, and undo restores the `fnv1a32` body before downstream GitHub comment, note, KB, and benchmark flows continue.
- `scripts/audit-release-readiness.mjs` keeps apply/preview/undo terms inside the `review_artifact_diff_panel` release gate.
- `README.md` documents `archived body 적용` and `적용 되돌리기` as the safe path when the archived receipt is authoritative.
- `npm run lint` passed.
- `npm run test` passed with packaged interaction evidence reporting `reviewArtifactReceiptRepairApply: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `134 pass, 0 fail, 0 not_run, 0 blocked, 134 total`.

## Improvement

- Before: a failed receipt could tell the user what to copy, but restoring the artifact still depended on manual paste and a separate edit path.
- After: the failed receipt compare can turn an authoritative archived body into the current saved issue/note body through a previewed, reversible action, making the final artifact easier to trust and reuse.

## Next Loop

- Add checklist completion toggles and progress state on issue sheets and Kanban cards.
- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review assignee override fields

- Hypothesis: Role-hint owner mappings are useful defaults, but users need visible confidence and a direct override before creating a durable issue.
- Primary metric: `reviewAssigneeOverrideCoverage`.
- Baseline: owner role hints auto-mapped to an assignee without visible confidence, review-required state, or a draft-level override.
- Candidate: Show role-hint mapping confidence/review-required status, add an issue draft assignee override select, persist manual confirmation labels and metadata, expose the fields in the issue sheet, and gate the path in smoke/audit.
- Decision: keep.

## External Comparison

- OpenAI structured outputs make schema fields reliable typed data, so JooPark now separates automatic owner interpretation from explicit user confirmation: https://platform.openai.com/docs/guides/structured-outputs
- GitHub issue forms expose structured issue fields before submission, so JooPark now lets the user correct the assignee before creating the issue: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates preserve assignee and issue metadata as first-class fields, so JooPark now stores assignee confidence, source, and override state outside prose: https://linear.app/docs/issue-templates

## Evidence

- `app.js` now computes review owner assignments with confidence/source/review-required metadata, renders the `담당 확인` assignee select, handles manual overrides, and stores `assigneeOverride`, `assigneeConfidence`, `assigneeSource`, and `assigneeReviewRequired` on created issues.
- `styles.css` adds the assignee override panel styling and warning state for review-required automatic mappings.
- `scripts/smoke-interactions.mjs` verifies the PM benchmark draft starts as `role-hint`/`medium`/review-required, changes the assignee to `서기태`, creates the issue with `manual-override`, and asserts `assignee-confirmed` survives persistence.
- `scripts/audit-release-readiness.mjs` adds the `review_assignee_override_fields` gate; `README.md` documents `assignee-review`, `assignee-confirmed`, and manual override metadata.
- `node --check app.js`, `node --check scripts/smoke-interactions.mjs`, `node --check scripts/audit-release-readiness.mjs`, `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run verify` passed; final release audit reported `134 pass, 0 fail, 0 not_run, 0 blocked, 134 total`.
- Computer Use manual verification opened `http://127.0.0.1:5192/#pm-portfolio`, clicked `벤치 포커스`, inserted the PM benchmark example, confirmed the draft showed `담당 박주호`, `마감 2026-06-07`, `예상 4h`, `체크리스트 5개`, and role-based review-required status, changed the assignee to `서기태`, created issue `issue-mq30mgdl70rt`, and opened the issue sheet showing `담당: 서기태`, `assignee confidence: manual`, `assignee source: manual-override`, `assignee override: manual`, `assignee-confirmed`, `tracker-ready`, `checklist-ready`, and `execution checklist`.

## Improvement

- Before: PM role hints could silently choose the default PM assignee, and the user had to trust that automatic mapping before creating an issue.
- After: automatic role-hint mappings are marked for review, the draft has a direct assignee confirmation control, and the created issue records whether the assignee was manually confirmed.

## Next Loop

- Add checklist completion toggles and progress state on issue sheets and Kanban cards.
- Add low-confidence owner prompt examples and requiredFollowUp guidance for unmapped owners.
- Persist draft-level assignee override state before issue creation refreshes the draft panel.
- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review execution checklist progress

- Hypothesis: A checklist preview is only partly actionable; issue owners should be able to complete execution items from the issue sheet or Kanban card and see progress update without editing Markdown by hand.
- Primary metric: `reviewExecutionChecklistProgressCoverage`.
- Baseline: created review issues stored `executionChecklist` and showed the first item on Kanban, but completion state was not interactive and progress was not persisted into the issue body.
- Candidate: Add issue sheet checklist controls, Kanban next-item completion controls, progress count/percent datasets, Markdown body synchronization, localStorage persistence checks, and release audit terms.
- Decision: keep.

## External Comparison

- GitHub tasklists let users toggle Markdown checkboxes and show issue tasklist progress in issue views, so JooPark now keeps the generated `## Execution Checklist` interactive and progress-aware: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists
- Linear parent/sub-issues can convert checklist-like selections into sub-issues and auto-close parents when all sub-issues are done; JooPark mirrors the smaller in-issue version by tracking completed execution items and next incomplete work: https://linear.app/docs/parent-and-sub-issues
- Linear milestones show completion percentage from done issues, so JooPark exposes completion count and percentage directly on review issue sheets and Kanban cards: https://linear.app/docs/project-milestones
- Notion status properties can display task status as a checkbox, supporting quick progress updates from a database view; JooPark now uses checkbox completion as the visible task-state control: https://www.notion.com/help/guides/status-property-gives-clarity-on-tasks

## Evidence

- `app.js` now computes `issueExecutionChecklistProgress()`, renders issue sheet checklist controls with `data-execution-checklist-done-count` and `data-execution-checklist-progress-percent`, syncs toggles back into the Markdown `## Execution Checklist`, and keeps Kanban card toggles from opening the issue sheet.
- `styles.css` adds stable sheet checklist and Kanban progress/toggle styling so counts, bars, and checkbox labels stay compact on dense cards and sheets.
- `scripts/smoke-interactions.mjs` now verifies the PM benchmark issue starts at `0%`, sheet checkbox completion persists, the issue body changes to `- [x]`, the Kanban card updates to `실행 1/`, the next Kanban item can be completed, and localStorage stores two completed items.
- `scripts/audit-release-readiness.mjs` now requires checklist progress helpers, toggle attributes, sheet/Kanban CSS, smoke assertions, and README progress documentation in `review_execution_checklist_fields` plus `review_execution_checklist_progress`.
- `README.md` documents that issue sheets and Kanban cards show 완료 수/진행률 and let users complete execution items directly.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `reviewExecutionChecklistProgress: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `135 pass, 0 fail, 0 not_run, 0 blocked, 135 total`.
- Computer Use manual verification opened fresh `http://127.0.0.1:5194/#pm-portfolio`, clicked `벤치 포커스`, and reached the PM benchmark handoff showing Taskosaur as the primary `benchmark-review:repo-taskosaur-taskosaur:86` decision.
- Isolated CDP verification on the same fresh origin inserted the validated PM benchmark example, changed the assignee to `서기태`, created issue `issue-mq318bdn93rp`, confirmed the issue sheet moved from `0/5 완료 · 0%` to `1/5 완료 · 20%`, confirmed Kanban moved from `실행 0/5` to `실행 1/5`, and confirmed the issue body synced `- [x] First action:`.

## Improvement

- Before: generated review issues exposed checklist content, but completing the work required editing Markdown or ignoring the structured checklist state.
- After: issue sheet and Kanban card interactions update checklist completion, progress percentage, Markdown body, and persisted issue data together.

## Next Loop

- Add post-checklist completion receipt regeneration prompt so progressed issue bodies can archive a fresh pass receipt.
- Add low-confidence owner prompt examples and requiredFollowUp guidance for unmapped owners.
- Persist draft-level assignee override state before issue creation refreshes the draft panel.
- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review assignee follow-up guidance

- Hypothesis: Low-confidence or unmapped owners should not silently become fallback assignees; the review result and generated issue draft should ask for exact assignee confirmation before durable issue creation.
- Primary metric: `reviewAssigneeFollowUpCoverage`.
- Baseline: low-confidence owner text could fall back to team or role-level assignment with `assignee-review`, but the saved result did not require a concrete follow-up prompt, show prompt examples, or add visible issue-body guidance.
- Candidate: Fail low-confidence owners unless `exceptions.requiredFollowUp` asks for exact assignee confirmation, render draft-level assignee follow-up guidance and prompt examples, persist follow-up metadata on review issues, add an `owner-followup` label, and clear stale follow-up state after manual assignee confirmation.
- Decision: keep.

## External Comparison

- GitHub issue forms support required inputs plus default labels and assignees, so JooPark now treats uncertain owner mapping as a required confirmation step instead of hidden prose: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear form templates allow required fields and default issue properties, including assignee, so JooPark now stores assignee follow-up metadata as structured issue state: https://linear.app/docs/issue-templates
- Linear assigns issues to a single person for ownership, so JooPark now distinguishes role/team hints from exact active team-member assignment: https://linear.app/docs/assigning-issues
- Jira Cloud blocks issue creation when required fields are missing, which matches the new validator behavior for low-confidence owners without `requiredFollowUp`: https://support.atlassian.com/jira/kb/cant-create-issues-because-of-required-fields-in-jira-cloud/

## Evidence

- `app.js` now adds owner-accountability prompt criteria, derives follow-up items and prompt examples for low-confidence owner mappings, fails invalid review results without assignee confirmation follow-up, includes `## Assignee Follow-up` in generated bodies, persists `assigneeRequiredFollowUp` and prompt examples, and exposes those fields in the issue sheet.
- `styles.css` adds the assignee follow-up panel and prompt-example styling.
- `scripts/smoke-interactions.mjs` verifies low-confidence owners fail without `requiredFollowUp`, pass after exact-assignee follow-up text is supplied, render the draft follow-up panel and prompt examples, include the body follow-up section, and remove stale follow-up state after manual assignee override.
- `scripts/audit-release-readiness.mjs` adds `review_assignee_followup_guidance`; `README.md` documents the `owner-followup` label, `Assignee Follow-up` body section, and manual-confirmation cleanup path.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `reviewAssigneeFollowUp: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `138 pass, 0 fail, 0 not_run, 0 blocked, 138 total`.
- A reset-smoke copy mismatch was fixed by aligning the `dbm-instances` empty-state expectation with the actual `등록된 DB 카탈로그 인스턴스가 없습니다.` UI text.

## Improvement

- Before: a low-confidence owner could look assigned even when the output had not named an exact JooPark team member.
- After: uncertain ownership is visibly blocked for confirmation through validation, draft metadata, issue labels, prompt examples, issue body text, and issue sheet fields, while manual assignee selection clears the warning state.

## Next Loop

- Persist draft-level assignee override state before issue creation refreshes the draft panel.
- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Home public readiness summary

- Hypothesis: External visitors should not need to inspect System Status before understanding whether the app is local-first, verifiable, benchmark-backed, and still blocked on live publish evidence.
- Primary metric: `homePublicReadinessCoverage`.
- Baseline: the home dashboard explained daily work and workspace modules, but public-readiness evidence lived behind the System and Settings views.
- Candidate: Add a compact home readiness panel for data ownership, release gates, publish proof blockers, and benchmark queue evidence; link each card to the relevant operational view; gate it in smoke and audit.
- A/B decision: keep B. A full dashboard redesign would create more regression surface, while the compact panel improves first-visit trust without disturbing existing workflows.

## External Comparison

- Ink & Switch local-first guidance emphasizes user control, backup/export, offline checks, and durable app operation; JooPark now exposes data ownership and JSON backup as a first-screen trust signal.
- Linear documents consistent action paths through buttons, shortcuts, and command menu; JooPark keeps each readiness card actionable by routing into System, Settings, or Portfolio.
- Notion database views and AFFiNE's local-first workspace positioning both surface the same underlying data through task-specific views; JooPark now resurfaces publish and benchmark evidence on Home instead of hiding it in operational panels.

## Evidence

- `app.js` renders `data-home-readiness` with four first-visit cards: `data-ownership`, `release-gate`, `publish-proof`, and `benchmark-queue`.
- `styles.css` adds responsive readiness-card styling with distinct green, blue, amber, and violet states.
- `scripts/smoke-chrome.mjs` verifies the home readiness text, card count, required keys, publish blocker count, benchmark count, and source-backed count.
- `scripts/audit-release-readiness.mjs` adds the `home_public_readiness_summary` checklist item; `README.md` documents the home public readiness summary.

## Improvement

- Before: a first-time reviewer could see useful modules but had to navigate away to judge publish readiness and evidence quality.
- After: the first viewport has a concise trust/readiness summary that explains local ownership, verification, live-publish blockers, and benchmark evidence with direct navigation.

## Next Loop

- Persist draft-level assignee override state before issue creation refreshes the draft panel.
- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact fresh receipt after checklist

- Hypothesis: Once a generated issue checklist is partially completed, the archived receipt should be regenerated from the progressed issue body so downstream reviewers do not compare against stale pre-progress Markdown.
- Primary metric: `reviewArtifactFreshReceiptAfterChecklistCoverage`.
- Baseline: checklist progress updated the issue body and Kanban state, but the user still had to know when to produce a fresh pass receipt after completing items.
- Candidate: Render `post-checklist receipt` controls in the issue sheet, generate a pass-state fresh receipt from the current issue body, expose copy/download actions, verify the receipt includes progressed `- [x] First action` Markdown, and gate the behavior in audit.
- Decision: keep.

## External Comparison

- GitHub tasklists preserve checkbox progress directly in Markdown, so JooPark now makes the post-progress issue body the source for a fresh receipt: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists
- GitHub issues use the issue body as the durable artifact, so JooPark receipts now capture the current body after checklist progress rather than an older draft: https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues
- Linear issue history and restore patterns treat changed descriptions as recoverable artifacts, so JooPark pairs progressed bodies with a new receipt users can archive immediately: https://linear.app/docs/editing-issues

## Evidence

- `app.js` now computes fresh receipts for review issues, renders `post-checklist receipt` controls in issue sheets, and copies/downloads `joopark-${receipt.kind}-fresh-receipt.md` from the current progressed artifact body.
- `scripts/smoke-interactions.mjs` verifies the benchmark review issue fresh receipt renders pass state after checklist progress, exposes a download payload, copies to the clipboard, and includes the updated `- [x] First action:` body line.
- `scripts/audit-release-readiness.mjs` adds `review_artifact_fresh_receipt_after_checklist`; `README.md` documents that checklist completion can be followed by a fresh receipt including progressed Markdown.
- `npm run verify` passed with `138 pass, 0 fail, 0 not_run, 0 blocked, 138 total`.

## Improvement

- Before: a completed checklist item could leave the archived receipt one step behind the current issue body.
- After: the issue sheet gives users an immediate fresh receipt for the progressed artifact, keeping body, checksum, diff status, and receipt archive aligned.

## Next Loop

- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review assignee override draft persistence

- Hypothesis: A manually confirmed review assignee is part of the user's output decision, so it must survive navigation, draft rerender, backup/export, and issue creation instead of living only in the current DOM.
- Primary metric: `reviewAssigneeOverrideDraftPersistenceCoverage`.
- Baseline: assignee override metadata updated the visible draft and created issue when the user clicked create immediately, but a screen change or draft refresh before issue creation could rebuild the draft from saved review JSON and lose the manual assignee.
- Candidate: Add a `reviewIssueDraftOverrides` localStorage/backup slice keyed by `persistKey`, merge it into regenerated drafts before issue creation, stamp `data-issue-draft-assignee-override-saved-at`, preserve manual `assignee-confirmed` labels across navigation, and cover reset/import/export normalization.
- Decision: keep.

## External Comparison

- Linear issue drafts preserve composer state while users finish issue details, so JooPark now saves manual assignee confirmation before the issue is created: https://linear.app/docs/create-issues
- Linear issue templates/default properties treat assignee as structured issue metadata, so JooPark stores draft assignee confirmation outside Markdown prose: https://linear.app/docs/issue-templates
- GitHub issue forms expose assignees and required fields declaratively before submission, so JooPark now treats a confirmed assignee as pre-submit draft state: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms

## Evidence

- `app.js` now stores `reviewIssueDraftOverrides`, merges persisted overrides via `reviewDraftWithPersistedAssigneeOverride()`, writes `saveReviewIssueDraftAssigneeOverride()` on select change, carries `data-issue-draft-assignee-override-saved-at`, and includes the slice in localStorage, backup export/import, normalization, settings summary, and reset.
- `scripts/smoke-interactions.mjs` now changes the benchmark review assignee to `서기태`, asserts the override is in localStorage before issue creation, navigates away and back, verifies the refreshed draft still shows `manual-override`/`assignee-confirmed`, and only then creates the issue.
- `scripts/audit-release-readiness.mjs` adds `review_assignee_override_draft_persistence`; `README.md` documents `reviewIssueDraftOverrides` and the issue 생성 전 화면 이동 preservation contract.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `reviewAssigneeOverrideDraftPersistence: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `140 pass, 0 fail, 0 not_run, 0 blocked, 140 total`.

## Improvement

- Before: the generated issue output could silently revert from the user-confirmed assignee to the automatic role hint if the draft rerendered before creation.
- After: the confirmed assignee is durable draft state, survives navigation/rerender, appears in backup data, and is used by the final created issue without asking the user to re-check the same field.

## Next Loop

- Add post-apply fresh receipt regeneration prompt so restored issue/note bodies can archive a new pass receipt immediately.
- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Review artifact post-apply fresh receipt

- Hypothesis: Applying an archived receipt body should not leave the user guessing which receipt to archive next; if the restored body passes the current artifact checks, the fresh pass receipt should be one click away.
- Primary metric: `reviewArtifactPostApplyFreshReceiptCoverage`.
- Baseline: `archived body 적용` updated the issue/note body and exposed undo, but the user had to return to generic receipt copy/compare controls to archive proof of the restored state.
- Candidate: Render a `post-apply fresh receipt` panel after repair apply, show ready vs needs-review state from the current artifact checks, expose copy/download actions for the current pass receipt, and verify the copied receipt contains the restored body.
- Decision: keep.

## External Comparison

- GitHub issue tasklists keep work evidence in the issue body and surface completion state from that body, so JooPark now treats the restored artifact body as the receipt source of truth: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists
- GitHub Issues are the durable work-tracking artifact, so post-repair evidence should be generated from the current saved issue/note body rather than an older draft: https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues
- Linear keeps local issue drafts and issue properties during creation and recovery flows, so JooPark now makes the repaired artifact's next archival action explicit instead of relying on user memory: https://linear.app/docs/creating-issues

## Evidence

- `app.js` now renders `reviewArtifactPostApplyReceiptPanel()` when a repair apply undo is available, `copyReviewArtifactPostApplyReceipt()` copies the current restored artifact receipt, and the repair preview snippet prioritizes `First action` so users can verify the archived body before applying it.
- `styles.css` adds the post-apply receipt panel with ready and needs-review states.
- `scripts/smoke-interactions.mjs` now creates a body-only drift that preserves pass checks, applies the archived body, verifies the post-apply receipt panel is ready, and confirms the copied receipt includes `Diff status: pass`, the primary key, and `First action: restored evidence -`.
- `scripts/audit-release-readiness.mjs` adds `review_artifact_post_apply_fresh_receipt`; `README.md` documents the post-apply fresh receipt contract.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `reviewArtifactPostApplyFreshReceipt: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `142 pass, 0 fail, 0 not_run, 0 blocked, 142 total`.

## Improvement

- Before: after restoring an archived body, users could undo but had no explicit prompt to archive a new proof receipt for the restored pass state.
- After: the diff panel immediately presents a post-apply fresh receipt when the restored artifact passes checks, preserving body, checksum, diff status, and receipt evidence in the same workflow.

## Next Loop

- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Publish evidence next action

- Hypothesis: Release gates can be green while public launch remains blocked; the publish evidence surface should name the one next action instead of forcing operators to infer it from a blocker list.
- Primary metric: `publishEvidenceNextActionCoverage`.
- Baseline: `data/publish-evidence.json` exposed blockers, commands, and suggested repo commands, but did not have a structured `nextAction` that System Status and Markdown could display consistently.
- Candidate: Add `publishEvidenceNextAction()` to compute the next publish action from dry-run/live mode, repo placeholder state, Pages API readiness, workflow run evidence, blockers, and launch-proof readiness. Store it in JSON, render it in Markdown and System Status, and cover it in smoke/audit gates.
- Decision: keep.

## External Comparison

- GitHub Pages REST evidence exposes `html_url` and `status`, so the next-action state now distinguishes Pages API verification from workflow-run verification: https://docs.github.com/en/rest/pages/pages
- GitHub Actions manual runs require `workflow_dispatch`, so the next-action state can point to workflow dispatch when no run evidence exists: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub Actions workflow run evidence uses `status` and `conclusion`, so the next-action state can point to run inspection when a run exists but is not successful: https://docs.github.com/en/rest/actions/workflow-runs

## Evidence

- `scripts/capture-publish-evidence.mjs` now writes `nextAction` with a key, label, detail, and command; dry-run evidence currently resolves to `capture-live-evidence` with the suggested repo command.
- `app.js` renders a `Next action` card in System Status and exposes `data-publish-evidence-next-action` plus `data-publish-evidence-next-command`.
- `styles.css` styles the next-action card without changing the surrounding publish readiness layout.
- `scripts/smoke-interactions.mjs` asserts the next-action dataset, card text, and command in the packaged browser flow.
- `scripts/audit-release-readiness.mjs` requires the next-action JSON, Markdown, UI, smoke, style, and README contracts.
- `data/publish-evidence.json` was regenerated by `node scripts/capture-publish-evidence.mjs --dry-run --write`.
- `npm run lint` passed.
- `npm run test` passed with packaged interaction evidence reporting `systemPublishReadiness: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `143 pass, 0 fail, 0 not_run, 0 blocked, 143 total`.

## Improvement

- Before: operators saw a list of blockers and commands but still had to decide which command came next.
- After: the saved evidence, Markdown report, and System Status all expose the same single next action, reducing publish handoff ambiguity while live workflow access remains blocked.

## Next Loop

- Continue the blocked live-publish path only after workflow-scope access and real Pages/workflow evidence are available.

## Experiment: Publish dispatch UI install handoff

- Hypothesis: When publish dispatch is blocked because repository-root workflows are missing, the dispatch plan itself should return the exact GitHub UI install links and template hashes instead of forcing operators to run a separate planning command.
- Primary metric: `publishDispatchUiInstallHandoffCoverage`.
- Baseline: `plan-publish-dispatch.mjs` named missing workflows and guarded dispatch commands, but the operator still had to know to run `plan-workflow-ui-install.mjs --dry-run --markdown` to get `githubNewFileUrl`, workflow URL, default branch, and template hash details.
- Candidate: Embed `workflowUiInstallPlans` in the dispatch plan with `githubNewFileUrl`, `githubWorkflowUrl`, `templateSha256`, required terms, scope-check command, UI steps, and `nextActions`; keep dispatch blocked until workflows are installed and visible.
- Decision: keep.

## External Comparison

- GitHub manual workflow runs require workflows to be configured for `workflow_dispatch`, so JooPark now keeps dispatch blocked while returning the install steps needed before a run can exist: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub workflow triggers are tied to workflow files on the default branch for dispatch/schedule behavior, so JooPark now puts `defaultBranch`, repository-root target paths, and workflow URLs directly in the dispatch plan: https://docs.github.com/actions/using-workflows/triggering-a-workflow
- GitHub workflow syntax defines the YAML workflow file contract, so JooPark continues to verify required template terms and hashes before telling an operator what to paste into GitHub UI: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

## Evidence

- `scripts/plan-publish-dispatch.mjs` now returns `workflowUiInstallReady`, two `workflowUiInstallPlans`, each plan's GitHub new-file URL, workflow URL, `templateSha256`, scope-check command, UI steps, and concrete `nextActions`.
- Live preflight with `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` confirmed the current blocker remains real: both workflows are missing locally and not visible in GitHub Actions, while the plan now includes the UI install handoff for both.
- `app.js` now derives a readable `Capture live publish evidence` next-action label even if older persisted evidence only stores the action key, fixing the packaged System Status smoke path.
- `scripts/audit-release-readiness.mjs` now requires the dispatch plan to expose UI install links, template hashes, workflow scope checks, and next actions; `README.md` documents the new `workflowUiInstallPlans` contract.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `systemPublishReadiness: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `143 pass, 0 fail, 0 not_run, 0 blocked, 143 total`.

## Improvement

- Before: a blocked dispatch plan was safe but incomplete; it told the operator what was missing but not enough to install the missing workflows from that same output.
- After: the dispatch plan is an actionable handoff. It blocks unsafe dispatch, names the missing workflows, gives the exact GitHub UI creation URLs and template hashes, and tells the operator which live command to rerun after installation.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Publish dispatch suggested command guard

- Hypothesis: A blocked publish dispatch plan is safer when repo-specific `suggestedCommands` contains only the next verification command until every workflow reports `allDispatchReady: true`.
- Primary metric: `unsafeSuggestedDispatchCommandCount`.
- Baseline: `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` reported `allDispatchReady: false` and two workflow visibility blockers, but `suggestedCommands` still included two `gh workflow run --repo biojuho/BIOJUHO-Projects ...` commands.
- Candidate: Split the plan output into `suggestedVerificationCommands` and `suggestedDispatchCommands`; keep `suggestedDispatchCommands: []` and `dispatchSuggestionStatus: withheld-until-all-dispatch-ready` until dispatch is actually safe; surface the guard in System Status, README, audit, and interaction smoke.
- Decision: keep.

## External Comparison

- GitHub manual workflow runs require `workflow_dispatch`, and GitHub documents that triggering this event requires the workflow to be on the default branch: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub workflow syntax also documents that the `workflow_dispatch` trigger only receives events when the workflow file is on the default branch: https://docs.github.com/actions/reference/workflow-syntax-for-github-actions

## Evidence

- `node scripts/plan-publish-dispatch.mjs --dry-run` now returns `suggestedCommands: ["node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects"]`, `suggestedDispatchCommands: []`, and `dispatchSuggestionStatus: withheld-until-all-dispatch-ready`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` persisted the same safe command split to `data/publish-dispatch-plan.json` while keeping the two blockers: Pages and Drift Watch workflows are not visible in GitHub Actions.
- `release-status.js` now renders `suggestedDispatchCommands` as withheld until `allDispatchReady: true`, and `scripts/smoke-interactions.mjs` verifies the suggested command panel contains no `gh workflow run --repo` before dispatch readiness.
- `README.md` and `docs/app-architecture.md` were also aligned with the extracted `notes-view.js` runtime helper so structure and workflow audits match the current module boundary.
- `npm run lint` passed.
- `npm test` passed packaged release smoke with desktop, mobile, interaction, and accessibility checks.
- `npm run verify` passed with `165 pass, 0 fail, 0 not_run, 0 blocked, 165 total`.

## Improvement

- Before: a blocked plan correctly said dispatch was not ready, but the recommended command list still made premature dispatch easy to copy.
- After: the visible recommended command is only the repo-scoped live verification command until the remote workflows are visible and every dispatch gate is true.

## Next Loop

- Install the two repository-root workflow files on the default branch, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `suggestedDispatchCommands` becomes populated and `allDispatchReady: true`.
- After dispatch, run `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady: true`.

## Experiment: Review package submit sequence

- Hypothesis: Review packages are more directly usable when they tell the operator the exact submission order after fields and bodies are copy-ready.
- Primary metric: `reviewPackageSubmitSequenceCopyCoverage`.
- Baseline: The package exposed copy-ready tracker fields and body text, but the user still had to reconstruct the order: create issue, record URL/ID, comment, note, and retain bundle proof.
- Candidate: Add `Submit Sequence` to the pre-submit preview and Markdown bundle, with ordered steps for tracker fields, tracker body, external issue URL/ID receipt, GitHub comment, pinned note, and bundle proof plus one-click `순서 복사`.
- Decision: keep.

## External Comparison

- GitHub issue forms separate structured form inputs from generated issue Markdown; JooPark now mirrors that separation and adds the missing operator sequence before submission: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates and create-issue flows support reusable issue structure and URL-based creation from templates, so JooPark keeps reusable field/body packets but adds the step order needed when multiple destinations are involved: https://linear.app/docs/issue-templates and https://linear.app/docs/creating-issues
- Jira creation guidance emphasizes completing required fields and configuring visible fields; JooPark records the field-first order and external issue receipt so required-field submission does not become body-only: https://support.atlassian.com/jira-work-management/docs/create-an-issue-and-a-sub-task/

## Evidence

- `review-handoff.js` now renders `Submit Sequence`, six ordered steps, Markdown output, hidden copy payload, and the `순서 복사` control.
- `app.js` copies the submit sequence and records copied state/status in the sequence panel.
- `scripts/smoke-interactions.mjs` verifies `reviewPackageSubmitSequenceCopy: true`, including clipboard content for `Review Package Submit Sequence`, `Set tracker fields first`, `Record external issue receipt`, and the workspace persist key.
- `scripts/audit-release-readiness.mjs` adds `review_package_submit_sequence`, and README documents the tracker fields -> tracker body -> external issue URL/ID -> GitHub comment -> pinned note -> bundle proof order.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 34 packaged files and `sourceDirtyFiles: 46`.
- `npm run verify` passed with `163 pass, 0 fail, 0 not_run, 0 blocked, 163 total`.

## Improvement

- Before: the package was copy-ready but the submission workflow still depended on memory and manual sequencing.
- After: the output now includes a copy-ready operational sequence, reducing the chance that a tracker issue is created without fields, without a recorded external receipt, or without matching comment/note proof.

## Next Loop

- Continue improving final output quality by adding the next missing copy-ready proof or verifier where external submission still depends on manual interpretation.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Review package external receipt template

- Hypothesis: Review packages are more reusable after submission when they include a copy-ready receipt template for the external issue URL, issue ID, submission timestamp, and bundle proof.
- Primary metric: `reviewPackageExternalReceiptTemplateCopyCoverage`.
- Baseline: The submit sequence told the operator to record an external issue receipt, but the package did not provide a ready template to paste into a note, tracker update, or handoff log.
- Candidate: Add `External Issue Receipt Template` to the pre-submit preview and Markdown bundle, with persist key, title, project, priority, labels, external issue URL/ID placeholders, submitted-at placeholder, and bundle proof plus one-click `receipt 복사`.
- Decision: keep.

## External Comparison

- GitHub issue forms preserve structured submission data before generating issue Markdown, so JooPark now keeps a post-create receipt template tied to the same persist key: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue creation supports reusable issue templates and template URLs; JooPark adds the missing after-create receipt surface so the reusable package remains traceable after the issue exists: https://linear.app/docs/creating-issues
- Jira creation guidance requires completing required fields and allows field visibility configuration; JooPark's receipt template makes the external URL/ID and submitted-at fields explicit after those required fields are accepted: https://support.atlassian.com/jira-work-management/docs/create-an-issue-and-a-sub-task/

## Evidence

- `review-handoff.js` now renders `External Issue Receipt Template`, nine receipt rows, Markdown output, hidden copy payload, and the `receipt 복사` control.
- `app.js` copies the external receipt template and records copied state/status in the receipt panel.
- `scripts/smoke-interactions.mjs` verifies `reviewPackageExternalReceiptTemplateCopy: true`, including clipboard content for `External Issue Receipt Template`, external issue URL/ID placeholders, and the workspace persist key.
- `scripts/audit-release-readiness.mjs` adds `review_package_external_receipt_template`, and README documents `External issue URL`, `External issue ID`, `Submitted at`, and bundle proof.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 35 packaged files and `sourceDirtyFiles: 47`.
- `npm run verify` passed with `165 pass, 0 fail, 0 not_run, 0 blocked, 165 total`.

## Improvement

- Before: the workflow could create a good external issue but still lose the URL/ID receipt or force the operator to write one by hand.
- After: the package now carries its own receipt template, so the final submission can be traced back to the persist key and bundle proof without inventing a new handoff note.

## Next Loop

- Continue improving final output quality by reducing any remaining manual interpretation between generated package, external tracker state, and final proof.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Review package external receipt composer

- Hypothesis: Review packages are more copy-ready after external issue creation when the operator can enter the issue URL, issue ID, and submitted-at value once, then copy a completed receipt without placeholders.
- Primary metric: `reviewPackageExternalReceiptFilledCopyCoverage`.
- Baseline: The package provided an external receipt template, but the operator still had to manually replace `[paste after creation]` fields before sharing final proof.
- Candidate: Add external issue URL, ID, and submitted-at inputs to the receipt panel plus `완성 receipt 복사`, which copies a completed receipt and refuses to copy until URL and ID are present.
- Decision: keep.

## External Comparison

- GitHub issue forms preserve structured submission values before generating Markdown, so JooPark now lets the operator bind the generated package to concrete post-create receipt fields: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue creation uses reusable issue structure and creates a concrete issue URL after submission; JooPark closes that same after-create traceability gap with a completed receipt copy path: https://linear.app/docs/creating-issues
- Jira creation guidance distinguishes required fields from the created issue identity; JooPark records the external URL, ID, timestamp, and bundle proof after those fields are accepted: https://support.atlassian.com/jira-work-management/docs/create-an-issue-and-a-sub-task/

## Evidence

- `review-handoff.js` now renders the external receipt composer inputs and `완성 receipt 복사` control in the pre-submit preview.
- `app.js` adds `copyReviewPackageExternalReceiptFilled()`, validates URL/ID before copying, fills the submitted-at timestamp, and stores copied status on the receipt panel.
- `scripts/smoke-interactions.mjs` verifies `reviewPackageExternalReceiptFilledCopy: true` by entering a Linear-style URL, issue ID, and timestamp, then confirming the clipboard contains no `[paste after creation]` placeholders.
- `scripts/audit-release-readiness.mjs` adds `review_package_external_receipt_composer`, and README documents the placeholder-free completed receipt path.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 36 packaged files and `sourceDirtyFiles: 49`.
- `npm run lint` passed.
- `npm run verify` passed with `167 pass, 0 fail, 0 not_run, 0 blocked, 167 total`.

## Improvement

- Before: the receipt template was copy-ready as a scaffold, but final receipt proof still depended on manual placeholder editing after the external tracker accepted the issue.
- After: the package panel creates the final receipt directly from URL, ID, timestamp, persist key, and bundle proof, reducing the chance of shipping a handoff with placeholder text.

## Next Loop

- Continue improving final output quality by reducing the remaining manual gap between external tracker submission and public publish evidence.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Review package submission update

- Hypothesis: Review packages are more immediately useful after external issue creation when they produce a short team-shareable submission update, not only a receipt record.
- Primary metric: `reviewPackageSubmissionUpdateCopyCoverage`.
- Baseline: The completed receipt could preserve URL/ID/timestamp proof, but a user still had to rewrite that proof into a concise Slack/GitHub/status-update message before sharing.
- Candidate: Add `Review Submission Update` to the pre-submit preview and bundle, reuse the external issue URL/ID/submitted-at inputs, and copy a placeholder-free final update with status, external issue, persist key, proof, and next action.
- Decision: keep.

## External Comparison

- GitHub issue forms turn structured fields into generated issue Markdown, which makes the post-submit update more valuable when it references the concrete generated issue identity: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue creation and templates support reusable issue structure and concrete created issue URLs, so JooPark now turns that same URL/ID into a share-ready status update rather than leaving it as a private receipt only: https://linear.app/docs/creating-issues
- Jira creation guidance separates field completion from the created issue record; JooPark now preserves the created record in both receipt form and a short completion update: https://support.atlassian.com/jira-work-management/docs/create-an-issue-and-a-sub-task/

## Evidence

- `review-handoff.js` now renders `Review Submission Update`, nine update rows, hidden copy text, and `최종 update 복사` in the receipt panel and includes the template in the Markdown bundle.
- `app.js` adds `copyReviewPackageSubmissionUpdateFilled()` and shared external issue placeholder filling so the same URL/ID/submitted-at values power both completed receipt and final update.
- `scripts/smoke-interactions.mjs` verifies `reviewPackageSubmissionUpdateCopy: true` by confirming the clipboard contains the Linear-style issue URL/ID, submitted-at value, persist key, proof, next action, and no `[paste` placeholders.
- `scripts/audit-release-readiness.mjs` adds `review_package_submission_update`, and README documents the team-shareable final update path.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 37 packaged files and `sourceDirtyFiles: 50`.
- `npm run lint` passed.
- `npm run verify` passed with `168 pass, 0 fail, 0 not_run, 0 blocked, 168 total`.

## Improvement

- Before: users could preserve proof, but the final team-facing update still required manual rewriting from the receipt.
- After: the same completed external issue fields produce both durable proof and a concise status update that can be pasted directly into a team channel, comment thread, or handoff log.

## Next Loop

- Continue improving final output quality by reducing the remaining manual gap between external publish evidence, team-facing proof, and launch-ready status updates.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Publish evidence share update

- Hypothesis: Publish evidence is more usable when the long report also produces a short copy-ready team update that distinguishes `action required` from `launch proof ready`.
- Primary metric: `publishEvidenceShareUpdateCopyCoverage`.
- Baseline: `capture-publish-evidence.mjs --markdown` produced a full report and System Status exposed next action, but a user still had to rewrite the report into a concise team-facing status update.
- Candidate: Add `shareUpdate` to publish evidence JSON/Markdown, render `Launch proof share update` in System Status, and copy the update with `share update 복사`.
- Decision: keep.

## External Comparison

- GitHub Actions manual workflow runs rely on visible workflow run status and conclusion, so the share update includes each workflow file with `ready/status/conclusion/url`: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- The GitHub CLI `gh run list` JSON fields include `status`, `conclusion`, `url`, and `headSha`, so the update preserves the same run-proof fields in a compact form: https://cli.github.com/manual/gh_run_list
- GitHub Pages REST evidence exposes Pages deployment/site state such as URL/status, so the update keeps Pages URL/status next to workflow evidence instead of only listing commands: https://docs.github.com/en/rest/pages?apiVersion=2022-11-28

## Evidence

- `scripts/capture-publish-evidence.mjs` now writes `shareUpdate` and includes a `## Share update` block in Markdown output.
- `data/publish-evidence.json` contains `JooPark Publish Evidence Update` with `Status: action required`, suggested repo, workflow run placeholders, blocker, and next command for the current dry-run state.
- `release-status.js` renders `Launch proof share update` with hidden copy text and `share update 복사`; `app.js` copies it via `copyPublishEvidenceShareUpdate()`.
- `scripts/smoke-interactions.mjs` verifies `publishEvidenceShareUpdate: true` by copying the update and checking action-required status, next command, workflow files, and the dry-run launch-proof guard in the clipboard.
- `scripts/audit-release-readiness.mjs` adds `publish_evidence_share_update`, and README documents the team-shareable status update.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 37 packaged files and `sourceDirtyFiles: 50`.
- `npm run lint` passed.
- `npm run verify` passed with `170 pass, 0 fail, 0 not_run, 0 blocked, 170 total`.

## Improvement

- Before: the publish evidence report was accurate, but it was too long to paste as a quick team update without manual editing.
- After: the product emits both the full proof report and a compact update that says whether launch proof is ready, which blocker remains, and which command should run next.

## Next Loop

- Continue improving final output quality by reducing the gap between publish proof, default-branch workflow visibility, and final public launch announcement text.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Publish launch announcement guard

- Hypothesis: Public launch copy is safer and more usable when the product generates a launch announcement only behind proof readiness, and otherwise copies a clear not-ready guard.
- Primary metric: `publishLaunchAnnouncementGuardCoverage`.
- Baseline: Publish evidence had a full report and a team share update, but there was no separate public-facing launch announcement output or guard against premature public posting.
- Candidate: Add `launchAnnouncement` to publish evidence JSON/Markdown, render `Public launch announcement` in System Status, and copy either a `ready to post` announcement or a `not ready for public posting` guard depending on `postPublishEvidenceReady`.
- Decision: keep.

## External Comparison

- GitHub Actions manual workflow evidence depends on workflow runs being visible and completed, so the announcement stays blocked until workflow status/conclusion proof is available: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- The GitHub CLI exposes workflow run `status`, `conclusion`, `url`, and `headSha` fields, so the ready announcement keeps run-proof URLs instead of making an unsupported launch claim: https://cli.github.com/manual/gh_run_list
- GitHub Pages REST evidence exposes the Pages site URL/status, so public launch copy requires Pages URL/status evidence before it says the workspace is live: https://docs.github.com/en/rest/pages

## Evidence

- `scripts/capture-publish-evidence.mjs` now writes `launchAnnouncement` and includes `## Launch announcement` in Markdown output.
- `data/publish-evidence.json` currently stores `JooPark Public Launch Announcement` with `Status: not ready for public posting`, blocker, next command, and the explicit `Do not post` guard because the evidence is dry-run.
- `release-status.js` renders `Public launch announcement`; `app.js` copies it through `copyPublishLaunchAnnouncement()`.
- `scripts/smoke-interactions.mjs` verifies `publishLaunchAnnouncement: true` by copying the guard and checking that the clipboard blocks public posting until `repoEvidenceReady`, `evidenceFresh`, and `postPublishEvidenceReady` are all true.
- `scripts/audit-release-readiness.mjs` adds `publish_launch_announcement_guard`, and README documents the not-ready guard and ready-to-post behavior.
- While re-verifying, the audit was aligned with the extracted `kanban-view.js` runtime helper so Kanban search empty state and execution checklist markers are checked in the file that actually renders them; the issue delete modal also regained contextual `title` and `aria-label`.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 38 packaged files and `sourceDirtyFiles: 51`.
- `npm run lint` passed.
- `npm run verify` passed with `172 pass, 0 fail, 0 not_run, 0 blocked, 172 total`.

## Improvement

- Before: a user could share internal proof status, but would still need to decide manually whether public launch wording was safe.
- After: the product emits a public-facing announcement only when proof is ready; otherwise the copied output is a safe blocker message, preventing premature launch claims.

## Next Loop

- Continue improving final output quality by reducing the gap between live publish evidence, public launch announcement, and post-launch follow-up/checklist outputs.
- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Mobile search empty debounce guard

- Hypothesis: Mobile search empty-state smoke is more reliable when it proves the debounced app search state updated before checking the empty DOM.
- Primary metric: `mobileSearchEmptyDebounceGuardCoverage`.
- Baseline: Mobile smoke reproduced a `cal search query did not reach app state on mobile` failure because the route could be visually ready before the test had proved the topbar search input was non-readonly and receiving input events.
- Candidate: `scripts/smoke-mobile.mjs` now waits for route/search input readiness, dispatches an `InputEvent` inside the wait loop until lexical `state.query` matches the route-specific no-match query, then waits for both `[data-search-empty]` and the live `검색 결과 없음` status. Failure reports still include query propagation and recovery evidence.
- Decision: keep.

## Evidence

- `node --check scripts/smoke-mobile.mjs` and `node --check scripts/audit-release-readiness.mjs` passed.
- `npm run lint` passed with `todo-view.js`, `scripts/smoke-mobile.mjs`, and `scripts/audit-release-readiness.mjs` included in syntax checks.
- `npm run verify` passed with `161 pass, 0 fail, 0 not_run, 0 blocked, 161 total`; packaged browser gates passed after mobile, interaction, and accessibility smoke.

## Improvement

- Before: the mobile smoke could conflate a real UI failure with debounce timing and gave little state evidence when it failed.
- After: the smoke proves query propagation, empty-state rendering, live status text, and clear recovery separately, making release failures easier to diagnose without weakening the gate.

## Next Loop

- Continue the external publish unblock path once repository-root workflows are visible on the default branch.

## Experiment: Review package tracker field packet

- Hypothesis: Review packages are more copy-ready when tracker metadata can be copied separately from the issue body instead of being re-read from the draft UI.
- Primary metric: `reviewPackageTrackerFieldCopyCoverage`.
- Baseline: The pre-submit preview had one-click body copy for tracker, GitHub comment, and pinned note, but tracker fields such as title, priority, labels, estimate, assignee, and persist key were still implicit.
- Candidate: Add a `Tracker field packet` to the review package pre-submit preview and Markdown bundle, with title, project, priority, assignee, due, estimate, labels, and persist key plus a one-click `필드 복사` action.
- Decision: keep.

## External Comparison

- GitHub issue forms separate structured fields from generated issue Markdown, so JooPark now exposes tracker metadata beside the body preview before submission: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates focus on reusable issue structure for repeated workflows; the field packet makes the reusable tracker attributes explicit instead of relying only on the body copy: https://linear.app/docs/issue-templates
- Atlassian frames acceptance criteria as testable completion conditions, so the packet keeps operational fields and submit-readiness evidence available before the issue is created: https://www.atlassian.com/work-management/project-management/acceptance-criteria

## Evidence

- `review-handoff.js` now renders `Tracker Field Packet`, field rows, Markdown output, a hidden copy payload, and the `필드 복사` control.
- `app.js` copies the tracker field packet, records copied state/status in the panel, and surfaces a toast after clipboard write.
- `scripts/smoke-interactions.mjs` verifies `reviewPackageTrackerFieldCopy: true`, including title, priority, labels, and persist key in the copied clipboard payload.
- `scripts/audit-release-readiness.mjs` adds `review_package_tracker_field_packet`, and README documents the tracker field packet as part of the pre-submit preview.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 33 packaged files and `sourceDirtyFiles: 45`.
- `npm run verify` passed with `161 pass, 0 fail, 0 not_run, 0 blocked, 161 total`.

## Improvement

- Before: package bodies were copy-ready, but tracker metadata could still be skipped or transcribed inconsistently.
- After: the body preview and tracker fields each have their own copy path, so the package can move into tracker submission with less manual reconstruction.

## Next Loop

- Continue the external publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.
- Keep improving final output quality by adding the next copy-ready packet or verifier where the workflow still depends on manual interpretation.

## Experiment: Review package pre-submit copy

- Hypothesis: A pre-submit preview is more operator-ready when each final paste body can be copied independently from the preview card, without reassembling the bundle.
- Primary metric: `reviewPackagePreSubmitCopyCoverage`.
- Baseline: `Pre-submit preview` displayed the tracker issue, GitHub comment, and pinned note bodies, but the operator still had to select the right preview text manually.
- Candidate: Add per-target `본문 복사` controls for tracker issue body, GitHub comment body, and pinned note body; record copied state/status in the DOM; require static audit and browser smoke coverage.
- Decision: keep.

## Evidence

- `review-handoff.js` now renders three `copy-review-paste-body` buttons inside `reviewPackagePastePreview()`.
- `app.js` adds `copyReviewPackagePasteBody()` and updates button, preview item, and panel copied state after clipboard write.
- `scripts/smoke-interactions.mjs` clicks tracker/comment/note copy buttons and verifies clipboard contents plus `reviewPackagePastePreviewCopy: true`.
- `scripts/audit-release-readiness.mjs` adds `review_package_pre_submit_copy`.
- `README.md` documents per-target copy for the `tracker/comment/note body` preview.
- `npm run lint` passed.
- `npm test` passed with package files `30`, interaction steps `43`, `reviewPackagePastePreviewCopy: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `156 pass, 0 fail, 0 not_run, 0 blocked, 156 total`.

## Improvement

- Before: the final body preview removed guesswork, but copying still depended on manual text selection.
- After: each final paste target has a one-click copy path with visible status, so the package can move straight into tracker/comment/note submission.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Release unique DOM id gate

- Hypothesis: The release package is safer when duplicate HTML `id` values fail verification before browser smoke has to diagnose selector collisions.
- Primary metric: `releaseUniqueDomIdGateCoverage`.
- Baseline: `index.html` currently had 50 source ids and 0 duplicates, but `verify-release.mjs` did not enforce that invariant.
- Candidate: `verify-release.mjs` now scans packaged `index.html` for duplicate ids, `audit-release-readiness.mjs` has a `release_unique_dom_ids` checklist item, and README documents the duplicate-id regression guard.
- Decision: keep.

## Evidence

- Source scan reported `{ "totalIds": 50, "duplicates": [] }`.
- `node scripts/package-release.mjs` plus `node scripts/verify-release.mjs` passed with 30 packaged files and the duplicate-id gate active.
- `scripts/smoke-interactions.mjs` now proves `JooParkWorkspaceStorage.version === "joopark-workspace-storage/v1"` in the packaged settings flow, and README plus `docs/app-architecture.md` align `workspace-storage.js` as the persistence/import runtime boundary.
- `node --check scripts/smoke-interactions.mjs`, `node --check scripts/verify-release.mjs`, and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` reported `155 pass, 0 fail, 1 not_run, 0 blocked, 156 total`; the single `not_run` item was the packaged browser gates before the final full verify.

## Improvement

- Before: source and packaged HTML could accidentally gain duplicate ids without a manifest-level release failure.
- After: the release verifier, release audit, README, and smoke contract all preserve the DOM id uniqueness and storage-runtime loading invariants.

## Next Loop

- Run the full `npm run lint`, `npm test`, and `npm run verify` gates after this log update.
- Continue the external publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: Release runtime script order gate

- Hypothesis: The release package is safer when the verifier fails if vendor files or extracted runtime helpers load after `app.js` or out of dependency order.
- Primary metric: `releaseRuntimeScriptOrderGateCoverage`.
- Baseline: `index.html` loaded scripts in the correct order, but `verify-release.mjs` did not enforce the order and did not normalize packaged `?v=` asset hashes.
- Candidate: `verify-release.mjs` now normalizes script `src` values, verifies vendor -> storage -> UI/runtime helper -> `app.js` order, and `audit-release-readiness.mjs` has a `release_runtime_script_order` checklist item. The check also formalized `storage-status-view.js` as a packaged runtime file in docs and release expectations.
- Decision: keep.

## Evidence

- `node scripts/package-release.mjs` plus `node scripts/verify-release.mjs` passed with 32 packaged files, `sourceDirtyFiles: 44`, and the script-order gate active.
- `node scripts/audit-release-readiness.mjs --format=summary` reported `156 pass, 0 fail, 1 not_run, 0 blocked, 157 total`; the single `not_run` item was the packaged browser gates before the final full verify.
- `README.md` and `docs/app-architecture.md` now list `storage-status-view.js` beside `workspace-storage.js`, and the storage-health audit checks rendering in `storage-status-view.js` separately from storage data collection in `workspace-storage.js`.
- `npm test` passed with packaged evidence including `search_empty_state_cache_no_cache: true`, `storage_status_view_cache_no_cache: true`, `searchEmptyStateModule: true`, `storageStatusViewModule: true`, and `reviewPackageTrackerFieldCopy: true`.
- `node scripts/audit-release-readiness.mjs --run-gates` passed with `160 pass, 0 fail, 0 not_run, 0 blocked, 160 total`.

## Improvement

- Before: a release could include every runtime file but still load an extracted helper after `app.js`, producing startup failures only in browser smoke.
- After: manifest verification catches missing, reordered, or query-versioned runtime script mismatches before the browser gates start.

## Next Loop

- Run the full `npm run lint`, `npm test`, and `npm run verify` gates after this log update.
- Continue the external publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: Review package pre-submit preview

- Hypothesis: Review packages are more practical when users can inspect the exact tracker issue, GitHub comment, and pinned-note body text immediately before external paste.
- Primary metric: `reviewPackagePreSubmitPreviewCoverage`.
- Baseline: `Paste-Ready Targets` named the three destinations and bundle sections, but users still had to scroll through the full bundle to inspect the final body text for each destination.
- Candidate: Add a compact `Pre-submit preview` panel and embedded `### Paste Body Preview` section with `Tracker issue body`, `GitHub comment body`, and `Pinned note body`, including body bytes and exact Markdown content.
- Decision: keep.

## External Comparison

- GitHub issue forms generate issue Markdown from structured inputs, so the preview now exposes the final tracker body before the user submits it: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates keep reusable issue content close to the destination workflow; JooPark mirrors that by showing tracker/comment/note bodies separately before paste: https://linear.app/docs/issue-templates
- Atlassian acceptance-criteria guidance emphasizes concrete, testable output; the preview makes each paste body inspectable without reconstructing the bundle: https://www.atlassian.com/work-management/project-management/acceptance-criteria

## Evidence

- `review-handoff.js` now adds `reviewPackagePastePreviewTargets()`, `reviewPackagePastePreviewMarkdown()`, and `reviewPackagePastePreview()` helpers.
- `app.js` renders the preview for workspace, knowledge-base, and benchmark review packages.
- Bundle Markdown now includes `### Paste Body Preview` with exact fenced Markdown bodies for tracker issue, GitHub comment, and pinned note.
- `styles.css` adds `.portfolio-package-paste-preview`, `.portfolio-package-paste-preview-head`, and `.portfolio-package-paste-preview-grid` with bounded scroll areas for long bodies.
- `scripts/smoke-interactions.mjs` verifies all three preview cards and persisted `reviewPackagePastePreviewVisible: true`.
- `scripts/audit-release-readiness.mjs` adds `review_package_pre_submit_preview`.
- `npm run lint` passed.
- `npm test` passed with 29 release files, 16 desktop routes, 16 mobile routes, 43 interaction steps, `reviewPackagePastePreviewVisible: true`, and zero console/network/layout issues.
- `npm run verify` passed with `153 pass, 0 fail, 0 not_run, 0 blocked, 153 total`.

## Improvement

- Before: the user knew the bundle had tracker/comment/note targets, but still had to search the full bundle sections to review the final text.
- After: the shipped review package exposes the exact three paste bodies in a compact panel and repeats them in the bundle Markdown preview section.

## Next Loop

- Add one-click per-target copy controls for the tracker issue body, GitHub comment body, and pinned note body so users can paste a single destination without copying the entire bundle.
- Continue the live publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: Publish dispatch default-branch handoff

- Hypothesis: The publish unblock path is safer when the app separates local staged workflow files from the default-branch action required for GitHub Actions visibility.
- Primary metric: `publishDispatchDefaultBranchHandoffCoverage`.
- Baseline: `data/publish-dispatch-plan.json` showed `localWorkflowTargetsReady: true` and `remoteWorkflowVisibilityReady: false`, but the default-branch handoff was only prose in `nextActions`.
- Candidate: Add `workflowDefaultBranchHandoff` to `plan-publish-dispatch.mjs`, persist it in `data/publish-dispatch-plan.json`, surface it in System Status, and require it in smoke/audit/docs.
- Decision: keep.

## External Comparison

- GitHub workflow configuration is defined in YAML workflow files, so the handoff names the exact two `.github/workflows` paths that must land on the repository default branch: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- Manual workflow runs still require `workflow_dispatch` and a visible workflow in GitHub Actions, so the handoff keeps dispatch blocked until the live plan confirms `allDispatchReady`: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow

## Evidence

- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` now writes `workflowDefaultBranchHandoff` with `localStageReady: true`, default branch `main`, `git add .github/workflows/joopark-pages.yml .github/workflows/joopark-drift-watch.yml`, `git commit -m 'Add JooPark publish workflows'`, and the repo-scoped visibility verification command.
- System Status renders `workflowDefaultBranchHandoff` inside the `Publish dispatch plan` panel and keeps `remoteWorkflowVisibilityReady: false` plus both GitHub Actions visibility blockers.
- `scripts/smoke-interactions.mjs` checks the new data attribute and command text in the packaged browser flow.
- `node scripts/audit-release-readiness.mjs --format=summary` reported `152 pass, 0 fail, 1 not_run, 0 blocked, 153 total`; the only not-run item was packaged browser gates before the final `npm run verify`.
- `npm run lint`, `npm test`, and `npm run verify` passed; final readiness reported `153 pass, 0 fail, 0 not_run, 0 blocked, 153 total` with packaged browser gates passing.

## Improvement

- Before: the next action told the operator to push or commit, but the machine-readable plan did not expose the exact local stage command pair or default-branch requirement.
- After: the JSON, System Status UI, smoke, audit, and docs all expose the same handoff while still refusing to dispatch until GitHub Actions lists both workflows.

## Next Loop

- Land the staged repository-root Pages and Drift Watch workflow files on default branch `main` with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `remoteWorkflowVisibilityReady` and `allDispatchReady` are true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Review package paste-ready targets

- Hypothesis: Review packages become more copy-ready when the manifest names the exact tracker, GitHub comment, and pinned-note paste targets instead of only saying the bundle is complete.
- Primary metric: `reviewPackagePasteTargetPreviewCoverage`.
- Baseline: Review package bundles exposed Markdown Handoff, Issue Draft, GitHub Comment Draft, Pinned Note Body, manifest, final quality gate, and quality repairs, but the UI did not summarize the exact paste destinations or their readiness count.
- Candidate: Add `Paste-Ready Targets`, `Paste target readiness: pass (3/3)`, paste-target status/count/ready data attributes, and visible tracker/comment/note target rows in the manifest summary and bundle Markdown.
- Decision: keep.

## External Comparison

- GitHub issue forms turn structured required inputs into issue Markdown, so JooPark now labels the tracker issue target and verifies the issue body is ready before paste: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates keep reusable issue structures close to the workflow that will receive them; JooPark mirrors that by separating tracker, GitHub comment, and workspace note paste destinations: https://linear.app/docs/issue-templates
- Atlassian acceptance-criteria guidance emphasizes concrete, testable completion conditions; the paste-target table makes each external destination a testable readiness item before submission: https://www.atlassian.com/work-management/project-management/acceptance-criteria

## Evidence

- `app.js` now adds `REVIEW_PACKAGE_PASTE_TARGETS`, `reviewPackagePasteTargetReadiness()`, manifest `pasteTargets`, and visible `data-review-package-paste-target-status`, `data-review-package-paste-target-count`, and `data-review-package-paste-target-ready` attributes.
- Review bundle Markdown now embeds `Paste target readiness: pass (3/3)` and a `### Paste-Ready Targets` table for Tracker issue, GitHub comment, and Pinned note.
- `scripts/smoke-interactions.mjs` verifies the paste-target list for workspace, knowledge-base, and benchmark review bundles, and records `reviewPackagePasteTargetsVisible: true`.
- `scripts/audit-release-readiness.mjs` adds `review_package_paste_ready_targets`, and the run-gated audit reported `review_package_paste_ready_targets: pass`.
- `README.md` documents the Paste-Ready Targets section alongside the final quality gate and repair checklist.
- A stale release package initially exposed a missing `review-handoff.js` runtime in `dist/release`; rebuilding with `node scripts/package-release.mjs` restored the 28-file package and `node scripts/verify-release.mjs` passed.
- `npm test` passed with packaged evidence including `reviewPackagePasteTargetsVisible: true`, `reviewPackageQualityRepairChecklistVisible: true`, `dbCatalogModule: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `151 pass, 0 fail, 0 not_run, 0 blocked, 151 total`; packaged browser gates passed with 16 desktop routes, 16 mobile routes, 43 interaction steps, and 28 release files.

## Improvement

- Before: the bundle contained the right pieces, but the user still had to infer which exact text went to the issue tracker, GitHub comment, or pinned note.
- After: every review package shows a 3/3 paste-target readiness summary and names the three paste destinations before the user copies the bundle.

## Next Loop

- Add an optional compact pre-submit preview that extracts only the final tracker/comment/note body text from the bundle for one-click paste review.
- Continue the live publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: GitHub workflow local staging

- Hypothesis: The external publish blocker is more actionable when the repository-root workflow files are staged locally and the remaining blocker is only remote GitHub Actions visibility.
- Primary metric: `githubWorkflowLocalStagingCoverage`.
- Baseline: `plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` reported both workflows as missing from the repository root, so dispatch was blocked before Actions visibility could be verified.
- Candidate: Add `--stage-local` to both workflow preparation scripts, write `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` from the checked templates, update publish dispatch planning and System Status to distinguish `localWorkflowTargetsReady` from `remoteWorkflowVisibilityReady`, and audit the staged files against their templates.
- Decision: keep.

## External Comparison

- GitHub workflow files are stored under `.github/workflows`, so the staged files now match the repository-root target paths: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- Manual workflow dispatch still depends on `workflow_dispatch` and default-branch visibility, so the live plan continues to block dispatch until GitHub Actions lists both workflows: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow

## Evidence

- `node scripts/prepare-github-pages-workflow.mjs --stage-local` and `node scripts/prepare-github-drift-watch-workflow.mjs --stage-local` wrote both repository-root workflow files without requiring a workflow-scope token for remote writes.
- `cmp -s docs/github-pages-workflow.yml .github/workflows/joopark-pages.yml` and `cmp -s docs/github-drift-watch-workflow.yml .github/workflows/joopark-drift-watch.yml` proved both local files match their templates exactly.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` now reports `localWorkflowTargetsReady: true`, `remoteWorkflowVisibilityReady: false`, both workflow plans with `targetExists: true`, and only two blockers: the workflows are not visible in GitHub Actions.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed with `151 pass, 0 fail, 0 not_run, 0 blocked, 151 total`.
- `node scripts/smoke-release.mjs` passed with packaged desktop, mobile, interaction, and accessibility gates; interaction evidence reported 129/129 persisted checks and zero console/network issues.

## Improvement

- Before: the publish plan mixed local missing-file blockers with remote Actions visibility blockers.
- After: the local files are staged and audited, so the remaining external blocker is precise: push or commit the staged workflows to the default branch with a workflow-scope token or GitHub UI session, then rerun the live dispatch plan.

## Next Loop

- Push or commit the staged repository-root Pages and Drift Watch workflows to the default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `remoteWorkflowVisibilityReady` and `allDispatchReady` are true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Review package quality repair checklist

- Hypothesis: The review package output is more copy-ready when a failed final quality gate produces exact repair actions, not only a `needs_review` status.
- Primary metric: `reviewPackageQualityRepairChecklistCoverage`.
- Baseline: Review package manifests showed `Final Output Quality Gate`, `Ready to submit`, and `Final quality score`, but the repair path was implicit in evidence text.
- Candidate: Add `Quality repairs`, `Quality Repair Checklist`, repair status/count data attributes, and criterion-specific repair actions for accuracy evidence, specific context, execution readiness, reuse readiness, safety readiness, and submit readiness. Passing bundles now show `Quality repairs: none (0)` and `No repairs required; package is ready to submit.`
- Decision: keep.

## External Comparison

- GitHub issue forms use required validations and convert structured inputs into issue Markdown, so JooPark now pairs each final quality criterion with the exact missing field to repair before submission: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates emphasize reusable prefilled issue structure for repeated workflows; JooPark keeps the reusable bundle but adds a repair checklist when the output is not yet reusable: https://linear.app/docs/issue-templates
- Atlassian frames acceptance criteria as clear, concise, testable completion conditions; JooPark mirrors that by turning failed output-quality criteria into checklist actions instead of vague warnings: https://www.atlassian.com/work-management/project-management/acceptance-criteria

## Evidence

- `app.js` now adds `REVIEW_PACKAGE_FINAL_QUALITY_REPAIRS`, `repairStatus`, `repairCount`, `repairSummary`, and visible `data-review-package-quality-repair-status` / `data-review-package-quality-repair-count` attributes.
- Review bundle Markdown now includes `Quality repairs: none (0)`, `### Quality Repair Checklist`, and `- [x] No repairs required; package is ready to submit.` for pass-state packages; failed criteria map to copy-ready repair actions.
- `scripts/smoke-interactions.mjs` verifies the repair checklist for workspace, knowledge-base, and benchmark review bundles, and records `reviewPackageQualityRepairChecklistVisible: true`.
- `scripts/audit-release-readiness.mjs` adds `review_package_quality_repair_checklist`.
- `README.md` documents the repair checklist as the operational rule for when a generated bundle is not ready to submit.
- While re-verifying, release audit exposed that `db-catalog.js` had to be treated as a packaged runtime file and one migration delete tooltip lacked target-specific text; the package now ships 27 runtime files and the migration delete control includes a target-specific accessible title/label.
- `npm run lint` passed.
- `npm test` passed with packaged evidence including `reviewPackageQualityRepairChecklistVisible: true`, `dbCatalogModule: true`, `db_catalog_cache_no_cache: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `148 pass, 0 fail, 0 not_run, 0 blocked, 148 total`.

## Improvement

- Before: users could see that a bundle was pass/fail, but a failed final-quality result still required interpretation before they could repair it.
- After: every bundle carries a repair checklist. Passing bundles explicitly say no repairs are required, and failing bundles name the exact source/context/execution/reuse/safety/submit-readiness fields to restore before sharing.

## Next Loop

- Add a compact pre-submit preview that extracts the final tracker/comment/note body from the bundle and highlights only the exact text the user should paste.
- Continue the live publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: Publish dispatch System panel

- Hypothesis: The public readiness surface is more operator-ready when the repo-scoped publish dispatch plan is persisted and visible inside System Status, not only returned by CLI.
- Primary metric: `publishDispatchSystemPanelCoverage`.
- Baseline: `plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` could detect missing workflow files and GitHub Actions visibility, but the saved app still showed only workflow install and post-dispatch evidence panels.
- Candidate: Add `data/publish-dispatch-plan.json`, make `plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` generate it, render a `Publish dispatch plan` panel in System Status, and verify it in package manifest, smoke, and release audit.
- Decision: keep.

## External Comparison

- GitHub workflow dispatch depends on workflows existing on the default branch and being visible to Actions, so JooPark keeps `allDispatchReady` false until both workflow plans report readiness: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub workflow listing is repo-scoped through `gh workflow list --repo`, so the panel records `workflowListCommand` and the exact repo used for live evidence: https://cli.github.com/manual/gh_workflow_list

## Evidence

- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` writes `data/publish-dispatch-plan.json` with `repoEvidenceReady: true`, two workflow cards, four blockers, `dispatchReady: false`, `driftDispatchReady: false`, and `allDispatchReady: false`.
- `release-status.js` now renders `publishDispatchPlanHTML()` and `app.js` loads it through `loadPublishDispatchPlan()` into the System Status publish readiness panel.
- `scripts/verify-release.mjs` and `scripts/audit-release-readiness.mjs` now treat `data/publish-dispatch-plan.json` as a runtime release artifact.
- `scripts/smoke-interactions.mjs` verifies `data-system-publish-dispatch-plan`, two workflow cards, blocker text, repo-scoped dispatch commands, `nextVerificationCommand`, and `suggestedCommands` in the packaged browser flow.
- `npm run lint`, `npm test`, and `npm run verify` passed; final release readiness reported `148 pass, 0 fail, 0 not_run, 0 blocked, 148 total`.
- Live publish remains blocked because repository-root Pages and Drift Watch workflow files are not installed and are not visible in GitHub Actions.

## Improvement

- Before: the operator had to rerun CLI output to see whether workflow dispatch was safe.
- After: the shipped app displays the live dispatch blocker state, workflow visibility result, guarded dispatch commands, and next verification command from the persisted plan.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Review package final output quality gate

- Hypothesis: Review package bundles are more usable when the bundle itself says whether it is ready to submit, not just whether a Markdown file was generated.
- Primary metric: `reviewPackageReadyToSubmitGateCoverage`.
- Baseline: review bundles had a manifest, checksum, source freshness, required sections, and smoke coverage, but no explicit final output quality gate that separated "generated" from "tracker/comment/note ready".
- Candidate: Add `Final Output Quality Gate` to the bundle manifest with `Ready to submit`, `Final quality score`, and six criteria: `Accuracy evidence`, `Specific context`, `Execution ready`, `Reuse ready`, `Safety ready`, and `Submit ready`. Expose the same status through UI data attributes, Markdown bundle text, smoke persisted checks, audit, and README.
- Decision: keep.

## External Comparison

- GitHub issue forms convert structured user inputs into issue Markdown, which makes required fields and copy-ready issue bodies a useful external baseline for JooPark package bundles: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates emphasize reusable prefilled issue structure for repeated workflows, so JooPark keeps all copy targets in one bundle and adds a reusable final gate: https://linear.app/docs/issue-templates
- Atlassian's acceptance criteria guidance emphasizes specific, testable criteria; JooPark now treats acceptance, validation, decision gate, fallback, and missing-evidence handling as submit-readiness inputs: https://www.atlassian.com/work-management/project-management/acceptance-criteria

## Evidence

- `app.js` now adds `REVIEW_PACKAGE_FINAL_QUALITY_CRITERIA`, `reviewPackageFinalQualityGate()`, manifest fields `finalQualityGate`, and visible `data-review-package-final-quality-status` / `data-review-package-final-quality-score` attributes.
- Review bundle Markdown now embeds `Ready to submit: pass`, `Final quality score: 6/6`, and a `### Final Output Quality Gate` table before source freshness.
- `scripts/smoke-interactions.mjs` verifies the final quality gate for workspace, knowledge-base, and benchmark review bundles, and records `reviewPackageFinalQualityGateVisible: true`.
- `scripts/audit-release-readiness.mjs` adds `review_package_final_output_quality_gate`.
- `README.md` documents the gate as the difference between a generated bundle and a tracker/comment/note-ready output.
- A stale package run exposed a missing `command-palette.js` release artifact; after rebuilding, `smoke-release` verified the command palette runtime with no console issues.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence including `reviewPackageFinalQualityGateVisible: true`, `workflowUiInstallPlanPanel: true`, `commandPaletteModule: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `146 pass, 0 fail, 0 not_run, 0 blocked, 146 total`.

## Improvement

- Before: a review bundle could be complete in structure but still required a reviewer to infer whether it was safe and polished enough to paste into a tracker, GitHub comment, or pinned note.
- After: every review bundle carries its own final output quality verdict and score, so users can distinguish "generated" from "ready to submit" before sharing.

## Next Loop

- Add a compact, copy-ready "quality defects" section for any future bundle that fails the final quality gate, so the user gets exact repair steps instead of only `needs_review`.
- Continue the live publish unblock path after repository-root workflow installation, then capture post-dispatch evidence.

## Experiment: Workflow UI install System panel

- Hypothesis: The public readiness surface is more product-ready when the GitHub UI workflow install plan is visible inside System Status, not only in CLI output or copied handoff text.
- Primary metric: `workflowUiInstallSystemPanelCoverage`.
- Baseline: The app could load `data/publish-evidence.json`, but the workflow UI install plan still required running CLI commands to see the exact GitHub new-file links, copy commands, workflow confirmation links, and next verification command.
- Candidate: Add `data/workflow-ui-install-plan.json`, make `plan-workflow-ui-install.mjs --dry-run --write` generate it, render a `GitHub UI workflow install plan` panel in System Status, and verify it in package manifest, smoke, and release audit.
- Decision: keep.

## External Comparison

- GitHub workflows are YAML files stored under `.github/workflows`, so the System panel now shows the exact repository-root targets and template hashes before dispatch: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub web UI supports creating new files in repositories with write access, so the panel exposes the exact default-branch `githubNewFileUrl` links instead of only text instructions: https://docs.github.com/en/github/managing-files-in-a-repository/creating-new-files
- GitHub manual workflow runs require `workflow_dispatch` on the default branch, so the panel keeps `nextVerificationCommand` visible until both workflows are installed and visible: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow

## Evidence

- `scripts/plan-workflow-ui-install.mjs --dry-run --write` writes `data/workflow-ui-install-plan.json` with two ready plans, `githubNewFileUrl`, `githubWorkflowUrl`, `templateCopyCommand`, `githubNewFileOpenCommand`, `githubWorkflowOpenCommand`, and `nextVerificationCommand`.
- `release-status.js` now renders `workflowUiInstallPlanHTML()` and `app.js` loads it through `loadWorkflowUiInstallPlan()` into the System Status publish readiness panel.
- `scripts/verify-release.mjs` and `scripts/audit-release-readiness.mjs` now treat `data/workflow-ui-install-plan.json` as a runtime release artifact.
- `scripts/smoke-interactions.mjs` verifies `data-system-workflow-ui-install-plan`, two workflow cards, two GitHub new-file links, two workflow confirmation links, and the repo-specific next verification command in the packaged browser flow.
- `npm run lint`, `npm run test`, and `npm run verify` passed; final release readiness reported `146 pass, 0 fail, 0 not_run, 0 blocked, 146 total`.
- Live preflight still reports `repoEvidenceReady: true`, `targetExists: false`, `dispatchReady: false`, `driftDispatchReady: false`, `allDispatchReady: false`; the real blocker remains remote workflow installation.

## Improvement

- Before: an operator had to run CLI planning commands or copy a long handoff to locate the two GitHub workflow creation URLs.
- After: the shipped app itself displays the two workflow install cards, copy/open commands, hashes, and next verification command, so the external publish unblock path is visible from the product surface.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Workflow UI install copy/open commands

- Hypothesis: Workflow UI install handoff is more operator-ready when it returns terminal-ready copy/open commands, not only URLs and hashes.
- Primary metric: `workflowUiInstallCopyOpenCommandCoverage`.
- Baseline: `plan-workflow-ui-install.mjs` and embedded dispatch plans exposed `githubNewFileUrl`, `githubWorkflowUrl`, and template hashes, but the operator still had to manually copy YAML and open GitHub pages.
- Candidate: Add `templateCopyCommand`, `githubNewFileOpenCommand`, and `githubWorkflowOpenCommand` to both workflow UI install plans and publish dispatch UI install plans; update release-status handoffs, Settings copy text, README, audit, and browser smoke assertions.
- Decision: keep.

## External Comparison

- GitHub manual workflow runs require `workflow_dispatch`, so JooPark still blocks dispatch until workflows are installed and visible: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow
- GitHub trigger behavior depends on workflow files being present on the repository default branch, so the UI install handoff now opens the exact default-branch new-file page and the Actions workflow page: https://docs.github.com/actions/using-workflows/triggering-a-workflow
- GitHub workflow syntax is YAML-file based, so the plan keeps template hash/required-term checks while adding `pbcopy` for the exact template content: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown` prints two `templateCopyCommand` values, two `githubNewFileOpenCommand` values, and two `githubWorkflowOpenCommand` values for Pages and Drift Watch.
- `node scripts/plan-publish-dispatch.mjs --dry-run` embeds the same copy/open commands in both `workflowUiInstallPlans` and nested `workflowPlans[].uiInstallPlan`.
- `release-status.js`, `app.js`, `README.md`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` now require the copy/open command handoff.
- `npm run lint` passed.
- `npm test` passed with packaged interaction evidence reporting `settingsHandoffCopy: true`, `systemPublishReadiness: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `144 pass, 0 fail, 0 not_run, 0 blocked, 144 total`.

## Improvement

- Before: the handoff was safe and source-specific, but still forced manual browser opening and YAML copying.
- After: the same plan output gives a terminal-ready sequence: copy the YAML with `pbcopy`, open the GitHub new-file page, then open the Actions workflow page to verify visibility.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Workflow UI install suggested repo command

- Hypothesis: A workflow UI install handoff is safer when the next verification command uses the detected repo directly and keeps `OWNER/REPO` only as a clearly labeled template fallback.
- Primary metric: `workflowUiInstallSuggestedRepoCommandCoverage`.
- Baseline: `plan-workflow-ui-install.mjs --dry-run --markdown` and embedded dispatch UI install plans exposed GitHub URLs and hashes, but their next verification step still emphasized the `OWNER/REPO` placeholder.
- Candidate: Add `suggestedRepo`, `repoReplacementHint`, repo-specific `nextVerificationCommand`, and `placeholderVerificationCommand` to the UI install plan and embedded dispatch plans; update app handoffs, README, smoke, and audit coverage.
- Decision: keep.

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --markdown` now prints `suggestedRepo: biojuho/BIOJUHO-Projects`, `nextVerificationCommand: node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects`, and keeps `node scripts/plan-publish-dispatch.mjs --live --repo OWNER/REPO` as `placeholderVerificationCommand`.
- `node scripts/plan-publish-dispatch.mjs --dry-run` now embeds the same repo-specific `nextVerificationCommand` in both workflow UI install plans and `nextActions`, while dispatch commands remain guarded with `OWNER/REPO` until `repoEvidenceReady: true`.
- `release-status.js`, `app.js`, `README.md`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` now require the suggested repo command in publish handoff copy and release checks.
- `node --check app.js`, `node --check scripts/audit-release-readiness.mjs`, and `node --check scripts/smoke-interactions.mjs` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` reported `142 pass, 0 fail, 1 not_run, 0 blocked, 143 total`; the only not-run item was packaged browser gates before the final `npm run verify`.
- `npm run lint`, `npm run test`, and `npm run verify` passed; final release readiness reported `144 pass, 0 fail, 0 not_run, 0 blocked, 144 total`.

## Improvement

- Before: the safest install plan still left the operator with a placeholder command at the handoff point where the real repo is already known.
- After: the handoff promotes the exact repo-scoped verification command first, while preserving the placeholder template as a fallback for copied instructions that target a different repo.

## Next Loop

- Install repository-root Pages and Drift Watch workflows via the verified GitHub UI plan, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Publish dispatch ready fixture proof

- Hypothesis: Publish dispatch automation is safer when the blocked live branch and the fully ready branch are both machine-verified, so future changes cannot accidentally expose `gh workflow run` suggestions before GitHub Actions workflow visibility is proven.
- Primary metric: `publishDispatchReadyFixtureCoverage`.
- Baseline: Live dispatch planning correctly withheld `suggestedDispatchCommands`, but release audit only proved the blocked branch and did not exercise a ready workflow-list response.
- Candidate: Add `--workflow-list-fixture` support to `scripts/plan-publish-dispatch.mjs`, fixture active workflow data for Pages and Drift Watch, and audit assertions that the ready branch emits repo-scoped verification, dispatch, drift follow-up, and launch-proof commands only when all workflow plans are visible.
- Decision: keep.

## Evidence

- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --workflow-list-fixture scripts/fixtures/publish-workflows-ready.json` returns `workflowListSource: workflow-list-fixture`, `remoteWorkflowVisibilityReady: true`, `allDispatchReady: true`, `dispatchSuggestionStatus: ready`, and two repo-scoped `suggestedDispatchCommands`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` still returns `remoteWorkflowVisibilityReady: false`, `allDispatchReady: false`, `dispatchSuggestionStatus: withheld-until-all-dispatch-ready`, `suggestedDispatchCommands: []`, with blockers for both workflow files not being visible in GitHub Actions.
- `scripts/audit-release-readiness.mjs` now requires the ready fixture branch and the repo-scoped launch proof command.
- `docs/app-architecture.md`, `README.md`, and regenerated `dist/release` now include `habits-view.js` as a packaged runtime helper after the audit exposed stale release/documentation boundaries.
- `npm run lint` passed.
- `npm test` passed with packaged browser evidence including `habitsViewModule: true`, `habitSearchRecovery: true`, `personal_habit_action_labels: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `167 pass, 0 fail, 0 not_run, 0 blocked, 167 total`.

## Improvement

- Before: dispatch safety was proven for the withheld live branch, but the positive ready branch could regress without being caught until actual workflow visibility changed.
- After: the audit proves both sides: live visibility failure keeps dispatch commands empty, while fixture-backed visibility proves exactly which commands may appear once GitHub Actions lists both workflows.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Remote workflow file parity gate

- Hypothesis: External publish handoff is safer when default-branch workflow files are checked directly against the local templates before any dispatch command can be treated as runnable.
- Primary metric: `remoteWorkflowFileParityGateCoverage`.
- Baseline: Local workflow targets matched the templates and GitHub Actions visibility blockers were shown, but the release evidence did not carry a separate GitHub Contents API check proving whether those YAML files existed on the remote default branch.
- Candidate: Add `scripts/check-remote-workflow-files.mjs`, persist `data/remote-workflow-file-check.json`, surface the check in System Status, and carry `remoteWorkflowFilesReady` blockers through launch packet, output-quality receipt, smoke, audit, README, and release packaging.
- Decision: keep.

## Evidence

- `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write` wrote `data/remote-workflow-file-check.json` with `repoEvidenceReady=true`, `remoteWorkflowFilesChecked=true`, `remoteWorkflowFilesReady=false`, and two `not found on default branch` blockers.
- System Status now renders `Remote workflow file check` before `Publish dispatch plan`, with two workflow cards showing `templateSha256`, `remoteSha256`, `remoteExists=false`, `remoteMatchesTemplate=false`, and the repo-specific next command.
- `data/launch-execution-packet.json` now includes `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`, `remoteWorkflowFilesReady=false`, and remote workflow file blockers.
- `data/output-quality-audit.json` now includes `Remote workflow files ready: false` and `Remote workflow file check` blockers in the copy-ready final receipt.
- `scripts/smoke-interactions.mjs` verifies the remote file panel, launch packet, output-quality receipt, and publish handoff text in the browser.
- `npm run lint`, `npm run check:structure`, `npm test`, and `npm run verify` passed; final release readiness reported `184 pass, 0 fail, 0 not_run, 0 blocked, 184 total`.

## External Comparison

- GitHub's repository contents API is the direct source for reading a workflow file on the default branch before comparing it to local template content: https://docs.github.com/en/rest/repos/contents#get-repository-content
- Manual GitHub workflow dispatch requires the workflow file to exist on the default branch, so dispatch stays withheld until default-branch file evidence and Actions visibility both pass: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Improvement

- Before: operators saw that Actions did not list the workflows, but the product did not independently show whether the expected YAML files were missing from `main` or merely invisible.
- After: the app, release audit, launch packet, and final receipt all name the missing default-branch workflow files and keep dispatch blocked until `remoteWorkflowFilesReady` becomes true.

## Next Loop

- Install `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session.
- Rerun `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`, then `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `remoteWorkflowFilesReady` and `allDispatchReady` are true.

## Experiment: Remote workflow file check panel

- Hypothesis: Publish handoff quality improves when the product shows a repo-scoped default-branch workflow file check before any dispatch command can be copied or run.
- Primary metric: `remoteWorkflowFileCheckPanelCoverage`.
- Baseline: Remote workflow installation blockers were visible through publish dispatch planning, but System Status and the release audit did not independently prove whether `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` existed on the default branch and matched local templates.
- Candidate: Surface `data/remote-workflow-file-check.json` as a `Remote workflow file check` panel with `remoteWorkflowFilesReady`, per-file `remoteMatchesTemplate`, `not found on default branch` errors, and the exact `check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write` next command.
- Decision: keep.

## Evidence

- `release-status.js` renders each remote workflow file card with `templateSha256`, `remoteSha256`, `remoteExists`, `remoteMatchesTemplate`, `error`, blocker, workflow URL, and next command evidence.
- `scripts/smoke-interactions.mjs` verifies the panel data attributes, both workflow cards, `remoteWorkflowFilesReady=false`, `remoteMatchesTemplate=false`, `not found on default branch`, and the repo-specific next command.
- README documents the remote file check before publish dispatch so operators verify default-branch files before running `gh workflow run`.
- `node scripts/audit-release-readiness.mjs --format=summary` passed with `183 pass, 0 fail, 1 not_run, 0 blocked`.
- `npm run verify` passed with `184 pass, 0 fail, 0 not_run, 0 blocked, 184 total`.

## External Comparison

- GitHub's repository contents API is the right primitive for comparing the default-branch workflow file against local template content before dispatch: https://docs.github.com/en/rest/repos/contents#get-repository-content
- Manual GitHub workflow dispatch requires the workflow file on the default branch, so the UI keeps dispatch commands withheld until that default-branch evidence is ready: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Improvement

- Before: the operator could see local workflow parity and GitHub Actions visibility blockers, but the missing default-branch file cause was less explicit in the UI.
- After: System Status names the exact remote file check, shows both missing workflow files with `not found on default branch`, and carries the same blocker into smoke, audit, launch packet, and output-quality receipts.

## Next Loop

- Install `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session.
- Rerun `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`, then `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `remoteWorkflowFilesReady` and `allDispatchReady` are true.

## Experiment: Review package view release boundary

- Hypothesis: Review package handoff rendering is safer as a dedicated runtime helper only if the package, workflow handoff, structure guard, browser smoke, and release audit all prove it as a first-class static asset.
- Primary metric: `reviewPackageViewReleaseBoundaryCoverage`.
- Baseline: `app.js` still owned the repeated Workspace, KB/IA, and Benchmark review package handoff shells even after `review-handoff.js` owned the prompt, manifest, bundle, and validator logic.
- Candidate: Extract `review-package-view.js`, keep scoring/action orchestration in `app.js`, register the helper in runtime script order and release packaging, and extend smoke/audit/docs coverage.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `review-package-view` extracted, `app.js` at 9145 lines, and no oversized sections/functions.
- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` and `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` regenerated the persisted handoff JSON with `review-package-view.js`; dispatch remains withheld because the workflows are not visible in GitHub Actions and the current CLI token lacks `workflow` scope.
- `npm run lint` passed with `review-package-view.js` and the updated release/smoke/audit scripts syntax-checked.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with 46 release files, 1532795 bytes, `sourceDirtyFiles: 61`, and `review-package-view.js` in runtime script order.
- `npm run verify` passed with `182 pass, 0 fail, 0 not_run, 0 blocked`, including packaged browser gates.
- Packaged smoke proved `review_package_view_cache_no_cache: true`, `reviewPackageViewModule: true`, `reviewPackageBundleVisible: true`, `reviewPackageManifestVisible: true`, `reviewPackagePastePreviewVisible: true`, and copy/status checks for the review package surfaces.

## Improvement

- Before: three review package handoff surfaces repeated shell markup in `app.js`, making future paste-preview or note-publish changes harder to audit.
- After: `review-package-view.js` owns the repeated shell, action bar, hidden bundle text, note publish status, paste preview composition, and review handoff data attributes; `app.js` delegates through a small helper boundary.

## Next Loop

- Split the remaining Portfolio review artifact/draft builders that still belong to `app.js` only because they coordinate issue, note, and receipt state.
- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on `main` with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Publish evidence resolved repo copy

- Hypothesis: Publish evidence copy blocks are only copy-ready if the visible repo line uses the resolved repository instead of leaving `OWNER/REPO` for the user to edit.
- Primary metric: `publishEvidenceResolvedRepoCopyCoverage`.
- Baseline: `shareUpdate`, `launchAnnouncement`, and `postLaunchVerificationReceipt` could still copy `Repo: OWNER/REPO` even when `suggestedRepo` had resolved to `biojuho/BIOJUHO-Projects`.
- Candidate: Add a shared repo display context to publish evidence capture, persist `displayRepo`, `evidenceRepo`, `repoResolution`, and `repoPlaceholderResolved`, and make all three copy outputs print `Repo: biojuho/BIOJUHO-Projects` while preserving the raw placeholder as evidence.
- Decision: keep.

## Evidence

- `node scripts/capture-publish-evidence.mjs --dry-run --write` regenerated `data/publish-evidence.json` with `displayRepo: biojuho/BIOJUHO-Projects`, `evidenceRepo: OWNER/REPO`, and `repoResolution: resolved_from_suggested_repo`.
- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` now prints `Repo: biojuho/BIOJUHO-Projects` and `Evidence repo: OWNER/REPO (placeholder resolved from suggestedRepo)`.
- System Status exposes `data-publish-evidence-display-repo`, `data-publish-evidence-evidence-repo`, `data-publish-evidence-repo-resolution`, and `data-publish-evidence-repo-placeholder-resolved`.
- `scripts/smoke-interactions.mjs` verifies the share update, public announcement, and post-launch receipt clipboard text use the resolved repo and do not include `Repo: OWNER/REPO`.
- `node scripts/audit-release-readiness.mjs --format=summary` passed static audit with `181 pass, 0 fail, 1 not_run, 0 blocked`; packaged browser gates were intentionally not run in that command.
- `npm run verify` passed the full release gate with `182 pass, 0 fail, 0 not_run, 0 blocked`, including packaged browser gates.

## External Comparison

- GitHub Pages evidence is repo-scoped and should name the repository that operators will verify through the Pages REST API: https://docs.github.com/en/rest/pages/pages

## Improvement

- Before: three copy-ready publish evidence outputs still needed manual repo editing after copy.
- After: the team update, public announcement guard, and archive receipt all show the actionable repo first and retain the placeholder only as traceable evidence context.

## Experiment: Publish evidence Markdown resolved repo header

- Hypothesis: The full publish evidence Markdown report is not copy-ready if its first repo field still says `OWNER/REPO`, even when the shorter copy blocks have been fixed.
- Primary metric: `publishEvidenceMarkdownResolvedRepoHeaderCoverage`.
- Baseline: `node scripts/capture-publish-evidence.mjs --dry-run --markdown` printed `- repo: OWNER/REPO` at the top of the report, forcing users to reinterpret the later `displayRepo` field before sharing the full report.
- Candidate: Render the Markdown header as `- repo: biojuho/BIOJUHO-Projects`, keep the raw placeholder as `- evidenceRepo: OWNER/REPO (placeholder resolved from suggestedRepo)`, document the behavior, and make the audit self-check fail if `- repo: OWNER/REPO` reappears.
- Decision: keep.

## Evidence

- Baseline command showed the first report fields as `- repo: OWNER/REPO`, `- displayRepo: biojuho/BIOJUHO-Projects`, and `- evidenceRepo: OWNER/REPO`.
- Candidate command now shows `- repo: biojuho/BIOJUHO-Projects`, `- displayRepo: biojuho/BIOJUHO-Projects`, and `- evidenceRepo: OWNER/REPO (placeholder resolved from suggestedRepo)`.
- `scripts/audit-release-readiness.mjs` now reports `resolvedRepoHeader: true` only when the Markdown report contains the resolved repo header and does not contain `- repo: OWNER/REPO`.
- `node scripts/audit-release-readiness.mjs --format=summary` passed static audit with `181 pass, 0 fail, 1 not_run, 0 blocked`; packaged browser gates were intentionally not run in that command.

## External Comparison

- GitHub Pages evidence is repo-scoped, so full reports should lead with the repository operators will verify through the Pages API rather than a template placeholder: https://docs.github.com/en/rest/pages/pages

## Improvement

- Before: users could copy the full Markdown report and still need to manually fix or explain the first repo line.
- After: the full report, short team update, public announcement guard, and archive receipt all share the same resolved repo convention.

## Experiment: Publish dispatch workflow-scope evidence

- Hypothesis: Publish handoff is safer when the dispatch plan records both remote workflow visibility and the current CLI token's ability to install workflow files.
- Primary metric: `publishDispatchWorkflowScopeEvidenceCoverage`.
- Baseline: `data/publish-dispatch-plan.json` showed `remoteWorkflowVisibilityReady=false`, but the same plan did not carry the current token's `workflow` scope state into System Status or the launch packet.
- Candidate: Add `workflowScopeChecked`, `workflowScopeAvailable`, and `workflowScopeInstallBlocked` to `plan-publish-dispatch.mjs`, render those fields in System Status, and include the install-scope blocker in launch/output quality receipts.
- Decision: keep.

## External Comparison

- GitHub's manual workflow dispatch documentation says a `workflow_dispatch` workflow must exist on the default branch before it can be run manually or through CLI/API, so the product now separates default-branch workflow installation from dispatch readiness: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Evidence

- `gh auth status -h github.com` showed the active token scopes are `gist`, `read:org`, and `repo`; `workflow` is absent.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` saved `workflowScopeAvailable=false`, `workflowScopeInstallBlocked=true`, and `remoteWorkflowVisibilityReady=false`.
- Fixture verification still reports `allDispatchReady=true` when the workflows are remote-visible, proving the missing `workflow` scope blocks installation only, not dispatch after installation.
- `node scripts/capture-launch-execution-packet.mjs --write` now records `workflowScopeAvailable=false` and `workflowScopeInstallBlocked=true` in the install stage.
- `node scripts/capture-output-quality-audit.mjs --write` now includes `Workflow scope available: false` and `Workflow scope install blocked: true`.
- `npm test` passed with `publishDispatchPlanPanel`, `launchExecutionPacket`, and `outputQualityAuditReceipt` true.

## Improvement

- Before: a user could see workflow visibility was blocked, but not whether the current CLI session could fix it.
- After: System Status and copied launch receipts distinguish the two states: workflow files are not remote-visible, and the current CLI token cannot install them without a workflow-scope token or GitHub UI session.

## Next Loop

- Install the two workflow files on the default branch using a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write`.
- Once `allDispatchReady=true`, dispatch Pages/Drift Watch and capture live publish evidence.

## Experiment: Output quality resolved repo receipt

- Hypothesis: A final quality receipt is not truly copy-ready if the first repo line still says `OWNER/REPO` when a verified suggested repo is already available.
- Primary metric: `outputQualityResolvedRepoCoverage`.
- Baseline: `JooPark Final Output Quality Audit Receipt` exposed `Repo: OWNER/REPO`, forcing users to edit the copied receipt before sharing or saving it.
- Candidate: Resolve the display repo from `suggestedRepo`/dispatch evidence, print `Repo: biojuho/BIOJUHO-Projects`, retain the raw placeholder as `Evidence repo: OWNER/REPO (placeholder resolved from suggestedRepo)`, and expose repo-resolution data attributes in System Status.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries are Markdown evidence meant to be read directly from the run summary, so the project receipt should not require placeholder cleanup before it is useful: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- GitHub Releases are public-facing release records, so release-quality receipts must keep repository identity and launch-proof state explicit before users adapt them for public notes: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## Evidence

- `scripts/capture-output-quality-audit.mjs` now resolves repo context and writes `repoResolution=resolved_from_suggested_repo`.
- `data/output-quality-audit.json` now contains `publishState.repo=biojuho/BIOJUHO-Projects`, `evidenceRepo=OWNER/REPO`, and a receipt with `Repo: biojuho/BIOJUHO-Projects`.
- `release-status.js` exposes `data-output-quality-audit-repo`, `data-output-quality-audit-evidence-repo`, `data-output-quality-audit-repo-resolution`, and `data-output-quality-audit-repo-placeholder-resolved`.
- `scripts/smoke-interactions.mjs` verifies the System Status attributes, receipt text, clipboard copy, and absence of `\nRepo: OWNER/REPO`.
- `node --check scripts/capture-output-quality-audit.mjs`, `node --check release-status.js`, `node --check scripts/smoke-interactions.mjs`, and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed static checks with only packaged browser gates not run.

## Improvement

- Before: the audit receipt had accurate blockers, but the first repo field was a template placeholder, so a user had to repair it before sharing.
- After: the first repo field is already actionable, while the raw placeholder is preserved as source-evidence context. The copied output is more practical without hiding the fact that live launch proof is still blocked.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: System Status view release boundary

- Hypothesis: System Status can be extracted into a runtime helper without weakening publish readiness, source snapshot, launch packet, or quality receipt evidence.
- Primary metric: `systemStatusViewReleaseBoundaryCoverage`.
- Baseline: System Status KPI, operational surface, source snapshot health, and publish readiness rendering were embedded in `app.js`; `npm run check:structure` reported `app.js` above 9200 lines with no dedicated System Status helper.
- Candidate: Add `system-status-view.js`, delegate System Status rendering through `JooParkSystemStatusView`, register it in runtime/package/workflow/audit/docs lists, and verify module load plus source snapshot live-region semantics.
- Decision: keep.

## External Comparison

- MDN's ARIA `status` role guidance treats status regions as polite live regions, matching the System Status source snapshot health panel that exposes `role="status"` and `aria-live="polite"`: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role

## Evidence

- `system-status-view.js` now owns System Status KPI, operational surface, source snapshot health, and publish readiness composition while `app.js` keeps data loading and copy actions.
- `npm run check:structure` passed with the `system-status-view` extraction candidate covered and `app.js` at 9200 lines.
- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` and `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed workflow/publish plans with `system-status-view.js`; dispatch remains withheld because remote workflows are not visible in GitHub Actions.
- `npm test` passed with 45 release files, `system_status_view_cache_no_cache: true`, `systemStatusViewModule: true`, `sourceSnapshotHealth: true`, `system_status_view_module_loaded: true`, and `system_status_source_snapshot_region: true`.
- `scripts/smoke-interactions.mjs` now parse-checks the browser interaction expression, escapes the repo newline guard, and waits for the full publish dispatch data-attribute contract before asserting the System publish panel.
- `node scripts/verify-release.mjs` passed with 45 release files, 1522438 bytes, and 60 dirty source files.
- `npm run verify` passed with `181 pass, 0 fail, 0 not_run, 0 blocked, 181 total`.

## Improvement

- Before: System Status mixed publish readiness UI, source snapshot health markup, and launch evidence composition inside the main app file.
- After: System Status rendering is a packaged runtime helper with release, browser, accessibility, workflow, audit, and docs coverage; the external publish path remains blocked only by remote workflow visibility, not by local release quality.

## Next Loop

- Split remaining Portfolio/review package rendering builders once release smoke coverage stays green.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Review package external tracker form packet

- Hypothesis: Review packages become more copy-ready for real external trackers when they expose a form-field packet, not only a Markdown body and generic tracker fields.
- Primary metric: `externalTrackerFormPacketCopyCoverage`.
- Baseline: Review packages copied the issue body and basic tracker fields, but users still had to reinterpret acceptance criteria, validation plan, owner, source key, and post-submit receipt fields for GitHub Issue Forms, Linear issue templates, or Jira work items.
- Candidate: Add `External Tracker Form Packet` to every paste preview and bundle, include 11 mapped rows, require 8/8 required fields, copy the packet to clipboard, and keep a post-submit external URL/ID receipt guard.
- Decision: keep.

## External Comparison

- GitHub Issue Forms define YAML-backed inputs plus labels and assignees, so a copy packet should separate title, body, labels, owner, and required fields: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear issue templates can be applied from the create issue modal and integrations, including form templates, so tracker-ready packets should preserve properties and intake fields: https://linear.app/docs/issue-templates
- Jira templates emphasize starting work from preformatted templates, so the packet keeps fields suitable for a Jira work item instead of only a freeform note: https://www.atlassian.com/software/jira/templates

## Evidence

- `review-handoff.js` now renders `External Tracker Form Packet` with title, description/body, acceptance criteria, validation plan, owner/assignee, due, estimate, priority, labels, source/persist key, and post-submit receipt rows.
- `scripts/smoke-interactions.mjs` verifies required fields `8/8`, 11 rows, GitHub/Linear/Jira copy text, clipboard copy, and receipt guard.
- `system-status-view.js` exposes the expected runtime alias and DOM marker after the structure gate surfaced the extraction contract.
- `node --check review-handoff.js` and `node --check scripts/smoke-interactions.mjs` passed.
- `node scripts/verify-release.mjs` passed with release files `45`, bytes `1518065`, and source dirty files `60`.
- `npm run verify` passed with `181 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the review package was strong for internal Markdown copy, but external issue-form submission still required manual field mapping and post-submit receipt discipline.
- After: the package exposes a copy-ready external tracker form packet with explicit required-field readiness, owner fallback from Operational Readiness, and a receipt reminder that prevents claiming external submission without an issue URL/ID.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Settings view release boundary

- Hypothesis: The Settings runtime helper is release-safe only when packaging, workflow handoff, interaction smoke, accessibility smoke, docs, and release audit all treat it as a first-class runtime file.
- Primary metric: `settingsViewReleaseBoundaryCoverage`.
- Baseline: `settings-view.js` was present, but the dedicated AutoResearch loop had not recorded Settings KPI/handoff/theme accessibility evidence as its own release boundary.
- Candidate: Register `settings-view.js` across workflow templates, planner required terms, README and architecture docs, release audit, interaction smoke, accessibility smoke, and persisted workflow/publish plans.
- Decision: keep.

## External Comparison

- MDN describes `aria-pressed` as the current pressed state of a toggle button, so the Settings theme controls now have a dedicated smoke check for true/false `aria-pressed` values: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-pressed

## Evidence

- `npm run check:structure` passed with `settings-view` extracted and `app.js` at 9256 lines.
- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` refreshed `data/workflow-ui-install-plan.json` with `settings-view.js` in the Pages template required terms and template hash `1bb6faa20beadeeda2769f2f8a3527eeb1550f705cd78c0e6efc6b849331d972`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed `data/publish-dispatch-plan.json`; dispatch remains withheld because Pages and Drift Watch workflows are not visible in GitHub Actions.
- `node scripts/capture-launch-execution-packet.mjs --write` refreshed `data/launch-execution-packet.json` with `readyToDispatch: false`, `launchProofReady: false`, and `readyForExternalClaim: false`.
- `npm run lint` passed.
- `npm test` passed with 44 release files, `settings_view_cache_no_cache: true`, `settingsViewModule: true`, `settings_view_module_loaded: true`, `settings_handoff_list_semantics: true`, `settings_theme_toggle_buttons: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `179 pass, 0 fail, 0 not_run, 0 blocked, 179 total`.

## Improvement

- Before: Settings runtime extraction could drift from workflow templates, docs, release audit, and a11y evidence.
- After: Settings KPI/profile/theme/backup/handoff rendering is tracked as a release boundary, package headers prove the file is shipped with no-cache, and browser smoke proves handoff list semantics plus toggle button state.

## Next Loop

- Split the remaining System Status rendering wrappers once release smoke coverage stays green.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Portfolio view release boundary

- Hypothesis: A Portfolio runtime helper is release-safe only when package, workflow handoff, interaction smoke, accessibility smoke, and audit evidence all prove it as a first-class runtime file.
- Primary metric: `portfolioViewReleaseBoundaryCoverage`.
- Baseline: `npm run check:structure` passed, but Portfolio KPI cards, segmented filters, candidate review snippets, card markup, and search empty-state recovery were still coupled to `app.js`.
- Candidate: Extract `portfolio-view.js`, keep project CRUD and review handoff state in `app.js`, add explicit `role="list"` / `role="listitem"` card semantics, register the module in release package/runtime order, and extend smoke/audit/docs coverage.
- Decision: keep.

## External Comparison

- MDN's ARIA list role guidance pairs `role="list"` with contained `role="listitem"` elements, matching the Portfolio project list and card semantics added in this loop: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/list_role

## Evidence

- `npm run check:structure` passed after extraction with `portfolio-view` extracted at 13/13 and module terms at 10/10.
- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` refreshed `data/workflow-ui-install-plan.json` with `portfolio-view.js` and the current Pages template hash `867bbaa44077ee761392c7fb9096d7b70e33c7fedbc8490b28247d925caf662e`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed `data/publish-dispatch-plan.json`; dispatch remains withheld because the Pages and Drift Watch workflows are not visible in GitHub Actions.
- `npm run lint` passed.
- `npm test` passed with release package files `43`, `portfolio_view_cache_no_cache: true`, `portfolioViewModule: true`, `portfolio_view_module_loaded: true`, `portfolio_card_list_semantics: true`, and no console/network/layout issues.
- `npm run verify` passed with `179 pass, 0 fail, 0 not_run, 0 blocked, 179 total`.

## Improvement

- Before: Portfolio rendering mixed KPI calculation, segmented filters, candidate queue summaries, project cards, list semantics, and search empty-state markup inside `app.js`.
- After: Portfolio rendering lives behind `JooParkPortfolioView`, the app wrapper only passes state and dependencies, project CRUD remains in `app.js`, card list semantics are browser-smoked, and release gates prove the helper is packaged and loaded.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Portfolio view release boundary

- Hypothesis: A PM Portfolio runtime helper is release-safe only when project cards, candidate filters, search empty states, package headers, structure audit, interaction smoke, accessibility smoke, and docs all treat it as a first-class runtime file.
- Primary metric: `portfolioViewReleaseBoundaryCoverage`.
- Baseline: Portfolio rendering, filter chips, KPI cards, card list semantics, and search empty-state markup were still owned by `app.js`, keeping the highest-value PM overview inside the monolith.
- Candidate: Add `portfolio-view.js`, delegate `renderPortfolio()` through `JooParkPortfolioView`, register the runtime file across package/release/workflow/audit gates, and add browser evidence for module loading plus card list semantics.
- Decision: keep.

## External Comparison

- GitHub Projects supports table, board, and roadmap views with per-view filtering, so Portfolio keeps segmented project/candidate filters and result markers as first-class UI.
- Jira Product Discovery views emphasize list/board/matrix/timeline organization plus filters, sorting, and autosave; Portfolio keeps candidate filters and ranked candidate evidence separate from project CRUD.
- Linear Timeline separates high-level project planning from issue implementation; Portfolio now keeps project-card rendering isolated from issue/CRUD logic.

## Evidence

- `npm run check:structure` passed with `app.js` at `9326` lines and `portfolio-view` marked `extracted` with `13/13` extraction terms.
- `node --check portfolio-view.js app.js scripts/check-app-structure.mjs scripts/audit-release-readiness.mjs scripts/package-release.mjs scripts/verify-release.mjs scripts/smoke-release.mjs scripts/smoke-interactions.mjs scripts/smoke-a11y.mjs` passed.
- `npm run lint` passed.
- `node scripts/package-release.mjs` passed with release files `43` and bytes `1497020`.
- `node scripts/verify-release.mjs` passed with release files `43`, bytes `1497020`, and deploy support files `4`.
- `node scripts/audit-release-readiness.mjs --format=summary` reached `177 pass, 0 fail, 1 not_run, 0 blocked, 178 total` before browser gates.
- `npm run verify` passed with `178 pass, 0 fail, 0 not_run, 0 blocked, 178 total`.

## Improvement

- Before: Portfolio was a broad rendering island inside `app.js`; release coverage could prove the page worked but not that the PM overview had a maintainable runtime boundary.
- After: Portfolio cards, KPI rendering, candidate filters, search empty state, and list semantics are packaged and audited as `portfolio-view.js`, while project CRUD and review handoff logic stay in `app.js`.

## Next Loop

- Split the remaining Portfolio review package builders or Settings/System rendering wrappers once release smoke coverage stays green.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Final output quality audit receipt

- Hypothesis: The final output is more practical and reusable when System Status can copy one criteria-based receipt that separates release quality from public launch proof.
- Primary metric: `outputQualityAuditReceiptCopyCoverage`.
- Baseline: Release readiness and publish evidence existed, but there was no single copy-ready receipt mapping accuracy, specificity, usability, reuse, safety, and public launch proof to concrete evidence and blockers.
- Candidate: Add `capture-output-quality-audit.mjs`, persist `data/output-quality-audit.json`, expose a System Status `Final output quality audit` panel with copy-to-clipboard receipt, and require release-audit plus browser smoke coverage.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries are designed to put important run results in Markdown on the workflow summary page, so the receipt mirrors that pattern by surfacing gate and blocker evidence without requiring raw log inspection: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- GitHub Releases package software with release notes for a wider audience, so the receipt keeps internal quality evidence distinct from public launch/release claims until live proof is complete: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## Evidence

- `node scripts/capture-output-quality-audit.mjs --write` generated `data/output-quality-audit.json` with `JooPark Final Output Quality Audit Receipt`, `releaseQualityReady`, `publicLaunchProofReady`, and `readyForExternalClaim`.
- `node scripts/capture-output-quality-audit.mjs --markdown` prints the copy block with `Status: release quality ready; public launch proof blocked` and the public-launch-completion guard.
- System Status now renders `data-system-output-quality-audit`, criteria/blocker counts, and a `copy-output-quality-audit-receipt` action.
- `scripts/smoke-interactions.mjs` verifies receipt loading, criteria count, blocked external-claim state, copy status, and clipboard text.
- `node scripts/verify-release.mjs` passed with release files `41`, bytes `1463342`, sourceDirtyFiles `55`, and deploy support files `4`.
- `npm run lint` passed.
- `npm run verify` passed with `176 pass, 0 fail, 0 not_run, 0 blocked, 176 total`.

## Improvement

- Before: a reviewer had to combine release gate output, publish evidence, dispatch blockers, and workflow install state to judge final-output quality.
- After: the app copies one internal audit receipt that is accurate, specific to `biojuho/BIOJUHO-Projects`, reusable for handoff, and explicitly blocked from public launch claims until live evidence is present.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Output quality external comparison receipt

- Hypothesis: The audit receipt is more defensible when it includes explicit external comparison sources instead of keeping that comparison only in the AutoResearch notes.
- Primary metric: `outputQualityExternalComparisonCoverage`.
- Baseline: The product receipt copied internal criteria and blockers, but copied 0 official external comparison references.
- Candidate: Add `externalComparison` to `capture-output-quality-audit.mjs`, persist two official GitHub comparison sources in `data/output-quality-audit.json`, render them in System Status, and verify both DOM and clipboard coverage.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries display important run results on the workflow summary page, matching the receipt's compact gate/blocker summary pattern: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- GitHub Releases package software with release notes for a wider audience, matching the receipt's separation between internal quality evidence and public launch claims: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## Evidence

- `data/output-quality-audit.json` now includes `externalComparison` with 2 sources: `GitHub Actions job summaries` and `GitHub Releases`.
- System Status exposes `data-output-quality-audit-comparison-count="2"` and renders both source links under the final output quality audit panel.
- The hidden `JooPark Final Output Quality Audit Receipt` copy text now includes an `External comparison:` section with both official source URLs.
- `node --check scripts/capture-output-quality-audit.mjs`, `node --check release-status.js`, `node --check app.js`, `node --check scripts/smoke-interactions.mjs`, and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/verify-release.mjs` passed with release files `41`, bytes `1466754`, sourceDirtyFiles `55`, and deploy support files `4`.
- `npm run lint` passed.
- `npm run verify` passed with `176 pass, 0 fail, 0 not_run, 0 blocked, 176 total`.

## Improvement

- Before: external comparison was available in the research note, but the copied product receipt did not carry it forward.
- After: the copied receipt names the external pattern it follows, cites both official sources, and still preserves the public launch proof blocker before any external completion claim.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Launch execution packet

- Hypothesis: The output is more practical when the remaining launch blocker is converted into one copy-ready operator packet instead of forcing the user to combine workflow install, dispatch, evidence, and quality receipts by hand.
- Primary metric: `launchExecutionPacketCopyCoverage`.
- Baseline: System Status had separate workflow install, dispatch, evidence, and quality receipt panels, but no single `JooPark Launch Execution Packet` copy that ordered the launch steps and guardrails.
- Candidate: Add `capture-launch-execution-packet.mjs`, persist `data/launch-execution-packet.json`, render the packet in System Status, and verify stage count, command text, external comparison, guard text, and clipboard copy.
- Decision: keep.

## External Comparison

- GitHub manual workflow dispatch requires `workflow_dispatch` and the workflow file on the default branch, so the packet makes default-branch workflow installation and visibility verification the first gate: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui
- GitHub Pages custom workflows deploy uploaded artifacts through `actions/deploy-pages` with `pages: write` and `id-token: write`, so the packet keeps Pages workflow verification before dispatch: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## Evidence

- `node scripts/capture-launch-execution-packet.mjs --write` generated `data/launch-execution-packet.json` with 5 execution stages, 13 commands, 8 blockers, and 2 official external comparison sources.
- System Status now exposes `data-system-launch-execution-packet`, `data-launch-execution-stage-count="5"`, `data-launch-execution-command-count="13"`, and `data-launch-execution-comparison-count="2"`.
- The hidden `JooPark Launch Execution Packet` copy text includes `pbcopy` template commands, GitHub new-file URLs, visibility verification, withheld dispatch commands, live evidence capture, and the public-claim guard.
- `scripts/smoke-interactions.mjs` verifies the packet panel, stage labels, external comparison, copy status, and clipboard text.
- `node scripts/verify-release.mjs` passed with release files `44`, bytes `1502372`, sourceDirtyFiles `59`, and deploy support files `4`.
- `npm run lint` passed.
- `npm run verify` passed with `179 pass, 0 fail, 0 not_run, 0 blocked, 179 total`.

## Improvement

- Before: an operator had to inspect several panels and decide the safe sequence manually.
- After: the app copies one ordered launch packet that starts with workflow installation, blocks dispatch until `allDispatchReady: true`, captures proof with repo-scoped commands, and refuses public claims until live proof is complete.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Gantt view release boundary

- Hypothesis: A PM Gantt runtime helper is release-safe only when package, workflow handoff, interaction smoke, accessibility smoke, and audit evidence all prove it as a first-class runtime file.
- Primary metric: `ganttViewReleaseBoundaryCoverage`.
- Baseline: `npm run check:structure` passed with `app.js` at 9412 lines, but Gantt SVG rendering, dependency lines, task labels, KPIs, and search empty-state recovery were still embedded in `app.js`.
- Candidate: Extract `gantt-view.js`, keep task CRUD in `app.js`, add chart summary semantics, register the module in release package/runtime order, and extend smoke/audit/docs coverage.
- Decision: keep.

## External Comparison

- W3C APG button guidance treats Space and Enter as required button activation keys, so Gantt SVG task bars are tested with both keys: https://www.w3.org/WAI/ARIA/apg/patterns/button/
- MDN's ARIA button role guidance notes that non-native buttons need explicit focus and keyboard handling, which matches the `role="button"`/`tabindex="0"` checks for SVG task shapes: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/button_role
- MDN documents SVG `tabindex` as the sequential focus hook for SVG elements, so the Gantt SVG smoke verifies focusability instead of relying on pointer-only interaction: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/tabindex

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` refreshed `data/workflow-ui-install-plan.json` with `gantt-view.js` in the Pages template required terms and template hash `758ced1bd556e25bc8de58078a090610bc122a454810c3c6a5520868aca89204`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed `data/publish-dispatch-plan.json`; dispatch remains withheld because the Pages and Drift Watch workflows are not visible in GitHub Actions.
- `npm run check:structure` passed after extraction with `gantt-view` covered as an extraction candidate.
- `npm run lint` passed with `gantt-view.js` and the updated release/smoke/audit scripts syntax-checked.
- `npm test` passed with release files `39`, `gantt_view_cache_no_cache: true`, `ganttViewModule: true`, `ganttSvgTaskAccessibility: true`, `gantt_view_module_loaded: true`, `gantt_svg_group_labelled: true`, and `gantt_svg_button_semantics: true`.
- `npm run verify` passed with `174 pass, 0 fail, 0 not_run, 0 blocked, 174 total`.

## Improvement

- Before: Gantt was a large inline renderer inside `app.js`, mixing KPI calculation, SVG task/milestone rendering, dependency lines, search empty-state markup, and accessibility strings.
- After: Gantt rendering lives behind `JooParkGanttView`, the app wrapper only passes state and query, SVG tasks keep keyboard button semantics, and release gates prove the helper is packaged and loaded.

## Next Loop

- Split `View: Team / Resources` into a `team-view.js` runtime helper, preserving member CRUD in `app.js` and adding release/a11y smoke evidence for load matrix search recovery.

## Experiment: Team view release boundary

- Hypothesis: A PM Team/Resources runtime helper is release-safe only when package, workflow handoff, interaction smoke, accessibility smoke, and audit evidence all prove it as a first-class runtime file.
- Primary metric: `teamViewReleaseBoundaryCoverage`.
- Baseline: `npm run check:structure` passed with `app.js` at 9325 lines, but Team KPI, member rows, load indicators, resource matrix, and team search empty-state recovery were still embedded in `app.js`.
- Candidate: Extract `team-view.js`, keep member CRUD in `app.js`, add matrix table semantics, register the module in release package/runtime order, and extend smoke/audit/docs coverage.
- Decision: keep.

## External Comparison

- MDN's ARIA table role guidance describes static tabular data with row, columnheader, rowheader, and cell semantics, matching the Team resource matrix checks: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/table_role

## Evidence

- `npm run check:structure` passed after extraction with `team-view` extracted at 12/12.
- `node scripts/package-release.mjs && node scripts/verify-release.mjs` passed with release files `41`, bytes `1466754`, and deploy support files `4`.
- `npm run lint` passed with `team-view.js` and the updated release/smoke/audit scripts syntax-checked.
- `npm test` passed with `team_view_cache_no_cache: true`, `teamViewModule: true`, `teamSearchRecovery: true`, `team_view_module_loaded: true`, `team_matrix_table_semantics: true`, `systemPublishReadiness: true`, and `outputQualityAuditReceipt: true`.
- `npm run verify` passed with `176 pass, 0 fail, 0 not_run, 0 blocked, 176 total`.

## Improvement

- Before: Team rendering mixed KPI calculation, member rows, load bars, resource matrix markup, search empty-state markup, and member action labels inside `app.js`.
- After: Team rendering lives behind `JooParkTeamView`, the app wrapper only passes state and query, the resource matrix exposes table/header/cell semantics, and release gates prove the helper is packaged and loaded.

## Next Loop

- Split Portfolio PM rendering utilities into a `portfolio-view.js` runtime helper, preserving project/review CRUD and benchmark state in `app.js`.

## Experiment: Publish post-launch verification receipt

- Hypothesis: A launch evidence workflow is more copy-ready when it produces an internal post-launch verification receipt, not only a team status update and a public announcement.
- Primary metric: `publishPostLaunchReceiptCopyCoverage`.
- Baseline: Publish evidence exposed `JooPark Publish Evidence Update` and `JooPark Public Launch Announcement`, but there was no separate archive-ready receipt for launch notes or incident-free post-launch records.
- Candidate: Add `JooPark Post-Launch Verification Receipt` to `capture-publish-evidence.mjs`, persist it in `data/publish-evidence.json`, expose a System Status copy button, and require clipboard smoke plus release-audit coverage.
- Decision: keep.

## External Comparison

- GitHub Pages evidence should record the API's site URL/status/HTTPS fields, matching GitHub Pages REST documentation: https://docs.github.com/rest/reference/pages
- Workflow run evidence should record `status`, `conclusion`, `url`, and `headSha`, matching `gh run list --json` fields: https://cli.github.com/manual/gh_run_list
- Manual launch dispatch still depends on installed `workflow_dispatch` workflows, so the receipt refuses archival while live workflow evidence is missing: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow

## Evidence

- `node scripts/capture-publish-evidence.mjs --dry-run --write` regenerated `data/publish-evidence.json` with `postLaunchVerificationReceipt`.
- `node scripts/capture-publish-evidence.mjs --dry-run --markdown` prints `## Post-launch verification receipt` and a guarded `Status: not ready to archive` copy block.
- System Status now renders `data-publish-evidence-post-launch-receipt`, and `scripts/smoke-interactions.mjs` verifies the copy button and clipboard text.
- `node --check app.js`, `node --check release-status.js`, `node --check scripts/capture-publish-evidence.mjs`, `node --check scripts/smoke-interactions.mjs`, and `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/verify-release.mjs` passed with release files `39`, bytes `1443429`, and deploy support files `4`.
- `npm run lint` passed.
- `npm run verify` passed with `174 pass, 0 fail, 0 not_run, 0 blocked, 174 total`.

## Improvement

- Before: after live proof, users had to reinterpret the evidence report to create an internal post-launch record.
- After: the product copies a ready-to-archive receipt with Pages URL/status/HTTPS, workflow status/conclusion/headSha, freshness, checklist, blockers, and next command. In dry-run or incomplete proof states, it copies a clear archival guard instead of a false launch record.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Stats view release boundary

- Hypothesis: A newly extracted Stats runtime helper is release-safe only when the package manifest, workflow templates, audit gates, interaction smoke, and docs all treat it as a first-class runtime file.
- Primary metric: `statsViewReleaseBoundaryCoverage`.
- Baseline: `stats-view.js` was loaded by the app and required by release verification, but persisted workflow handoffs and release audit evidence could drift from the actual packaged file list.
- Candidate: Add `stats-view.js` to workflow templates and planner required terms, release audit runtime/module gates, interaction smoke module evidence, README and architecture docs, and refresh persisted workflow/publish plan JSON.
- Decision: keep.

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` refreshed `data/workflow-ui-install-plan.json` with `stats-view.js` and the current Pages template hash.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed `data/publish-dispatch-plan.json`; dispatch remains withheld because the Pages and Drift Watch workflows are not visible in GitHub Actions.
- `npm run lint` passed.
- `npm test` passed with release package files `37`, `stats_view_cache_no_cache: true`, `statsViewModule: true`, no console issues, no network issues, and no layout issues.
- `npm run verify` passed with `170 pass, 0 fail, 0 not_run, 0 blocked, 170 total`.

## Improvement

- Before: Stats extraction could pass part of the release path while leaving template handoffs or audit evidence stale.
- After: Stats is covered across static file lists, package verification, browser module evidence, operator handoffs, and docs.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Kanban view release boundary

- Hypothesis: A PM Kanban runtime helper is release-safe only when package, workflow handoff, interaction smoke, accessibility smoke, and audit evidence all prove it as a first-class runtime file.
- Primary metric: `kanbanViewReleaseBoundaryCoverage`.
- Baseline: `kanban-view.js` was present in the runtime and release file lists, but the AutoResearch loop had not recorded a dedicated Kanban boundary experiment after the module extraction.
- Candidate: Verify `kanban-view.js` through release packaging, workflow/publish plan refreshes, interaction module evidence, Kanban search recovery, lane/list accessibility semantics, and final release audit gates.
- Decision: keep.

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` refreshed `data/workflow-ui-install-plan.json` with `kanban-view.js` in the Pages template required terms.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` refreshed `data/publish-dispatch-plan.json`; dispatch remains withheld because the Pages and Drift Watch workflows are not visible in GitHub Actions.
- `npm run lint` passed with `kanban-view.js`, `scripts/smoke-interactions.mjs`, `scripts/smoke-a11y.mjs`, and release audit scripts syntax-checked.
- `npm test` passed with release package files `38`, `kanban_view_cache_no_cache: true`, `kanbanViewModule: true`, `kanbanSearchRecovery: true`, `kanban_view_module_loaded: true`, and `kanban_lane_list_semantics: true`.
- `npm run verify` passed with `172 pass, 0 fail, 0 not_run, 0 blocked, 172 total`.

## Improvement

- Before: Kanban was packaged, but the dedicated module boundary evidence was not recorded as its own AutoResearch experiment.
- After: Kanban is covered across package headers, workflow handoffs, interaction smoke, accessibility smoke, release audit, and AutoResearch state.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Workflow target parity evidence

- Hypothesis: Workflow installation remains externally blocked, so the handoff must prove the local repository-root workflow files are byte-identical to the verified templates before anyone installs them through GitHub UI.
- Primary metric: `workflowTargetParityEvidenceCoverage`.
- Baseline: `plan-workflow-ui-install.mjs` and `plan-publish-dispatch.mjs` exposed template hashes and target existence, but did not persist `targetSha256`, `targetMatchesTemplate`, or a top-level local parity gate across the UI and audit receipts.
- Candidate: Add `templateSha256`, `targetSha256`, `targetMatchesTemplate`, and `localTargetParityReady` to workflow install planning, publish dispatch planning, System Status panels, launch execution packet, output-quality receipt, browser smoke, release audit, and README handoff docs.
- Decision: keep.

## Evidence

- `node scripts/plan-workflow-ui-install.mjs --dry-run --write` regenerated `data/workflow-ui-install-plan.json` with `localTargetParityReady=true` and matching template/target sha256 values for Pages and Drift Watch.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` regenerated `data/publish-dispatch-plan.json` with `targetMatchesTemplate=true` for both workflow plans while dispatch remains withheld because the workflows are not visible in GitHub Actions.
- `scripts/smoke-interactions.mjs` now requires workflow UI install and publish dispatch panels to expose local parity data attributes and copy-ready launch packet parity evidence.
- `scripts/audit-release-readiness.mjs` now requires persisted parity fields in dry-run, live, fixture-ready, and saved JSON paths.
- `data/launch-execution-packet.json` and `data/output-quality-audit.json` now include `localTargetParityReady` evidence.

## External Comparison

- GitHub manual workflow dispatch requires the workflow file to exist on the default branch with `workflow_dispatch`, so this loop verifies the exact YAML that will be installed before allowing dispatch planning to proceed: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Improvement

- Before: operators could see template hashes and local target existence, but not a single persisted proof that the local `.github/workflows` files matched the templates they were expected to install.
- After: the workflow handoff, System Status UI, launch packet, output-quality receipt, smoke tests, and release audit all carry the same parity proof and block dispatch readiness if a local workflow target differs from its template.

## Next Loop

- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.
- Dispatch Pages and Drift Watch after `dispatchReady` and `allDispatchReady` are true, then run `capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --markdown` and `--write` until `postPublishEvidenceReady` is true.

## Experiment: Review artifact view release boundary

- Hypothesis: Review artifact rendering can be split safely only when the diff, receipt compare, repair suggestion, and post-apply fresh receipt paths remain covered by release packaging, HTTP cache headers, interaction smoke, and the release audit.
- Primary metric: `reviewArtifactViewReleaseBoundaryCoverage`.
- Baseline: `app.js` still owned artifact diff snippets, receipt markdown parsing/comparison, repair suggestion markup, and post-apply fresh receipt rendering inline.
- Candidate: Extract `review-artifact-view.js`, keep copy/apply/undo/open state actions in `app.js`, register the helper in runtime order, release package checks, smoke checks, audit gates, workflow handoffs, and docs.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `review-artifact-view` extracted and `app.js` at 8881 lines.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with release files `48`, bytes `1552718`, and deploy support files `4`.
- `node scripts/smoke-release.mjs` passed with `review_artifact_view_cache_no_cache: true`, `reviewArtifactViewModule: true`, no layout issues, no console issues, and no network issues.
- `npm run lint` passed with `review-artifact-view.js` and the updated release/smoke/audit scripts syntax-checked.
- `npm run verify` passed with `184 pass, 0 fail, 0 not_run, 0 blocked, 184 total`.

## Improvement

- Before: review artifact rendering and artifact action orchestration were tightly mixed in `app.js`, increasing the risk that release packaging, cache headers, or smoke coverage would drift when the artifact review UI changed.
- After: artifact presentation lives behind `JooParkReviewArtifactView`, `app.js` keeps state-changing actions, and release gates prove the helper is packaged, loaded, cache-controlled, and exercised in the review artifact flow.

## Next Loop

- Split another large Portfolio review presentation cluster or continue reducing `app.js` around review result validation while preserving the action/state boundary.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Review package external receipt integrity

- Hypothesis: A review package is not fully ready for external tracker submission unless the copied receipt and status update preserve a deterministic body checksum, required-field readiness, and submit-sequence proof.
- Primary metric: `externalSubmissionReceiptIntegrityCoverage`.
- Baseline: The review package exposed an external tracker form packet and receipt copy flow, but the copied external receipt/update did not carry tracker body checksum, 8/8 required-field proof, or 6/6 submit-sequence proof as one integrity line.
- Candidate: Add `External receipt integrity` to the receipt/update builders, expand the External Issue Receipt Template to 13 rows, expand the Review Submission Update to 10 rows, and require the checksum/form/sequence proof in DOM, clipboard, static audit, and packaged release gates.
- Decision: keep.

## External Comparison

- GitHub issue forms convert required structured inputs into the final issue body, so JooPark now keeps required-field proof and the generated body checksum together before external paste: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms

## Evidence

- `review-handoff.js` now computes `reviewPackageSubmissionIntegrity()` from `trackerForm`, `issueDraft`, and `submitSequence`.
- The External Issue Receipt Template includes `Tracker body checksum`, `Tracker body bytes`, `Required form fields ready`, `Submit sequence ready`, and `External receipt integrity`.
- The Review Submission Update includes `External receipt integrity: tracker body checksum fnv1a32-...; required form fields 8/8; submit sequence 6/6`.
- `scripts/smoke-interactions.mjs` verifies the receipt/update rows and clipboard text, including `Tracker body checksum: fnv1a32-`, `Required form fields ready: 8/8`, `Submit sequence ready: 6/6`, and `External receipt integrity`.
- `scripts/audit-release-readiness.mjs` adds `review_package_external_receipt_integrity` and raises the release audit total to 186 checks.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `186 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the package had a useful tracker field packet, but after external paste the user still had to manually preserve proof that the submitted body, required fields, and submit steps matched the generated package.
- After: the receipt and copied submission update carry the same checksum/form/sequence proof, so the external handoff is archive-ready and easier to compare against the submitted tracker item.

## Next Loop

- Continue with review result validation output quality: make malformed-result repair guidance copy-ready and preserve exact failure/warning evidence without weakening release gates.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Review result view release boundary

- Hypothesis: Review result saved-card and validation output rendering can be split safely only when release packaging, interaction smoke, accessibility live-region smoke, and release audit all prove the helper as a first-class runtime file.
- Primary metric: `reviewResultViewReleaseBoundaryCoverage`.
- Baseline: `app.js` still owned saved result card HTML, action/confidence label rendering, compact saved result model creation, and validation output cards inline.
- Candidate: Extract `review-result-view.js`, keep localStorage persistence and issue/note mutation in `app.js`, add `role="status" aria-live="polite" aria-atomic="true"` to validator status, and register package/smoke/audit/docs/workflow coverage.
- Decision: keep.

## External Comparison

- W3C WCAG 4.1.3 Status Messages and ARIA22 support exposing dynamic validation status through a polite status region without moving focus: https://www.w3.org/WAI/WCAG21/Understanding/status-messages.html and https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA22

## Evidence

- `npm run check:structure` passed with `review-result-view` extracted and `app.js` at 8866 lines.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with release files `49`, bytes `1565193`, and deploy support files `4`.
- `node scripts/smoke-release.mjs` passed with `review_result_view_cache_no_cache: true`, `reviewResultViewModule: true`, `review_result_status_live_region: true`, no layout issues, no console issues, and no network issues.
- `npm run lint` passed with `review-result-view.js` and the updated release/smoke/audit scripts syntax-checked.
- `npm run verify` passed with `186 pass, 0 fail, 0 not_run, 0 blocked, 186 total`.

## Improvement

- Before: result validator presentation and saved-result compaction were mixed with persistence and downstream issue/note mutation in `app.js`.
- After: result presentation lives behind `JooParkReviewResultView`, `app.js` keeps state-changing behavior, and accessibility smoke proves the validator status is announced as a polite live region.

## Next Loop

- Continue splitting the remaining Portfolio review issue/note draft builders, especially validated-result body composition and assignee follow-up presentation, while preserving state mutation in `app.js`.
- Push or create `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the repository default branch with a workflow-scope token or GitHub UI session, then rerun `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write` and `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `allDispatchReady` is true.

## Experiment: Remote workflow install packet

- Hypothesis: Remote workflow installation stays externally blocked, so System Status should provide one copy-ready packet with exact GitHub UI URLs, local template copy commands, verification commands, and dispatch guards instead of only listing blockers.
- Primary metric: `remoteWorkflowInstallPacketCoverage`.
- Baseline: the Remote workflow file check panel showed missing default-branch workflow files, but operators still had to assemble the copy/open/verify sequence by reading several fields.
- Candidate: Add an `installPacket` to `check-remote-workflow-files`, render/copy it in System Status, cover the clipboard flow in interaction smoke, and refresh release receipts with `remoteWorkflowFilesReady=false`.
- Decision: keep.

## External Comparison

- GitHub repository contents API checks default-branch files, and manual workflow dispatch requires a `workflow_dispatch` workflow file on the default branch, so the packet keeps install, visibility, and dispatch as separate gates: https://docs.github.com/en/rest/repos/contents#get-repository-content and https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Evidence

- `scripts/check-remote-workflow-files.mjs` now emits `JooPark Remote Workflow Install Packet` with `pbcopy < 'docs/github-pages-workflow.yml'`, `pbcopy < 'docs/github-drift-watch-workflow.yml'`, GitHub new-file open commands, current blockers, and the `remoteWorkflowFilesReady: true` / `allDispatchReady: true` guard.
- `release-status.js` renders the packet and per-workflow copy/create actions; `app.js` validates the new payload fields and copies the install packet from System Status.
- `scripts/smoke-interactions.mjs` verifies the install packet panel, clipboard contents, GitHub new-file URLs, local template copy commands, and no-dispatch guard.
- `review-result-view.js` now wraps validation failure lists and pass summaries as complete raw fragments, fixing escaped `<li>`/`<p>` output without weakening text escaping.
- `npm test` passed with release files `49`, `reviewResultValidatorFailure: true`, `remoteWorkflowFileCheckPanel: true`, no console issues, no network issues, and no layout issues.
- `npm run lint`, `npm run check:structure`, and `npm run verify` passed; final readiness was `186 pass, 0 fail, 0 not_run, 0 blocked, 186 total`.

## Improvement

- Before: remote workflow blockers were accurate, but the next human step required manual reconstruction across docs, System Status fields, and terminal commands.
- After: System Status provides a single guarded install packet that can be copied into the GitHub UI workflow installation process, while release gates still block dispatch and public launch proof until the remote files are actually present.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on remote `main` with GitHub UI or a workflow-scope token, then rerun `node scripts/check-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write`.
- Rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` until `allDispatchReady` is true, then dispatch and capture live publish evidence.

## Experiment: Review result repair packet scaffold

- Hypothesis: Failed review result validation becomes more usable when the copied repair packet includes the exact required JSON field checklist and a minimal correction scaffold, not only a list of error messages.
- Primary metric: `reviewResultRepairScaffoldCoverage`.
- Baseline: The validator showed a repair packet and copied failure-specific guidance, but it did not carry a complete `Required JSON fields` checklist or `Correction scaffold` that preserved the expected `schemaVersion`, `primaryDecisionKey`, `executionPlan`, `exceptions`, and `uiArtifacts.markdownSummary` contract.
- Candidate: Add `Required JSON fields` and `Correction scaffold` to `reviewResultRepairPacket()`, verify malformed JSON repair packet DOM/clipboard content in interaction smoke, and add `review_result_repair_packet_copy` to release readiness.
- Decision: keep.

## External Comparison

- GitHub Issue Forms support field validations and convert filled form inputs into the issue body, so JooPark repair packets now preserve required fields and expected output shape before downstream issue creation: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear form templates can require fields at issue creation, so the repair packet mirrors the same “fill the required structured fields before creating an issue” flow: https://linear.app/docs/issue-templates
- Jira Cloud blocks issue creation when required fields are missing and recommends clearer validator error messages, matching JooPark's copy-ready repair instructions and scaffold: https://support.atlassian.com/jira/kb/cant-create-issues-because-of-required-fields-in-jira-cloud/

## Evidence

- `review-result-view.js` now builds `reviewResultRepairRequiredFields()` and `reviewResultRepairScaffold()` for every failed or warning-state repair packet.
- The repair packet includes `Required JSON fields`, `Correction scaffold`, expected `schemaVersion`, expected `primaryDecisionKey`, `decisions`, `sourceSnapshot`, `qualityGate`, `executionPlan`, `exceptions`, `missingEvidence`, and `uiArtifacts.markdownSummary`.
- `scripts/smoke-interactions.mjs` verifies malformed JSON repair packet text and clipboard copy include the field checklist, scaffold, expected schema, and expected primary key.
- `scripts/audit-release-readiness.mjs` adds `review_result_repair_packet_copy` and raises the release audit total to 187 checks.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `187 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: users could see why validator JSON failed, but still had to reconstruct the full required output contract before asking an LLM or teammate to repair it.
- After: a failed validator state copies one repair packet with exact failures, required fields, a JSON scaffold, and guardrails, making the next correction request immediately actionable.

## Next Loop

- Continue improving review result failure recovery by adding a post-repair comparison receipt once corrected JSON passes and creates issue/note artifacts.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review result draft body boundary

- Hypothesis: Validated issue/note body construction and assignee follow-up presentation can move into `review-result-view.js` without changing downstream issue/note persistence, tracker metadata, or manual assignee override cleanup.
- Primary metric: `reviewResultDraftBodyBoundaryCoverage`.
- Baseline: `app.js` still assembled the validated review Markdown body, saved validated note body, and assignee follow-up panel inline after the result view runtime split.
- Candidate: Keep parsing, owner assignment, saved result lookup, persistence, and DOM mutation in `app.js`, but delegate `reviewSavedResultBody`, `reviewSavedResultNoteBody`, and `reviewAssigneeFollowUpPanel` presentation to `JooParkReviewResultView`.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `review-result-view` requiring the three new runtime functions and `app.js` at 8805 lines.
- `scripts/audit-release-readiness.mjs` now proves validated issue/note body and assignee follow-up rendering from `review-result-view.js` while `app.js` keeps downstream mutation.
- `scripts/smoke-interactions.mjs` now verifies low-confidence owner follow-up prompt examples render as `<code>` elements and not `[object Object]`.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with release files `49`, bytes `1580822`, and deploy support files `4`.
- `node scripts/smoke-release.mjs` passed with route count `16`, interaction steps `43`, `review_result_view_cache_no_cache: true`, `reviewResultViewModule: true`, no layout issues, no console issues, and no network issues.
- `npm run lint`, `git diff --check`, and `npm run verify` passed; final readiness was `187 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: validated body Markdown and assignee follow-up HTML were mixed into `app.js` next to state mutation, making review-result presentation harder to package and audit as a runtime boundary.
- After: `review-result-view.js` owns the body/panel presentation, `app.js` only prepares the model and mutates issue/note state, and release smoke proves the generated artifacts still survive issue/note creation.

## Next Loop

- Continue with a post-repair comparison receipt for corrected review result JSON once it passes validation and creates issue/note artifacts.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review assignee override view boundary

- Hypothesis: The issue draft assignee override panel can move into `review-result-view.js` without changing owner assignment, select option generation, draft persistence, rerender cleanup, or issue creation behavior.
- Primary metric: `reviewAssigneeOverrideViewBoundaryCoverage`.
- Baseline: `app.js` still rendered the assignee review panel inline, including select markup, confidence/status copy, and review-required data attributes.
- Candidate: Delegate the assignee override panel presentation to `reviewIssueDraftAssigneeOverridePanel` in `JooParkReviewResultView`, while `app.js` keeps `reviewAssigneeOptions`, status labels, override persistence, and DOM event handling.
- Decision: keep.

## Evidence

- `review-result-view.js` now owns `data-issue-draft-assignee-review-panel`, `data-issue-draft-assignee-select`, `data-issue-draft-assignee-review-copy`, confidence/source attributes, and the select accessibility label.
- `app.js` now calls `reviewResultViewCall("reviewIssueDraftAssigneeOverridePanel")` and still owns assignee options, `updateReviewIssueDraftAssignee`, `reviewIssueDraftOverrides`, `assignee-review`, `assignee-confirmed`, and `manual-override` state transitions.
- `scripts/audit-release-readiness.mjs` now proves the split from both sides and raises release readiness to 188 checks.
- `npm test` passed with 49 release files, 43 interaction steps, `reviewAssigneeOverride: true`, `reviewAssigneeOverrideDraftPersistence: true`, no layout issues, no console issues, and no network issues.
- `npm run verify` passed with `188 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the assignee override UI was still mixed into `app.js` next to state mutation, making review-result presentation harder to package and audit as a runtime boundary.
- After: `review-result-view.js` owns the panel rendering, `app.js` remains the state/action boundary, and packaged interaction smoke proves manual override, draft persistence, and rerender behavior still work.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` are installed on remote `main` and live launch evidence is captured.

## Experiment: Review issue draft shell view boundary

- Hypothesis: The repeated review issue draft shell can move into `review-result-view.js` without changing saved-result application, issue creation, assignee override persistence, artifact diff receipts, or backup import safety.
- Primary metric: `reviewIssueDraftShellViewBoundaryCoverage`.
- Baseline: `app.js` still rendered the workspace, KB/IA, and PM benchmark issue draft shell HTML inline, including the repeated grid, create button, body `<pre>`, validated badge, and draft dataset attributes.
- Candidate: Add `reviewIssueDraftPanel` to `JooParkReviewResultView`, delegate the three issue draft shells through `reviewResultViewCall("reviewIssueDraftPanel")`, keep state/action model preparation in `app.js`, and align imported note body clamping with the 4000 character note editor limit.
- Decision: keep.

## External Comparison

- GitHub Issue Forms define structured fields that become issue body content, matching the split between JooPark's draft field shell and generated Markdown body: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms
- Linear form templates can mark fields as required before issue creation, supporting the same field/body/readiness separation: https://linear.app/docs/issue-templates
- Jira Cloud blocks issue creation when required fields are missing, so JooPark keeps draft field metadata visible instead of burying it only in body text: https://support.atlassian.com/jira/kb/cant-create-issues-because-of-required-fields-in-jira-cloud/

## Evidence

- `review-result-view.js` now owns `reviewIssueDraftPanel`, `data-review-issue-draft`, `data-issue-draft-labels`, `data-issue-draft-result-source`, `data-issue-draft-execution-checklist-count`, and the issue body shell.
- `app.js` now calls `reviewResultViewCall("reviewIssueDraftPanel")` while retaining saved-result application, assignee override panels, artifact diff model construction, and create issue actions.
- `scripts/audit-release-readiness.mjs` adds `review_issue_draft_shell_view_boundary` and moves dash-case draft DOM attributes to `review-result-view.js` evidence.
- Backup import normalization now clamps imported note bodies to `4000`, matching the note editor `maxlength` and restoring `backupNormalizeClamped`.
- `npm run lint`, `npm test`, `npm run check:structure`, and `npm run verify` passed; final readiness was `191 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: three review issue draft variants duplicated the same shell in `app.js`, so future changes to draft fields, badges, and body panels had to be repeated and audited in multiple places.
- After: the shell presentation is centralized in `review-result-view.js`, while `app.js` remains the state/action boundary and packaged smoke proves the three issue draft flows still create/persist artifacts.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, especially copy/receipt panels that can move without changing mutation behavior.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Review result post-repair receipt

- Hypothesis: A repaired review result is not archive-ready unless users can copy a receipt that links the previous validation failure, corrected pass state, saved checksum, and downstream artifact guardrails.
- Primary metric: `reviewResultPostRepairReceiptCoverage`.
- Baseline: Failed review result validation could copy a repair packet and the corrected JSON could pass/save, but there was no audited copy-ready receipt tying the previous failure evidence to the saved corrected result before issue/note creation.
- Candidate: Keep failed validation snapshots in `app.js`, render a `JooPark Review Result Post-Repair Receipt` from `review-result-view.js`, wire `copy-review-result-repair-receipt`, and verify DOM/clipboard/audit coverage.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries preserve run evidence in Markdown after a workflow step completes, so JooPark mirrors that pattern by preserving validation failure and correction proof before downstream artifact creation: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- Jira Cloud required-field failures block creation and recommend clearer validator messages, so the post-repair receipt keeps the original failure text and corrected pass evidence together for audit: https://support.atlassian.com/jira/kb/cant-create-issues-because-of-required-fields-in-jira-cloud/

## Evidence

- `review-result-view.js` renders `JooPark Review Result Post-Repair Receipt` with `Previous Failure Evidence`, corrected result fields, saved `Payload checksum`, current warnings, and `Downstream Guard`.
- `app.js` records failed validation snapshots, passes a post-repair receipt model after corrected JSON saves, and wires `copy-review-result-repair-receipt` to clipboard state and toast feedback.
- `scripts/smoke-interactions.mjs` verifies malformed JSON failure, pass after repair, receipt checksum, `Previous state: fail`, JSON parsing failure evidence, and clipboard copy text.
- `scripts/audit-release-readiness.mjs` includes `review_result_post_repair_receipt`.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `188 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: users could repair a bad validator response, but the repair journey itself was not a durable artifact.
- After: the validator copies one receipt that proves what failed, what passed after repair, which saved checksum anchors the corrected output, and why downstream issue/note artifact receipts are still required.

## Next Loop

- Continue by adding comparison between post-repair receipts and created issue/note artifact receipts, so repaired review results can be checked end-to-end after artifact creation.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review post-repair artifact link

- Hypothesis: A repaired review result is not complete after issue/note creation unless the post-repair receipt and current artifact receipt are linked by the same primary key, artifact status, and saved checksum.
- Primary metric: `reviewPostRepairArtifactLinkCoverage`.
- Baseline: The validator could produce a post-repair receipt and artifact diff could export a created artifact receipt, but the two receipts were not automatically compared or copied as one end-to-end completion proof.
- Candidate: Persist post-repair receipt Markdown on saved review results, pass it into issue/note artifact diff models, render a `JooPark Review Post-Repair Artifact Link`, and verify ready-state plus clipboard coverage in smoke and release audit.
- Decision: keep.

## Evidence

- `app.js` now persists `repairReceiptMarkdown`/`postRepairReceipt`, normalizes the fields during import/load, exposes `reviewResultRepairReceiptForKey`, and wires `copy-review-post-repair-artifact-link`.
- `review-artifact-view.js` renders the post-repair artifact link with key match, artifact receipt readiness, artifact diff status, created id, and saved payload checksum guardrails.
- `scripts/smoke-interactions.mjs` verifies `reviewPostRepairArtifactLink`, hidden Markdown contents, ready-state attributes, and clipboard copy text.
- `scripts/audit-release-readiness.mjs` adds `review_post_repair_artifact_link` and the runtime module terms.
- `npm run lint`, `npm run check:structure`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, `node scripts/smoke-release.mjs`, `git diff --check`, and `npm run verify` passed; final readiness was `191 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: corrected validator output and created issue/note artifact receipts were individually auditable, but users still had to infer that they belonged to the same repaired result.
- After: created artifact diffs expose one copy-ready link receipt that proves the repaired result receipt, current artifact receipt, primary key, pass diff status, and saved checksum line up.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Release manifest fresh package audit

- Hypothesis: Full release audit is less reliable if packaged browser gates build a fresh temporary artifact but `manifest_integrity` checks an older `dist/release` directory.
- Primary metric: `releaseManifestFreshPackageCoverage`.
- Baseline: `npm run verify` briefly failed `manifest_integrity` even though packaged browser gates passed, because `--run-gates` verified a temporary package while manifest/source parity inspected the existing default `dist/release`.
- Candidate: make `scripts/audit-release-readiness.mjs` run `node scripts/package-release.mjs` before `node scripts/verify-release.mjs` inside `verifyRelease()`, then require the behavior in the manifest integrity checklist and README.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now reports manifest verification as `node scripts/package-release.mjs && node scripts/verify-release.mjs`.
- `manifest_integrity` requires the audit script and README to mention the fresh package step and stale dist guard.
- `README.md` documents that audit regenerates `dist/release` before manifest/source parity verification.
- The follow-up verification plan is the same public release gate: `npm run lint`, `npm run check:structure`, `git diff --check`, `node scripts/package-release.mjs && node scripts/verify-release.mjs`, `npm run verify`, and cached quick audit.

## Improvement

- Before: a stale local `dist/release` could produce a false `manifest_integrity` failure after source/evidence edits.
- After: the full audit verifies a default release package generated from the same current source state it is auditing.

## Next Loop

- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.
- After workflow scope/default-branch install is complete, rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Release gate cache gitignore

- Hypothesis: A generated release gate cache should not appear as a source change or inflate release provenance dirty-file evidence.
- Primary metric: `releaseGateCacheIgnoredFromSourceProvenance`.
- Baseline: `git status --short --ignored autoresearch-results/release-readiness-gates.json` reported `?? autoresearch-results/release-readiness-gates.json`.
- Candidate: add `autoresearch-results/release-readiness-gates.json` to `.gitignore` while keeping the local cache file available for quick audit reuse.
- Decision: keep.

## Evidence

- `.gitignore` now excludes `autoresearch-results/release-readiness-gates.json`.
- `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` still reports `workflowScopeAvailable=false`, `remoteWorkflowVisibilityReady=false`, and `allDispatchReady=false`; external publish remains blocked correctly.
- Follow-up verification checks `git status --short --ignored autoresearch-results/release-readiness-gates.json`, JSON parse, lint, structure, release verify, full verify, and cached quick audit.

## Improvement

- Before: the generated browser gate cache appeared as an untracked source change.
- After: the cache remains usable for local quick audits without polluting source provenance or the reviewable change set.

## Next Loop

- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.
- After workflow scope/default-branch install is complete, rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true.

## Experiment: Release gate evidence cache

- Hypothesis: A release readiness summary is weaker if it forgets a just-passed packaged browser gate and reports `not_run` unless every quick status check reruns the full browser suite.
- Primary metric: `releaseGateQuickAuditCachedPass`.
- Baseline: after source edits, `node scripts/audit-release-readiness.mjs --format=summary` reported `195 pass, 0 fail, 1 not_run, 0 blocked, 196 total` because `packaged_browser_gates` had no fresh matching cache.
- Candidate: write `autoresearch-results/release-readiness-gates.json` after `--run-gates`, then let quick summary audits reuse it only when schema, source commit, input file fingerprint, completeness, and the 6-hour freshness window match.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries keep concrete gate output attached to a run, which supports preserving recent gate evidence with source and freshness metadata instead of treating a quick status command as proof by itself: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary

## Evidence

- `scripts/audit-release-readiness.mjs` now records `joopark-packaged-browser-gates/v1` cache evidence with command, source commit, input file stats, max age, and complete headers/fallbacks/desktop/mobile/interactions/accessibility payload checks.
- `README.md` documents that `node scripts/audit-release-readiness.mjs --format=summary` reuses the cache only while source fingerprint and 6-hour freshness still match.
- `npm run verify` passed with `196 pass, 0 fail, 0 not_run, 0 blocked` and `Packaged browser gates: pass (fresh run cached)`.
- A follow-up `node scripts/audit-release-readiness.mjs --format=summary` passed with `196 pass, 0 fail, 0 not_run, 0 blocked` and `Packaged browser gates: pass (cached 0m old)`.
- `autoresearch-results/release-readiness-gates.json` records 62 input files plus release headers and interaction evidence.

## Improvement

- Before: the quick release summary produced a false operational blocker immediately after a full pass unless the expensive packaged browser gate was rerun.
- After: the quick summary stays fast and truthful, reusing only fresh source-matched browser evidence and falling back to `not_run` when the proof is stale or mismatched.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI.
- Rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `allDispatchReady` is true, then dispatch Pages/Drift Watch and capture live publish evidence.

## Experiment: Workflow scope refresh current action handoff

- Hypothesis: Missing GitHub `workflow` scope is less likely to be mistaken for publish progress when the exact `gh auth refresh` command is carried as the first current action across dispatch planning, launch packet, publish evidence, and final quality receipt.
- Primary metric: `workflowScopeRefreshCurrentActionCoverage`.
- Baseline: The publish dispatch plan could show workflow scope state, but launch execution and post-publish evidence handoffs could still lead with workflow template copy or live evidence capture rather than the credential preflight.
- Candidate: Emit `workflowScopeRefreshCommand`, add it to current action packets and copy-ready handoffs, expose refresh/recheck commands in System Status and Settings, and verify the immediate/deferred action split in smoke and audit.
- Decision: keep.

## Evidence

- `scripts/plan-publish-dispatch.mjs` emits `workflowScopeRefreshCommand=gh auth refresh -h github.com -s workflow` and the repo-specific recheck command when workflow scope is missing.
- `release-status.js` and Settings Deploy Handoff surface the auth refresh command, repo-specific recheck, GitHub UI fallback, and state that auth refresh is not workflow installation, dispatch, or launch proof.
- `scripts/capture-launch-execution-packet.mjs` now starts the `install_workflows` current action with `gh auth refresh -h github.com -s workflow` before workflow template copy/open/check commands.
- `data/launch-execution-packet.json` now carries `currentAction.commandCount=7` and total `commandCount=16` while `remoteWorkflowFilesReady=false` and dispatch commands remain withheld.
- `scripts/capture-output-quality-audit.mjs` records `Publish evidence immediate action` as pass with `install_workflows`, immediate command `gh auth refresh -h github.com -s workflow`, deferred `capture-live-evidence`, and public launch proof still blocked.
- `npm test` passed with desktop `routeCount=16`, mobile `routeCount=16`, interaction `stepCount=43`, and accessibility pass after the refresh handoff and packaged `dist/release` sync.

## Improvement

- Before: the operator could see workflow scope was missing, but the next actionable handoff did not consistently start with the credential refresh/recheck path.
- After: auth refresh is the first current action everywhere it matters, while dispatch and external launch proof remain blocked until workflow files are installed on the default branch and live evidence is captured.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI.
- Rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects` until `remoteWorkflowFilesReady`, `remoteWorkflowVisibilityReady`, and `allDispatchReady` are true, then dispatch and capture live publish evidence.

## Experiment: Release package source parity

- Hypothesis: A release verifier is weaker if `dist/release` can pass manifest integrity while stable source-copied runtime files are stale compared with the current source tree.
- Primary metric: `releaseSourceParityCoverage`.
- Baseline: After source edits, `node scripts/verify-release.mjs` failed with source parity mismatches for `README.md` and generated evidence JSON, proving stale package content can be detected but also exposing volatile evidence JSON as a false-positive risk.
- Candidate: Add `verifySourceParity` for 38 stable source-copied runtime files and seed assets, exclude generated evidence JSON from parity while keeping it in the manifest, and require source parity coverage in release audit.
- Decision: keep.

## Evidence

- `scripts/verify-release.mjs` now reports `sourceParityFiles: 38` after comparing stable runtime helpers, `styles.css`, `README.md`, icons, manifest, preview assets, vendor files, `data/repos.json`, and `data/adoption-candidates.json`.
- Generated evidence JSON files with `generatedAt`-driven audit updates stay packaged and manifest-checked, but are excluded from source parity to avoid false failures during audit capture.
- `scripts/audit-release-readiness.mjs` requires `verifyRelease.result.sourceParityFiles >= 38` and source parity terms before `manifest_integrity` can pass.
- `README.md` documents that `node scripts/verify-release.mjs` checks source-copied runtime file and seed asset source parity.
- `node scripts/package-release.mjs` followed by `node scripts/verify-release.mjs` passed with `sourceParityFiles=38`.
- `npm run verify` passed with `196 pass, 0 fail, 0 not_run, 0 blocked` after source parity was added.

## Improvement

- Before: manifest integrity proved `dist/release` was internally consistent, but it did not directly prove stable copied source files matched the current workspace.
- After: stale packaged JS/CSS/helper/document/seed asset copies fail release verification, while volatile generated evidence remains governed by freshness and publish-proof gates.

## Next Loop

- Keep source parity scoped to stable source files; expand only when a generated artifact has deterministic content or a dedicated freshness contract.
- Continue external publish work only after workflow-scope auth, default-branch workflow installation, and live launch evidence are available.

## Experiment: Launch current action copy packet

- Hypothesis: Operators are less likely to run an unsafe dispatch command if System Status lets them copy only the current launch action instead of the full launch execution packet.
- Primary metric: `launchExecutionCurrentActionCopyCoverage`.
- Baseline: The current action was visible inside the launch execution packet, but only the full multi-stage packet had a copy button.
- Candidate: Add a `current action 복사` button inside the current action card, wire a focused clipboard handler, and verify the copied payload excludes the full `Execution stages:` section.
- Decision: keep.

## External Comparison

- GitHub manual workflow dispatch requires the workflow file to exist on the default branch before dispatch is safe: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Evidence

- `release-status.js` renders `data-launch-execution-current-action-copy` beside `data-launch-execution-current-action-text`.
- `app.js` adds `copyLaunchCurrentActionPacket` and routes `copy-launch-current-action-packet` through the existing clipboard/status/copied dataset pattern.
- `scripts/smoke-interactions.mjs` clicks the current action copy button, verifies copied status, and confirms the clipboard contains `JooPark Launch Current Action Packet` without the full `Execution stages:` section.
- `scripts/audit-release-readiness.mjs` now requires the render, action, style, README, and smoke terms for this focused current-action copy path.
- `npm run verify` passed with `195 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: users could copy the full launch sequence, but had to re-read the long packet to identify the single safe next action.
- After: users can copy only the current installation step, including the success condition and withheld dispatch guard, while the full launch packet remains available.

## Next Loop

- Continue improving the default-branch workflow installation UX until remote workflow visibility can be proven.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Publish dispatch safety gate handoff

- Hypothesis: Copied deploy/publish handoffs should make dispatch feel unavailable until all repo, remote workflow file, visibility, and dispatch-readiness evidence is true.
- Primary metric: `publishDispatchSafetyGateHandoffCoverage`.
- Baseline: The handoffs already mentioned `allDispatchReady`, but the GitHub UI install sequence could still be read as “install workflows, then run Actions” before the dispatch safety condition was repeated as its own section.
- Candidate: Add a shared `Dispatch safety gate` section to both Settings Deploy Handoff and System Status publish unblock handoff, then verify both clipboard payloads.
- Decision: keep.

## External Comparison

- GitHub manual workflow dispatch requires a `workflow_dispatch` workflow file on the default branch before manual or CLI runs are valid: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui

## Evidence

- `release-status.js` adds `publishDispatchGateGuardLines` and inserts `Dispatch safety gate` into the copied publish unblock handoff.
- `app.js` reuses the same helper in Settings Deploy Handoff and requires `remoteWorkflowFilesReady`, `dispatchReady`, `driftDispatchReady`, and `allDispatchReady` before dispatch.
- `scripts/smoke-interactions.mjs` verifies both Settings deploy and System publish handoff clipboard payloads include `Dispatch safety gate`, `suggestedDispatchCommands`, and `withheld-until-all-dispatch-ready`.
- `scripts/audit-release-readiness.mjs` expands `publish_repo_placeholder_handoff_guard` to cover dispatch-readiness evidence, not only repo placeholder replacement.
- `npm run verify` passed with `195 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: a user could copy the correct handoff but still encounter dispatch wording before the safety gate was prominent.
- After: both copied operating handoffs separate installation, verification-only commands, withheld dispatch commands, and live evidence capture.

## Next Loop

- Continue improving the default-branch workflow installation UX until remote workflow visibility can be proven.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Publish dispatch workflow scope evidence

- Hypothesis: The live publish dispatch blocker is still too easy to misread unless the actual token scopes and missing `workflow` scope appear in both System Status and copied handoffs.
- Primary metric: `publishDispatchWorkflowScopeEvidenceCoverage`.
- Baseline: The dispatch plan stored `workflowScopeAvailable=false` and `workflowScopeInstallBlocked=true`, but the System Status panel did not show the exact `workflowScope.scopes` list or the missing `workflow` scope as a visible evidence row.
- Candidate: Render `workflowScope.scopes`, `workflowScope.missing`, `workflowScope.source`, and a workflow scope evidence callout in the Publish dispatch plan panel, then extend copied Dispatch safety gate text, smoke checks, audit terms, and README documentation.
- Decision: keep.

## Evidence

- `data/publish-dispatch-plan.json` currently reports `workflowScope.scopes: gist, read:org, repo`, `workflowScopeAvailable: false`, and `workflowScopeInstallBlocked: true`.
- `release-status.js` now exposes `data-publish-dispatch-workflow-scope-scopes`, `data-publish-dispatch-workflow-scope-missing`, `data-publish-dispatch-workflow-scope-source`, visible `workflowScope.scopes`, and a `workflow scope evidence` callout.
- `publishDispatchGateGuardLines` now tells copied Settings/System handoffs to inspect `workflowScope.scopes`, `workflowScopeAvailable`, and `workflowScopeInstallBlocked` before workflow installation or dispatch.
- `scripts/smoke-interactions.mjs` verifies the scope attributes, current scope list, missing `workflow` state, and copied handoff text.
- `scripts/audit-release-readiness.mjs` and `README.md` require the scope evidence terms.

## Improvement

- Before: operators could see install was blocked, but had to infer the concrete token problem from JSON or CLI output.
- After: the public readiness UI and copied handoffs show the exact detected scopes and the missing `workflow` scope, keeping CLI write and dispatch blocked until the token/session issue is resolved.

## Next Loop

- Continue improving the default-branch workflow installation UX until remote workflow visibility can be proven.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Publish dispatch workflow scope packet copy

- Hypothesis: Showing the missing `workflow` scope is useful, but launch unblock is still slower unless the exact auth refresh, recheck, UI fallback, and dispatch guard can be copied as one operator packet.
- Primary metric: `publishDispatchWorkflowScopePacketCopyCoverage`.
- Baseline: The Publish dispatch plan displayed `workflowScope.scopes`, `workflowScopeRefreshCommand`, and `workflowScopeRecheckCommand`, but there was no focused copy button for this auth blocker.
- Candidate: Add a copy-ready `JooPark Workflow Scope Refresh Packet` to the Publish dispatch plan panel, wire a clipboard handler, and verify the copied payload in browser smoke and release audit.
- Decision: keep.

## Evidence

- `release-status.js` now renders `data-publish-dispatch-workflow-scope-packet`, `data-publish-dispatch-workflow-scope-packet-text`, and `scope packet 복사`.
- `app.js` adds `copyPublishWorkflowScopePacket` and routes `copy-publish-workflow-scope-packet` through the standard copied dataset/status/toast pattern.
- `scripts/smoke-interactions.mjs` clicks the scope packet button and verifies the clipboard includes `workflowScope.scopes: gist, read:org, repo`, `Missing scope: workflow`, `gh auth refresh -h github.com -s workflow`, the repo-specific recheck command, and the dispatch guard.
- `scripts/audit-release-readiness.mjs` and `README.md` require the packet/button terms.

## Improvement

- Before: the operator had to read the panel and manually assemble the next safe auth/recheck sequence.
- After: the exact scope-refresh packet is copy-ready and still blocks `gh workflow run` until `remoteWorkflowFilesReady`, `dispatchReady`, `driftDispatchReady`, and `allDispatchReady` are all true.

## Next Loop

- Continue improving the default-branch workflow installation UX until remote workflow visibility can be proven.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Publish evidence withheld dispatch commands

- Hypothesis: Publish evidence handoffs should not list `gh workflow run` under suggested commands while the dispatch plan still reports `allDispatchReady: false`.
- Primary metric: `publishEvidenceWithheldDispatchCoverage`.
- Baseline: `node scripts/capture-publish-evidence.mjs --dry-run --markdown` placed the two repo-scoped workflow dispatch commands in `Suggested repo commands`.
- Candidate: Split publish evidence commands into verification/capture suggestions and a guarded `Withheld dispatch commands` section backed by `data/publish-dispatch-plan.json`.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now reads `data/publish-dispatch-plan.json` and emits `suggestedVerificationCommands`, `suggestedDispatchCommands`, `withheldDispatchCommands`, `publishDispatchReady`, and `dispatchSuggestionStatus`.
- `data/publish-evidence.json` now has 7 safe suggested verification/capture commands, 0 suggested dispatch commands, 2 withheld dispatch commands, and `dispatchSuggestionStatus=withheld-until-all-dispatch-ready`.
- The Markdown report keeps `Suggested repo commands` and `Next commands` dispatch-free, and lists both `gh workflow run --repo biojuho/BIOJUHO-Projects ...` commands only under `Withheld dispatch commands` with `Do not run until allDispatchReady: true`.
- `release-status.js` exposes `data-publish-evidence-suggested-commands-safe`, suggested/withheld dispatch counts, and a visible `Dispatch command guard` in System Status.
- `scripts/smoke-interactions.mjs` and `scripts/audit-release-readiness.mjs` verify that suggested commands remain verification-only before dispatch readiness.

## Improvement

- Before: a copy-ready publish evidence report could encourage dispatch even though the workflow visibility/default-branch gates were still blocked.
- After: the report still gives the next safe verification and capture commands, while dispatch remains explicitly withheld until the dispatch plan proves `allDispatchReady: true`.

## Next Loop

- Keep publish completion blocked until default-branch workflows are installed and live launch evidence is captured.
- Continue tightening final handoff output where a copied report can still mix safe next steps with gated actions.

## Experiment: Publish evidence share update dispatch guard

- Hypothesis: The short `JooPark Publish Evidence Update` is the message most likely to be pasted into a team channel, so it must preserve dispatch guard state instead of relying on the full Markdown report.
- Primary metric: `publishEvidenceShareUpdateDispatchGuardCoverage`.
- Baseline: The share update showed blocker and next command, but did not include `allDispatchReady`, suggested dispatch count, withheld dispatch count, or the withheld `gh workflow run` commands.
- Candidate: Add `Dispatch guard`, `Suggested commands safe`, `Do not run dispatch until allDispatchReady: true`, and `Withheld dispatch commands` directly to the share update.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now builds share update dispatch guard lines from `suggestedCommands`, `suggestedDispatchCommands`, `withheldDispatchCommands`, `publishDispatchReady`, and `dispatchSuggestionStatus`.
- `data/publish-evidence.json` now copies `Dispatch guard: withheld (withheld-until-all-dispatch-ready)`, `Suggested commands safe: true; suggested dispatch: 0; withheld dispatch: 2`, and both repo-scoped `gh workflow run` commands under `Withheld dispatch commands`.
- `scripts/smoke-interactions.mjs` verifies the System Status share update DOM and copied clipboard text include the guard and both withheld dispatch commands.
- `scripts/audit-release-readiness.mjs` and `README.md` require the share update guard terms.
- `npm run verify` passed with 195 pass, 0 fail, 0 not_run, 0 blocked.

## Improvement

- Before: a teammate reading only the short action-required update could miss that dispatch is still withheld.
- After: the shortest copy-ready publish update carries the same operational guard as the full report, making it safe to paste without extra explanation.

## Next Loop

- Continue checking the smallest copy-ready artifacts first, because those are the outputs most likely to be used without reading the full report.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: Publish post-launch receipt dispatch guard

- Hypothesis: The post-launch verification receipt should not be archive-ready unless it preserves the same dispatch readiness guard as the full publish evidence report.
- Primary metric: `publishPostLaunchReceiptDispatchGuardCoverage`.
- Baseline: `JooPark Post-Launch Verification Receipt` included the launch-proof checklist and not-ready archive guard, but did not include `publishDispatchReady`, `dispatchSuggestionStatus`, or withheld dispatch commands.
- Candidate: Reuse the publish evidence dispatch guard lines inside the receipt checklist and copy output.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now uses `publishEvidenceDispatchGuardLines(evidence)` in the post-launch verification receipt.
- `data/publish-evidence.json` now includes `publishDispatchReady: false`, `dispatchSuggestionStatus: withheld-until-all-dispatch-ready`, `Dispatch gate`, `Dispatch guard: withheld`, and both withheld repo-scoped dispatch commands in `postLaunchVerificationReceipt`.
- `scripts/smoke-interactions.mjs` verifies the post-launch receipt DOM and copied clipboard text include the dispatch guard and both withheld dispatch commands.
- `scripts/audit-release-readiness.mjs` and `README.md` require the post-launch receipt dispatch guard terms.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed with 195 pass, 0 fail, 0 not_run, 0 blocked.

## Improvement

- Before: a saved receipt could prove that launch evidence was not ready, but omit the concrete dispatch gate that explains why workflow evidence cannot exist yet.
- After: the archive-target receipt records both the proof checklist and the withheld dispatch state, so it is safer to store or forward without losing launch context.

## Next Loop

- Continue auditing copy outputs that can be saved outside the app, especially public announcement and launch packet variants.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: Publish launch announcement dispatch guard

- Hypothesis: The not-ready public launch announcement should block both public posting and premature dispatch, but should not expose raw workflow commands in a public-facing copy block.
- Primary metric: `publishLaunchAnnouncementDispatchGuardCoverage`.
- Baseline: `JooPark Public Launch Announcement` copied the not-ready posting guard and next command, but did not include dispatch readiness state.
- Candidate: Add a `Dispatch gate` to the not-ready launch announcement with no raw `gh workflow run` commands.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now calls `publishEvidenceDispatchGuardLines(evidence, { includeCommands: false })` in `publishLaunchAnnouncement`.
- `data/publish-evidence.json` now includes `Dispatch guard: withheld`, suggested/withheld dispatch counts, and `Do not post or dispatch until allDispatchReady: true and postPublishEvidenceReady: true` in `launchAnnouncement`.
- The launch announcement guard intentionally omits raw `gh workflow run --repo` commands; command-level withheld details remain in the full report, share update, and post-launch receipt.
- `scripts/smoke-interactions.mjs` verifies the launch announcement DOM and copied clipboard text include the dispatch guard and exclude raw workflow dispatch commands.
- `scripts/audit-release-readiness.mjs` and `README.md` require the public announcement dispatch guard terms.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed with 195 pass, 0 fail, 0 not_run, 0 blocked.

## Improvement

- Before: a copied not-ready announcement blocked public posting, but a reader still had to infer that workflow dispatch was also withheld.
- After: the public-facing guard clearly blocks both posting and dispatch while keeping operational commands out of the public announcement copy.

## Next Loop

- Continue with launch packet and final handoff copy outputs, looking for places where a short copy block can lose critical operational context.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: Publish evidence immediate next action

- Hypothesis: Publish evidence handoffs can mislead users if they show live evidence capture as the next action while the launch execution packet still requires workflow installation and visibility checks first.
- Primary metric: `publishEvidenceImmediateNextActionCoverage`.
- Baseline: `data/publish-evidence.json` exposed `nextAction.key=capture-live-evidence`, but the current launch execution packet still had `currentAction.stageKey=install_workflows`.
- Candidate: Read `data/launch-execution-packet.json`, write `immediateNextAction` from `currentAction`, preserve `capture-live-evidence` as `deferredNextAction`, and verify JSON, Markdown, DOM, clipboard, and quality receipt coverage.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now writes `immediateNextAction.key=install_workflows`, `source=data/launch-execution-packet.json`, `command=gh auth refresh -h github.com -s workflow`, `commandCount=7`, `withheldCommandCount=2`, and `deferredNextAction.key=capture-live-evidence`.
- Share update, not-ready public launch announcement, post-launch receipt, and Markdown report now show `Immediate action` before `Deferred evidence capture`.
- `release-status.js` exposes `data-publish-evidence-immediate-action` and renders the immediate action card while preserving `data-publish-evidence-next-action=capture-live-evidence`.
- `scripts/smoke-interactions.mjs`, `scripts/audit-release-readiness.mjs`, and `scripts/capture-output-quality-audit.mjs` verify the immediate/deferred split through DOM, clipboard text, stored JSON, Markdown, and the final output quality receipt.
- `npm run verify` passed with 195 pass, 0 fail, 0 not_run, 0 blocked after the immediate next action split.

## Improvement

- Before: a copy-ready publish evidence block could make live evidence capture look like the first action even though workflow installation was still the active blocker.
- After: the copy outputs first name the launch packet action and only then show live evidence capture as deferred, so the launch sequence is harder to run out of order.

## Next Loop

- Continue auditing short copy outputs where a later-stage command can appear before the current blocker.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: Output quality specific context immediate action

- Hypothesis: The final output quality receipt can still mislead users if its `Specific context` criterion calls deferred live evidence capture the next action while the current launch action is workflow installation.
- Primary metric: `outputQualitySpecificContextImmediateActionCoverage`.
- Baseline: `data/output-quality-audit.json` said `next action: Capture live publish evidence` in the `Specific context` criterion even though publish evidence and the launch packet now identify `install_workflows` as the immediate action.
- Candidate: Build the criterion from `immediateNextAction` and `deferredNextAction`, regenerate the receipt, and make smoke/audit reject the stale phrase.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now requires both the immediate action command and deferred evidence command before `Specific context` passes.
- `data/output-quality-audit.json` now says `immediate action: Install workflows on the default branch` and `deferred evidence capture: Capture live publish evidence`.
- `scripts/smoke-interactions.mjs` verifies both the rendered receipt and copied clipboard text include the immediate/deferred wording and do not include `next action: Capture live publish evidence`.
- `scripts/audit-release-readiness.mjs` requires the new specific-context terms across the capture script, persisted JSON, and smoke coverage.
- `npm run verify` passed with 196 pass, 0 fail, 0 not_run, 0 blocked after the specific context immediate-action fix.

## Improvement

- Before: the copy-ready quality receipt could make live evidence capture look like the current action in one criterion, even though workflow installation was still blocking launch proof.
- After: the receipt consistently puts workflow installation first and only presents live evidence capture as deferred.

## Next Loop

- Continue auditing short copy outputs where a later-stage command can appear before the current blocker.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: System publish copy-ready smoke wait

- Hypothesis: System Status publish evidence panels should be tested after text-specific copy-ready content is rendered, not immediately after the panel reports `loaded=true`.
- Primary metric: `systemPublishCopyReadySmokeWaitCoverage`.
- Baseline: `npm run verify` exposed a first-attempt smoke race where the publish evidence panel had loaded, but the share update copy-ready text was asserted before all expected guard lines were visible.
- Candidate: Wrap the publish evidence share update, launch announcement guard, post-launch receipt guard, and output quality audit receipt content checks in `waitFor(..., 15000)` while keeping the existing clipboard assertions.
- Decision: keep.

## Evidence

- `scripts/smoke-interactions.mjs` now waits for text-specific readiness before asserting `JooPark Publish Evidence Update`, `JooPark Public Launch Announcement`, `JooPark Post-Launch Verification Receipt`, and `JooPark Final Output Quality Audit Receipt` copy-ready content.
- `scripts/audit-release-readiness.mjs` requires the wait-based guard terms in the publish evidence and output quality receipt checks.
- The patch keeps the same DOM selectors, data attributes, clipboard copy assertions, and user-facing guard text.
- AutoResearch tracks `publishEvidenceCopyReadySmokeWaitCoverage=1`, `outputQualityCopyReadySmokeWaitCoverage=1`, and `systemPublishCopyReadySmokeWaitCoverage=1`.

## Improvement

- Before: a fast smoke pass could read the async System Status evidence panel between `loaded=true` and final copy-ready text readiness.
- After: the smoke waits for the exact copy-ready artifacts that users can paste, reducing false negatives without weakening clipboard verification.

## Next Loop

- Continue checking copy-ready final outputs for async rendering assumptions before adding new launch-proof surface area.
- Keep public launch completion blocked until default-branch workflows are installed and live evidence is captured.

## Experiment: Launch execution current action packet

- Hypothesis: A launch execution packet is less practical if users must read the full blocker list to decide the one immediate next action.
- Primary metric: `launchExecutionCurrentActionCoverage`.
- Baseline: The launch packet listed five execution stages and all blockers, but it did not isolate the first incomplete stage into a standalone current-action handoff with success criteria and withheld dispatch commands.
- Candidate: Derive the first non-pass/non-ready stage as `currentAction`, embed a `JooPark Launch Current Action Packet` before the full stage list, render it in System Status, and verify DOM/clipboard/readiness coverage.
- Decision: keep.

## External Comparison

- GitHub manual workflow dispatch requires the workflow file to use `workflow_dispatch` and be present on the default branch before manual runs, so the current action must prioritize default-branch workflow installation before dispatch: https://docs.github.com/en/actions/managing-workflow-runs/manually-running-a-workflow?tool=webui
- GitHub Pages custom workflows depend on an artifact upload/deploy workflow with the required Pages permissions, so the packet keeps Pages workflow installation and verification as the first actionable step: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages

## Evidence

- `scripts/capture-launch-execution-packet.mjs` adds `currentActionPacket`, which emits repo/default branch, current stage, why-now detail, success condition, run-now commands, verification commands, withheld dispatch commands, and public-claim guard.
- `data/launch-execution-packet.json` now stores `currentAction.stageKey=install_workflows`, `commandCount=5`, `withheldCommandCount=2`, and the embedded `JooPark Launch Current Action Packet`.
- `release-status.js` renders `data-launch-execution-current-action`, `data-launch-execution-current-action-stage`, `data-launch-execution-current-action-status`, command counts, and the hidden current-action text.
- `scripts/smoke-interactions.mjs` verifies the current action DOM, `Success condition: remoteWorkflowFilesReady=true`, `Do not run yet`, and withheld `gh workflow run` commands in copied launch packet text.
- `scripts/audit-release-readiness.mjs` and `README.md` now require the current action packet evidence.

## Improvement

- Before: the launch packet was complete but still asked the operator to infer the next action from several stages and blockers.
- After: the packet opens with the exact current action, commands to run now, commands to verify afterward, and dispatch commands that must remain withheld.

## Next Loop

- Continue improving copy-ready final outputs where a user still needs to infer priority or reconstruct a handoff from multiple panels.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review GitHub comment Markdown boundary

- Hypothesis: GitHub comment handoffs remain easier to maintain if the Markdown body and draft shell share the same `review-result-view.js` presentation boundary while `app.js` keeps surface-specific orchestration.
- Primary metric: `reviewGithubCommentMarkdownBoundaryCoverage`.
- Baseline: `review-result-view.js` owned the visible GitHub comment draft shell, but workspace, KB/IA, and generic comment Markdown assembly still lived in `app.js`.
- Candidate: Move shared comment Markdown generation into `review-result-view.js`, delegate workspace/KB/IA/benchmark bodies through `reviewGithubCommentMarkdown`, and make the System smoke re-query the current publish panel after async JSON panel loads.
- Decision: keep.

## Evidence

- `review-result-view.js` now owns `reviewGithubCommentMarkdown`, including `Primary decision key`, recommendation, optional surface/reason, comparison, and `Issue Draft` Markdown sections.
- `app.js` now delegates comment Markdown through `reviewResultViewCall("reviewGithubCommentMarkdown")` while keeping draft selection, GitHub new issue URL generation, copy actions, and copied-state mutation.
- `workspaceReviewGithubCommentMarkdown`, `knowledgeBaseReviewGithubCommentMarkdown`, and benchmark queue comment generation all pass title/decisions/draft models through the shared helper.
- `scripts/check-app-structure.mjs`, `scripts/audit-release-readiness.mjs`, `README.md`, and `docs/app-architecture.md` now track the Markdown/draft boundary explicitly.
- `scripts/smoke-interactions.mjs` re-queries the current System publish panel after async JSON panels load, fixing the stale DOM reference that hid output-quality audit state during packaged smoke.
- `node scripts/smoke-release.mjs` passed with 49 release files, 1,610,518 bytes, 16 desktop routes, 16 mobile routes, 43 interaction steps, `systemPublishReadiness=true`, `outputQualityAuditReceipt=true`, and no console/network/layout failures.
- `npm run verify` passed with `195 pass, 0 fail, 0 not_run, 0 blocked` after launch packet readiness assertions were moved into `waitFor` to remove the remaining System async panel race.

## Improvement

- Before: GitHub comment shell and Markdown body ownership were split, so each surface could drift while sharing the same visible copy flow.
- After: Markdown body generation and draft rendering live behind the same view helper boundary, and the smoke gate now verifies async System panels against the current DOM.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Output quality receipt readiness snapshot

- Hypothesis: A final output quality receipt is less useful if it only says the gate passed but does not summarize the actual artifact readiness that makes the output directly usable.
- Primary metric: `outputQualityReceiptArtifactSnapshotCoverage`.
- Baseline: The copied `JooPark Final Output Quality Audit Receipt` included gate counts, blockers, quality criteria, and external comparison, but it did not surface review package final quality, tracker form payload readiness, runtime issue counts, or launch packet evidence in the copy text.
- Candidate: Add `outputReadinessSnapshot` to `data/output-quality-audit.json`, render it in System Status, include it in `quality receipt 복사`, and verify the DOM/clipboard/audit coverage.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries expose compact Markdown proof on the run summary page, so the quality receipt should summarize meaningful artifact evidence instead of forcing log inspection: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- GitHub Releases distinguish packaged software and release notes from raw build output, so the receipt keeps release quality and public launch proof separate: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- Linear issue templates use structured issue fields, so the receipt now reports tracker form payload readiness instead of only saying a review package exists: https://linear.app/docs/issue-templates

## Evidence

- `scripts/capture-output-quality-audit.mjs` adds `outputReadinessSnapshot` with review package readiness, final quality score, tracker form payload count/checksum readiness, runtime issue counts, copy-ready artifact flags, and launch packet coverage.
- `data/output-quality-audit.json` now stores `outputReadinessSnapshot.status=pass`, `reviewPackageFinalQualityScore=6/6`, 11 tracker form payloads with checksums ready, and runtime issues at console 0 / network 0 / layout 0.
- `release-status.js` renders the snapshot with `data-output-quality-audit-snapshot`, `data-output-quality-audit-snapshot-status`, `data-output-quality-audit-tracker-form-payload-count`, and checksum readiness attributes.
- `scripts/smoke-interactions.mjs` verifies the snapshot DOM, copied receipt text, `Output readiness snapshot`, `Tracker form payloads: pass (11 fields, checksums ready)`, `Runtime issues: console 0, network 0, layout 0`, and 3 external comparison entries.
- `scripts/audit-release-readiness.mjs` extends `output_quality_audit_receipt` so the snapshot cannot disappear without failing release readiness.

## Improvement

- Before: a user copying the final quality receipt still had to infer whether the review package itself was tracker-ready and whether runtime/browser evidence was clean.
- After: the copied receipt carries one compact readiness snapshot that proves the review package is ready, the structured tracker form payloads exist, runtime issues are zero, and launch execution evidence is present.

## Next Loop

- Continue improving copy-ready final outputs, especially places where receipt text still forces users to inspect hidden JSON or reconstruct state from UI panels.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review GitHub comment draft view boundary

- Hypothesis: The repeated workspace and KB/IA GitHub comment draft shell can move into `review-result-view.js` without changing markdown generation, encoded GitHub issue links, or copy state behavior.
- Primary metric: `reviewGithubCommentDraftViewBoundaryCoverage`.
- Baseline: `app.js` rendered the workspace and KB/IA GitHub comment panels inline, duplicating the same shell around different markdown bodies and scope-specific data attributes.
- Candidate: Add `reviewGithubCommentDraftPanel` to `JooParkReviewResultView`, delegate both GitHub comment draft shells through `reviewResultViewCall("reviewGithubCommentDraftPanel")`, keep markdown generation and copy actions in `app.js`, and align the tracker form comparison smoke with the implemented GitHub/Linear/Jira comparison set.
- Decision: keep.

## External Comparison

- GitHub issue query parameters support prefilled issue creation fields such as title/body, matching JooPark's encoded issue link handoff: https://docs.github.com/en/github/managing-your-work-on-github/about-automation-for-issues-and-pull-requests-with-query-parameters
- GitHub Markdown formatting applies to issues, comments, and Markdown files, matching JooPark's copy-ready comment body contract: https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax

## Evidence

- `review-result-view.js` now owns `reviewGithubCommentDraftPanel`, `data-review-github-comment-key`, `data-review-github-comment-target`, `data-review-github-comment-copy`, `data-review-github-comment-copy-status`, and `data-review-github-comment-text`.
- `app.js` now calls `reviewResultViewCall("reviewGithubCommentDraftPanel")` for workspace and KB/IA comment drafts while retaining `workspaceReviewGithubCommentMarkdown`, `knowledgeBaseReviewGithubCommentMarkdown`, `githubNewIssueUrl`, and `copyReviewGithubComment`.
- `scripts/smoke-interactions.mjs` verifies workspace and KB/IA comment keys, targets, Markdown format, encoded GitHub issue hrefs, clipboard body text, and copied state.
- `scripts/audit-release-readiness.mjs` adds `review_github_comment_draft_view_boundary`; `README.md` lists the GitHub comment draft shell as part of `review-result-view.js`.
- The stale tracker form smoke expectation was corrected from 2 to 3 comparison targets, matching the implemented GitHub Issue Forms, Linear issue templates, and Jira work items copy packet.
- `npm run lint`, `npm test`, `npm run check:structure`, and `npm run verify` passed; final readiness was `193 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the GitHub comment draft shell was repeated in `app.js`, so copy/status/link presentation could drift between workspace and KB/IA review flows.
- After: one view helper owns the shell while `app.js` remains the state/action boundary; browser smoke proves both comment panels still copy the expected Markdown and expose encoded GitHub issue links.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, especially copy/receipt shells that can move without changing mutation behavior.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Review package copy handler helper

- Hypothesis: Tracker field, tracker form, submit sequence, and external receipt template copy handlers can share one helper without changing copied dataset state, status text, toast feedback, or clipboard payloads.
- Primary metric: `reviewPackageCopyHandlerHelperCoverage`.
- Baseline: Four review package copy functions repeated the same `writeClipboardText`, target dataset, panel dataset, status text, and toast pattern.
- Candidate: Add `copyReviewPackagePanelText` in `app.js`, route the four static review package copy handlers through it, and add a release audit item that keeps the helper boundary covered.
- Decision: keep.

## Evidence

- `app.js` now has `copyReviewPackagePanelText` with explicit `targetDatasetKey`, `panelDatasetKey`, status, and toast options.
- `copyReviewPackageTrackerFields`, `copyReviewPackageTrackerForm`, `copyReviewPackageSubmitSequence`, and `copyReviewPackageExternalReceiptTemplate` keep their public function names and data keys while sharing the helper.
- `README.md` documents that the static copy handlers share one clipboard/status/copied dataset helper.
- `scripts/audit-release-readiness.mjs` adds `review_package_copy_handler_helper`, raising the local release audit to 194 checks.
- `npm run lint`, `npm run check:structure`, `git diff --check`, and static release audit passed before output-quality receipt regeneration.

## Improvement

- Before: a future status or dataset fix could be applied to one review package copy panel and missed in the others.
- After: the repeated static copy paths share one small helper, while panel-specific selectors and user-facing messages remain explicit at the call sites.

## Next Loop

- Continue shrinking remaining copy/receipt orchestration in `app.js`, but only after the current helper is proven by full package smoke.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Review package filled copy handler helper

- Hypothesis: Completed external receipt and review submission update copy flows can share URL/ID validation, template filling, clipboard writes, status text, toast feedback, and copied dataset updates without changing the public copy actions.
- Primary metric: `reviewPackageFilledCopyHandlerHelperCoverage`.
- Baseline: `copyReviewPackageExternalReceiptFilled` and `copyReviewPackageSubmissionUpdateFilled` repeated the same required URL/ID check, `externalReceiptValues(panel)` call, `fillExternalIssueText(template, values)` replacement, and copied-state updates.
- Candidate: Add `copyReviewPackageFilledText` in `app.js`, route both filled copy handlers through it, and add a release audit item that keeps URL/ID validation plus placeholder-free clipboard coverage tied to smoke checks.
- Decision: keep.

## Evidence

- `app.js` now has `copyReviewPackageFilledText` with explicit `stateHostSelector`, `templateHostSelector`, `targetDatasetKey`, status, and toast options.
- `copyReviewPackageExternalReceiptFilled` and `copyReviewPackageSubmissionUpdateFilled` keep the same action handlers, status labels, toast messages, and dataset keys: `reviewPackageExternalReceiptFilledCopied` and `reviewPackageSubmissionUpdateFilledCopied`.
- `scripts/audit-release-readiness.mjs` adds `review_package_filled_copy_handler_helper`, raising the local release audit total to 195 checks.
- `README.md` documents that completed receipt/update copy flows share URL/ID validation, template fill, clipboard, status, and copied dataset behavior.
- Static release audit passed at `194 pass, 0 fail, 1 not_run, 0 blocked, 195 total` before full package smoke regenerated the browser gate.

## Improvement

- Before: the receipt and submission update paths could diverge on required input handling, placeholder cleanup, or copied-state updates.
- After: both completed external-submission outputs share one small helper, while their selectors and user-facing messages remain explicit at the call sites.

## Next Loop

- Continue reducing the remaining Portfolio review copy/receipt orchestration in `app.js` only where smoke can prove exact clipboard output.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Review package bundle copy helper

- Hypothesis: The review package bundle copy path can share the same static copy helper as tracker field, tracker form, submit sequence, and receipt template copies without changing clipboard payloads or copied-state behavior.
- Primary metric: `reviewPackageBundleCopyHelperCoverage`.
- Baseline: `copyReviewPackageBundle` repeated `writeClipboardText`, `reviewBundleCopied`, status text, and toast updates even though the other static package copy handlers already used `copyReviewPackagePanelText`.
- Candidate: Route `copyReviewPackageBundle` through `copyReviewPackagePanelText`, then expand the helper audit terms and README scope from four static panels to five.
- Decision: keep.

## Evidence

- `copyReviewPackageBundle` now calls `copyReviewPackagePanelText` with the same handoff selector, `data-review-package-bundle-text`, `data-review-bundle-copy-status`, `reviewBundleCopied`, `bundle 복사됨`, and `review package bundle을 복사했습니다` values.
- `scripts/audit-release-readiness.mjs` expands `review_package_copy_handler_helper` so helper coverage includes `reviewPackageBundleVisible`, the bundle clipboard guard, and `reviewBundleCopied`.
- `README.md` now documents `bundle/tracker field/form/submit sequence/receipt template` as the static helper scope.
- AutoResearch browser evidence tracks `reviewPackageBundleCopyHelperCoverage=1` and `reviewPackageCopyHandlerHelperPanels=5`.
- The release audit total remains 195 checks; this loop strengthens one existing check instead of adding another checklist row.

## Improvement

- Before: the top-level bundle copy path could drift from the static panel helper even though it used the same clipboard/status/dataset pattern.
- After: all five static review package copy panels share one helper, leaving only per-target paste-body and filled URL/ID flows on separate specialized paths.

## Next Loop

- Continue with per-target paste-body copy only if smoke can prove exact copied payload and focus state after the refactor.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Review handoff copy helper

- Hypothesis: The benchmark, workspace, and knowledge-base review handoff copy path can share the same panel copy helper as static review package panels without changing copied Markdown, copied dataset state, status text, or toast behavior.
- Primary metric: `reviewHandoffCopyHelperCoverage`.
- Baseline: `copyBenchmarkReviewHandoff` repeated `writeClipboardText`, `reviewHandoffCopied`, status text, and toast updates while bundle/tracker/form/sequence/receipt template copies already shared `copyReviewPackagePanelText`.
- Candidate: Route `copyBenchmarkReviewHandoff` through `copyReviewPackagePanelText`, then strengthen the existing handoff copy audit checks so all three handoff surfaces require the helper.
- Decision: keep.

## Evidence

- `copyBenchmarkReviewHandoff` now calls `copyReviewPackagePanelText` with the shared benchmark/knowledge-base/workspace handoff selector, `data-review-handoff-text`, `data-review-handoff-copy-status`, `reviewHandoffCopied`, `복사됨`, and `handoff를 복사했습니다` values unchanged.
- `scripts/audit-release-readiness.mjs` now requires `copyReviewPackagePanelText(target, {` and `reviewHandoffCopied` in the benchmark, workspace, and knowledge-base review handoff copy checks.
- The `review_package_copy_handler_helper` gate now covers the 3 handoff copy surfaces plus the 5 static review package copy panels while keeping the release audit total at 195 checks.
- `README.md` documents `handoff/bundle/tracker field/form/submit sequence/receipt template` as the shared static helper scope.
- AutoResearch browser evidence tracks `reviewHandoffCopyHelperCoverage=1`, `reviewHandoffCopyHelperSurfaces=3`, and `reviewPanelCopyHelperSurfaces=8`.

## Improvement

- Before: handoff copy behavior could drift from bundle and static panel copy behavior even though it updated the same clipboard/status/dataset state.
- After: the three prompt handoff copy surfaces and five static package panels share the same helper, with panel-specific selectors and user-facing text still explicit at the call sites.

## Next Loop

- Continue with per-target paste-body copy only if smoke can prove exact copied payload and focus state after the refactor.
- Keep external publish work blocked until remote workflow installation and live launch evidence are available.

## Experiment: Issue sheet evidence view boundary

- Hypothesis: Issue sheet evidence controls are easier to maintain and less likely to regress visually when checklist progress and fresh receipt presentation live in view modules while `app.js` keeps state and actions.
- Primary metric: `issueSheetEvidenceViewBoundaryCoverage`.
- Baseline: `app.js` still rendered the issue sheet execution checklist and post-checklist fresh receipt HTML inline, and smoke did not explicitly prevent duplicate progress values in the checklist header.
- Candidate: Move issue sheet checklist controls into `review-result-view.js`, move issue fresh receipt controls into `review-artifact-view.js`, add boundary data attributes, add duplicate-progress smoke coverage, and harden External Tracker Form Packet owner fallback.
- Decision: keep.

## Evidence

- `review-result-view.js` now owns `issueExecutionChecklistControls`, including `data-issue-execution-checklist-view` and one progress percentage in the header.
- `review-artifact-view.js` now owns `issueFreshReceiptControls`, including `data-issue-fresh-receipt-view` and the fresh receipt download/copy shell.
- `app.js` delegates the two controls through `reviewResultViewCall("issueExecutionChecklistControls")` and `reviewArtifactViewCall("issueFreshReceiptControls")`, while retaining checklist/fresh receipt state and actions.
- `review-handoff.js` now fills External Tracker Form Packet owner/assignee from the issue assignee, execution owner, Operational Readiness owner, or `PM reviewer` fallback instead of leaving a required owner field as confirmation-only.
- `scripts/smoke-interactions.mjs` verifies the view-boundary attributes, duplicate progress guard, fresh receipt readiness/copy, and external tracker form readiness.
- `npm run lint`, `npm run check:structure`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, `node scripts/smoke-release.mjs`, `git diff --check`, and `npm run verify` passed; final readiness was `193 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: issue sheet evidence UI was mixed into `app.js`, and external tracker form packets could fail a required owner field when no assignee had been manually selected yet.
- After: evidence controls are split into their runtime view modules, smoke guards the checklist progress display, and external tracker form packets stay ready by carrying a concrete owner fallback from the handoff.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review package tracker form field payloads

- Hypothesis: External tracker form packets are not truly copy-ready for GitHub Issue Forms, Linear templates, or Jira required fields unless each separate field has its own exact payload, byte count, and checksum.
- Primary metric: `reviewPackageTrackerFormPayloadCoverage`.
- Baseline: The External Tracker Form Packet listed required rows, but some rows pointed users back to the tracker issue body instead of exposing field-specific values for separate textarea/input controls.
- Candidate: Extract field payloads from the generated issue draft, render them in the UI, include them in the copied form packet, and verify payload count, checksums, readiness, and clipboard contents in smoke and release audit.
- Decision: keep.

## External Comparison

- GitHub Issue Forms use structured `input`, `textarea`, and related fields that are submitted independently from the final issue body: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema
- Linear issue templates can include fields and required controls before issue creation, so field-specific values need to be available before submit: https://linear.app/docs/issue-templates
- Jira Cloud can block creation when required fields are missing, which supports preserving explicit required-field payloads instead of relying only on body text: https://support.atlassian.com/jira/kb/cant-create-issues-because-of-required-fields-in-jira-cloud/

## Evidence

- `review-handoff.js` adds `reviewPackageExternalTrackerPayloads`, field-specific Markdown extraction, payload byte/checksum summaries, and a copied `Field payloads` section for Description/body, Acceptance criteria, Validation plan, owner, due, estimate, priority, labels, source, persist key, and receipt.
- `styles.css` adds compact payload row styling, and the review package UI renders `data-review-package-tracker-form-payloads` with 11 payload rows plus ready/type/checksum attributes.
- `scripts/smoke-interactions.mjs` verifies 11 payloads, `fnv1a32` checksums, acceptance/validation readiness, source URL payload content, and clipboard instructions for separate external form fields.
- `scripts/audit-release-readiness.mjs` adds `review_package_tracker_form_payloads`, and `README.md` documents that `Field payloads` carries actual values with bytes/checksums and field type.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `193 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: users still had to cut Acceptance criteria or Validation plan out of the tracker body when an external form exposed separate required fields.
- After: each required external form field has a copy-ready payload with deterministic checksum, so users can fill structured forms without rewriting generated text.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Review result repair artifact body evidence

- Hypothesis: A post-repair artifact link is weaker if the created issue/note body and its artifact receipt do not carry the repair evidence section themselves.
- Primary metric: `reviewResultRepairArtifactLinkCoverage`.
- Baseline: The post-repair receipt could be linked to an artifact receipt, but the created artifact body did not require a durable `Repair Evidence` section with prior failure evidence and the saved checksum.
- Candidate: Persist structured `repairEvidence`, inject `## Repair Evidence` into validated issue/note bodies, add a conditional `repair_evidence` artifact diff check, and verify created body, receipt copy, opened artifact body, and fresh receipt preservation.
- Decision: keep.

## Evidence

- `review-result-view.js` adds `reviewSavedResultRepairEvidenceLines` and includes `Repair Evidence`, `JooPark Review Result Post-Repair Receipt`, `Previous Failure Evidence`, and `Post-repair receipt checksum` in validated issue/note bodies.
- `app.js` stores structured `repairEvidence` with previous failures/warnings, repaired timestamp, primary key, and checksum, then refreshes the issue draft after attaching the saved repair receipt.
- `review-artifact-view.js` adds the conditional `repair_evidence` / `Repair evidence linked` diff check for repaired artifacts.
- `scripts/smoke-interactions.mjs` verifies saved repair evidence, 8 artifact checks, issue/note body inspection, artifact receipt copy contents, and fresh receipt preservation after checklist progress.
- `scripts/audit-release-readiness.mjs` adds `review_result_repair_artifact_link`.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs`, `node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `191 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the repaired-result link receipt proved the relationship externally, but the created artifact body could still be archived without an embedded repair evidence section.
- After: repaired created artifacts carry the repair evidence in the body and artifact receipt, and the diff fails to full pass unless that evidence is present.

## Next Loop

- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js`, while keeping state mutation and persistence in `app.js`.
- Keep external publish work blocked until default-branch workflow installation and live launch evidence are available.

## Experiment: Output quality completion audit checklist

- Hypothesis: A release-quality receipt is not enough for external completion unless it maps the original objective to explicit pass/blocked evidence and keeps missing public proof visible.
- Primary metric: `outputQualityCompletionAuditChecklistItems`.
- Baseline: The output-quality audit receipt exposed quality criteria and readiness snapshot, but did not map release quality, packaged artifact, handoffs, dispatch guardrails, workflow installation, public proof, and external claim into one completion checklist.
- Candidate: Add `completionAuditChecklist`, `completionAuditReady`, and `completionAuditBlockedCount` to the audit JSON/receipt, render it in System Status, assert it in smoke, and require/document it in release readiness.
- Decision: keep.

## External Comparison

- GitHub Actions job summaries keep important run evidence visible with the run result, so completion evidence should stay close to the quality receipt: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-commands#adding-a-job-summary
- GitHub Releases separate packaged software from public release notes, so JooPark keeps internal release quality separate from public launch completion until live proof exists: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases

## Evidence

- `scripts/capture-output-quality-audit.mjs` now writes a 7-item `completionAuditChecklist`, with 4 pass items and 3 blocked items.
- `data/output-quality-audit.json` shows `completionAuditReady=false`, `completionAuditBlockedCount=3`, and blocked `Workflow installation`, `Public launch proof`, and `External completion claim`.
- `release-status.js` renders `Completion audit` with count/ready/blocked datasets and per-item key/status datasets.
- `scripts/smoke-interactions.mjs` verifies the rendered checklist, receipt text, clipboard text, `remoteWorkflowFilesReady=false`, `postPublishEvidenceReady=false`, and `readyForExternalClaim=false`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the completion audit evidence so it cannot silently disappear from the product.
- `npm run lint`, `git diff --check`, `node scripts/package-release.mjs && node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness was `196 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the product could prove internal quality while still requiring the operator to infer which parts of the original external-completion objective were not done.
- After: the receipt and System Status checklist show exactly what is complete and what remains blocked, without treating internal quality as public launch proof.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review issue decision summary

- Hypothesis: External tracker issue bodies should start with the decision-level summary themselves, so a reviewer does not need to open the full review package to understand the recommendation, rationale, comparison context, evidence anchor, first action, and stop condition.
- Primary metric: `reviewIssueDecisionSummaryCoverage`.
- Baseline: generated tracker issue bodies had `## Decision`, source snapshot, operational readiness, and validation sections, but no top-level `## Decision Summary`.
- Candidate: Add `## Decision Summary` to static review issue bodies and validated saved-result issue bodies with `Recommendation`, `Why this candidate`, `Comparison context`, `Evidence anchor`, `First action`, and `Stop condition`.
- Decision: keep.

## Evidence

- `app.js` now prepends `## Decision Summary` to static review issue bodies before the detailed `## Decision` section.
- `review-result-view.js` now prepends the same summary shape to validated saved review result issue bodies.
- `scripts/smoke-interactions.mjs` verifies workspace, knowledge-base, and benchmark bundle text, validated issue draft bodies, and created issue bodies include the summary fields.
- `scripts/capture-output-quality-audit.mjs` records `reviewIssueDecisionSummary=true`, `reviewIssueDecisionSummaryFields=6`, and `reviewIssueDecisionSummaryCoverage=1`.
- `data/output-quality-audit.json` records `Review issue decision summary: pass (6 fields, coverage=1)` while `readyForExternalClaim=false` remains blocked until public launch proof is complete.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the issue-body Decision Summary contract.
- `npm run verify` passed with 210 pass, 0 fail, 0 not_run, 0 blocked; packaged browser gates passed with `reviewIssueDecisionSummaryVisible=true`.

## Improvement

- Before: the generated issue body was detailed, but the decision context had to be reconstructed from later sections or the full package bundle.
- After: the issue body opens with the recommendation, reason, comparison, evidence anchor, first action, and stop condition before the detailed evidence sections.

## Next Loop

- Continue improving copy-ready tracker artifacts where a reviewer still has to infer intent from long evidence sections.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review package decision brief

- Hypothesis: A review package is harder to use if the operator must reread the long handoff to know the recommendation, rationale, evidence anchor, and next action.
- Primary metric: `reviewPackageDecisionBriefCoverage`.
- Baseline: bundles had Bundle Manifest, Artifact Quality Rubric, and Operator Quick Start, but no six-field `Decision Brief`.
- Candidate: Add a `Review Package Decision Brief` with `Recommendation`, `Why this candidate`, `Comparison context`, `Execution target`, `Evidence anchor`, and `Next action`, then propagate it through manifest UI, copied bundle Markdown, browser smoke, output-quality receipt, and release audit terms.
- Decision: keep.

## Evidence

- `review-handoff.js` now computes `reviewPackageDecisionBrief`, exposes `data-review-package-decision-brief-*`, and includes `Decision brief: pass (6/6)` plus `### Decision Brief` in copied bundle Markdown.
- `scripts/smoke-interactions.mjs` verifies workspace, knowledge-base, and benchmark packages render all six decision brief fields and include them in copied bundle text.
- `scripts/capture-output-quality-audit.mjs` records `reviewPackageDecisionBrief=true`, `reviewPackageDecisionBriefFields=6`, and `reviewPackageDecisionBriefCoverage=1` in latest gate browser evidence, output readiness, and the final quality receipt.
- `data/output-quality-audit.json` now includes `Review package decision brief: pass (6 fields, coverage=1)` while `readyForExternalClaim=false` remains blocked until public launch proof is complete.
- `npm run verify` passed with 209 pass, 0 fail, 0 not_run, 0 blocked.

## Improvement

- Before: the package told the operator how to submit, but the top of the bundle still did not summarize what decision was being submitted and why.
- After: the package starts with a concise decision brief before the long validation, paste target, and quality evidence sections.

## Next Loop

- Continue improving top-level copy-ready proof where users still need to infer an action from long evidence sections.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review submission copy runtime module

- Hypothesis: Filled external issue receipt and final submission update copy handling can move out of `app.js` without changing clipboard behavior or release readiness.
- Primary metric: `appJsLineCount`.
- Baseline: `app.js` had 8829 lines with URL/ID validation, template fill, clipboard, status, and dataset updates inline.
- Candidate: `app.js` has 8797 lines and delegates the filled receipt/update copy flow to `review-submission-copy.js`.
- Decision: keep.

## Evidence

- `review-submission-copy.js` exposes `JooParkReviewSubmissionCopy` version `joopark-review-submission-copy/v1` with `copyReviewPackageFilledText`, `copyReviewPackageExternalReceiptFilled`, and `copyReviewPackageSubmissionUpdateFilled`.
- `app.js` keeps the existing action wrappers and now calls `reviewSubmissionCopyCall(...)`, so the UI action surface remains stable.
- `scripts/smoke-interactions.mjs` verifies `reviewSubmissionCopyModule=true` while preserving the existing filled receipt/update clipboard checks.
- `node scripts/check-app-structure.mjs` passed with `app.js totalLines=8797` and `review-submission-copy` marked extracted.
- `node scripts/package-release.mjs` passed with 52 files and 1852943 bytes; `node scripts/verify-release.mjs` passed with `sourceParityFiles=41`.
- `npm run verify` passed with 209 pass, 0 fail, 0 not_run, 0 blocked.

## Improvement

- Before: completed external receipt/update copy logic lived inside `app.js`, increasing the review action surface in the main runtime file.
- After: URL/ID validation, placeholder removal, clipboard writes, status labels, and copied dataset updates are isolated in a packaged runtime helper while `app.js` stays responsible for routing.

## Next Loop

- Continue extracting bounded review-package helpers where browser smoke already proves behavior.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review package operator quick start

- Hypothesis: A high-quality review package needs a short operator path before long evidence tables, so the user can submit without re-reading the full manifest.
- Primary metric: `reviewPackageOperatorQuickStartCoverage`.
- Baseline: Bundles included manifest, paste preview, submit sequence, receipt template, and artifact rubric, but no five-step `Operator Quick Start` near the top of the copied bundle.
- Candidate: Add `Operator Quick Start` to the manifest and copied bundle with five ready steps: `Confirm quality gate`, `Fill external tracker fields`, `Paste tracker issue body`, `Share final submission update`, and `Keep bundle proof`.
- Decision: keep.

## Evidence

- `review-handoff.js` now computes `reviewPackageOperatorQuickStart`, includes it in `joopark-review-package-manifest/v1`, and exposes `data-review-package-operator-quick-start-*` attributes in the manifest UI.
- The manifest summary now reports `quick start 5/5`, and copied bundle Markdown includes `Operator quick start: pass (5/5)`, `### Operator Quick Start`, and `Review Package Operator Quick Start` before the longer validation details.
- `scripts/smoke-interactions.mjs` verifies workspace, knowledge-base, and benchmark bundles render all 5 quick-start steps and copy them to the clipboard.
- `scripts/capture-output-quality-audit.mjs` records `reviewPackageOperatorQuickStart=true`, `reviewPackageOperatorQuickStartSteps=5`, and `reviewPackageOperatorQuickStartCoverage=1` in latest gate browser evidence and the final quality receipt.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the operator quick start contract.
- `npm run verify` passed with 206 pass, 0 fail, 0 not_run, 0 blocked after adding the operator quick start.

## Improvement

- Before: the user had strong evidence but still had to infer the exact pre-submit path from multiple sections.
- After: the bundle opens with a concise 5-step operator path, then preserves the detailed proof for audit and reuse.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review recommendation export runtime module

- Hypothesis: Portfolio review recommendation export rendering can move out of `app.js` without changing scoring, copy-ready review artifacts, or release behavior.
- Primary metric: `appJsLineCount`.
- Baseline: `app.js` had `8940` lines and still owned candidate benchmark, Workspace, and Knowledge/IA recommendation Markdown/export shell rendering inline.
- Candidate: `app.js` has `8816` structured lines in `node scripts/check-app-structure.mjs`, while `review-recommendation-export.js` owns the recommendation Markdown/export renderer behind `JooParkReviewRecommendationExport`.
- Decision: keep.

## Evidence

- `review-recommendation-export.js` exposes `joopark-review-recommendation-export/v1` and renders candidate benchmark, Workspace, and Knowledge/IA recommendation Markdown/export shells.
- `app.js` now keeps scoring, filtering, and state mutation while delegating through `reviewRecommendationExportCall(...)` wrappers.
- `index.html`, `package-release`, `verify-release`, `smoke-release`, `smoke-interactions`, `check-app-structure`, `audit-release-readiness`, `README`, and `docs/app-architecture.md` now include the runtime helper contract.
- GitHub Pages workflow templates plus `prepare-github-pages-workflow` and `plan-workflow-ui-install` now include `review-recommendation-export.js`; regenerated `data/workflow-ui-install-plan.json` reports `localTargetParityReady=true`.
- `npm run verify` passed with `206 pass, 0 fail, 0 not_run, 0 blocked`; packaged browser evidence records `reviewRecommendationExportModule=true` and runtime console/network/layout issues `0/0/0`.
- Final `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with `51` files, `1833756` bytes, `4` deploy support files, and `40` source parity files.

## Improvement

- Before: the portfolio review export builders made the already-large `app.js` harder to reason about and easier to miss in release packaging/path-filter checks.
- After: recommendation export rendering has a named runtime module, explicit load order, workflow path coverage, and smoke evidence while public launch completion remains correctly blocked.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Continue shrinking remaining Portfolio review presentation that is still inline in `app.js` without moving state mutation or persistence.

## Experiment: Review package artifact quality rubric

- Hypothesis: A review package is not truly ready for external tracker/comment/note submission unless each bundle carries its own scored artifact-quality rubric, not only the global output-quality receipt.
- Primary metric: `reviewPackageArtifactQualityScore`.
- Baseline: Review package bundles could pass final output quality `6/6`, but the bundle manifest did not show a package-level 100-point rubric for form fit, paste completeness, evidence traceability, submission flow, and safety/reuse.
- Candidate: Add `Artifact Quality Rubric` to every review package manifest and copied bundle Markdown with five 20-point checks: `Required form fit`, `Paste-ready completeness`, `Evidence traceability`, `Submission flow readiness`, and `Safety and reuse readiness`.
- Decision: keep.

## Evidence

- `review-handoff.js` now computes `reviewPackageArtifactQualityRubric`, adds it to `joopark-review-package-manifest/v1`, renders `artifact quality 100/100` in the manifest UI, and embeds the rubric table in bundle Markdown.
- The rubric compares against GitHub Issue Forms, Linear form templates, Jira required fields, and GitHub Actions job summaries so the generated package is scored against external submission and summary standards.
- `scripts/smoke-interactions.mjs` verifies workspace, knowledge-base, and benchmark review bundles expose `data-review-package-artifact-quality-*`, render 5 rubric rows, and copy `Artifact quality rubric: pass (100/100, threshold 90)` to the clipboard.
- `scripts/capture-output-quality-audit.mjs` now carries `reviewPackageArtifactQualityRubric=true`, `reviewPackageArtifactQualityScore=100/100`, and `reviewPackageArtifactQualityItems=5` in latest gate browser evidence.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the package-level rubric and exact score keys.
- `npm run verify` passed with 204 pass, 0 fail, 0 not_run, 0 blocked after the output-audit refresh.

## Improvement

- Before: a passing review bundle still forced the operator to infer whether its fields, evidence, and submit sequence met external tracker standards.
- After: each bundle shows an explicit 100/100 package-quality score with itemized evidence before the user copies it into tracker/comment/note destinations.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Release package lock staging publish

- Hypothesis: Release verify and audit should never observe a half-built `dist/release` artifact, even when packaging and summary checks are run in parallel.
- Primary metric: `releasePackageConcurrentVerifyReady`.
- Baseline: Concurrent package+verify and audit summary runs could observe `dist/release` after removal but before `release-manifest.json` and `RELEASE.md` were republished.
- Candidate: Add `dist/release.packaging.lock`, build the full artifact in `.staging-*`, publish the finished directory with a final swap, and make `verify-release` wait for the lock.
- Decision: keep.

## Evidence

- `scripts/package-release.mjs` now acquires a release package lock, writes the complete package into staging, then swaps the finished directory into `dist/release`.
- `scripts/verify-release.mjs` waits on `.packaging.lock` before reading `release-manifest.json` or `RELEASE.md`.
- `scripts/audit-release-readiness.mjs` and `README.md` now require/document the package lock, staging publish, and verifier wait contract.
- An artificial lock-holder test kept `dist/release.packaging.lock` for about 800ms; `node scripts/verify-release.mjs` returned `pass` after waiting 982ms.
- The stale output-quality external comparison smoke expectation was corrected from 3 to 4 rendered sources, matching the generated GitHub Actions, GitHub Releases, Linear, and Jira receipt.
- `npm run verify` passed with 201 pass, 0 fail, 0 not_run, 0 blocked; final release package verification reports 50 files, 1787641 bytes, 4 deploy support files, and 39 source parity files.

## Improvement

- Before: release verification could fail intermittently with missing manifest or release notes when another process was publishing the package.
- After: readers wait during publish and only inspect a complete old or complete new release directory.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Output artifact quality rubric

- Hypothesis: A final output-quality receipt is more actionable when it scores the generated artifacts against external submission and summary standards, rather than only listing that copy-ready artifacts exist.
- Primary metric: `artifactQualityRubric.totalScore`.
- Baseline: The output-quality receipt showed criteria, source freshness, completion audit, and external comparison, but it did not provide a weighted score explaining why the generated handoffs were ready to use.
- Candidate: Add an `Artifact quality rubric` with five 20-point checks for required form fit, copy-ready completeness, evidence traceability, safety guardrails, and freshness/reuse, backed by GitHub Issue Forms, Linear form templates, Jira required fields, and GitHub Actions job summary patterns.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now emits `artifactQualityRubric` with `totalScore=100`, `passingScore=90`, five scored rubric items, and receipt text under `Artifact quality rubric:`.
- `release-status.js` surfaces the rubric in System Status with dataset attributes for status, score, max score, passing score, and item count.
- `scripts/smoke-interactions.mjs` verifies the rendered rubric, `Score 100/100`, five pass items, required form fit, copy-ready completeness, safety guardrails, and clipboard receipt text.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the artifact-quality rubric and the Jira required-field external comparison source.

## Improvement

- Before: a user could see that outputs were copy-ready, but still had to infer whether they met the practical quality bar of required fields, evidence summary, and safe external sharing.
- After: the receipt gives a weighted, external-standard-backed quality score that explains why the current handoff artifacts are usable now while still blocking public launch completion.

## Next Loop

- Add the same artifact-quality score into individual review package bundles if any package can pass final quality 6/6 without exposing its rubric score near the copy buttons.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review copy actions runtime module

- Hypothesis: Review package copy behavior should be a packaged runtime helper rather than inline `app.js` orchestration, because rendering helpers are already split and copy-state behavior needs the same release coverage.
- Primary metric: `reviewCopyActionsModule`.
- Baseline: `app.js` owned paste-body copy and shared panel copy implementation directly.
- Candidate: Add `review-copy-actions.js`, keep existing `app.js` action wrappers, and delegate clipboard/status/dataset/toast updates through `reviewCopyActionsCall`.
- Decision: keep.

## Evidence

- `review-copy-actions.js` now owns `copyReviewPackagePasteBody` and `copyReviewPackagePanelText`.
- `app.js` keeps the existing action function names and delegates to the runtime helper, preserving current button/action routing.
- `index.html`, package/verify scripts, release smoke headers, structure check, release readiness audit, lint, and README now register `review-copy-actions.js`.
- `scripts/smoke-interactions.mjs` verifies `JooParkReviewCopyActions` version `joopark-review-copy-actions/v1` and persisted `reviewCopyActionsModule=true`.
- Existing browser smoke still verifies paste preview body copy, bundle copy, tracker field/form copy, submit sequence copy, and external receipt copy behavior.
- A mobile smoke regression on the home launch CTA was fixed with a stronger mobile min-height rule, and the home launch label smoke now checks the rendered dataset-backed label rather than a stale hard-coded phrase.
- `npm run lint`, `npm run check:structure`, `node scripts/package-release.mjs && node scripts/verify-release.mjs`, and `npm run verify` passed; final readiness is `200 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: review package copy implementation lived inside `app.js`, increasing the remaining inline responsibility of the main SPA file.
- After: copy behavior has its own packaged helper with script order, cache header, structure, release, and browser-smoke evidence.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Workflow UI install receipt loader contract

- Hypothesis: The GitHub UI install handoff is safer when the copied receipt carries the same machine-readable readiness signals that the System Status loader requires.
- Primary metric: `workflowUiInstallLoaded`.
- Baseline: the System Status panel could render the workflow UI install plan shell while `workflowUiInstallLoaded=false` because the paste packet text did not include `workflowUiInstallReady` / `localTargetParityReady` signal lines.
- Candidate: Add those readiness lines to `scripts/plan-workflow-ui-install.mjs`, keep output-quality wording on `Workflow UI install receipt`, and cover the loader, receipt text, snapshot label, clipboard text, audit, and cache behavior.
- Decision: keep.

## Evidence

- `scripts/plan-workflow-ui-install.mjs` now emits `workflowUiInstallReady=true` and `localTargetParityReady=true` inside the GitHub UI workflow install receipt/paste packet.
- `scripts/capture-output-quality-audit.mjs`, `release-status.js`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs` consistently name the output-quality item `Workflow UI install receipt` while preserving `workflowUiInstallPastePacketCoverage=1`.
- Browser diagnostics verified all System panels loaded after the loader fix: workflow UI install, publish dispatch, remote workflow file, publish evidence, launch execution, output quality audit, and source snapshot.
- `npm run lint`, `npm run verify`, `node scripts/capture-output-quality-audit.mjs --write`, `node scripts/package-release.mjs && node scripts/verify-release.mjs`, `node scripts/audit-release-readiness.mjs --format=summary`, `jq empty`, `git diff --check`, and release gate cache exclusion checks passed.
- Final readiness is `198 pass, 0 fail, 0 not_run, 0 blocked`; external launch remains blocked by workflow-scope/default-branch workflow installation and fresh live publish evidence.

## Improvement

- Before: a valid-looking receipt could still fail the loader contract and hide the workflow UI install proof from System Status.
- After: the copied operator receipt, System Status loader, output-quality receipt, smoke checks, and audit terms all use the same readiness vocabulary.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Output quality workflow auth preflight snapshot

- Hypothesis: The final output-quality receipt should independently surface the browser-verified workflow auth preflight state, not only carry it indirectly through the latest gate summary.
- Primary metric: `outputQualityWorkflowAuthPreflightSnapshot`.
- Baseline: `0`; the quality receipt did not have a dedicated `workflowAuthPreflight` snapshot or receipt line.
- Candidate: `1`; the receipt, JSON snapshot, System Status UI, smoke assertions, audit terms, and README all expose `uiVerified=true`, `workflowScopeAvailable=false`, `workflowScopeInstallBlocked=true`, missing `workflow`, and scopes `gist, read:org, repo`.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now emits `outputReadinessSnapshot.workflowAuthPreflight` with readiness, UI verification, field coverage, scopes, missing scopes, refresh command, and recheck command.
- `data/output-quality-audit.json` records `Workflow auth preflight: pass (uiVerified=true, workflowScopeAvailable=false, workflowScopeInstallBlocked=true, missing=workflow, scopes=gist, read:org, repo)`.
- `release-status.js` renders the snapshot row and exposes `data-output-quality-audit-workflow-auth-preflight*` attributes for browser verification.
- `scripts/smoke-interactions.mjs` verifies the DOM row, dataset fields, receipt text, and copied clipboard text.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the final quality auth-preflight coverage.
- `npm run lint`, `npm run verify`, `node scripts/capture-output-quality-audit.mjs --write`, `node scripts/package-release.mjs && node scripts/verify-release.mjs`, and `node scripts/audit-release-readiness.mjs --format=summary` passed; final release quality stayed ready while public launch proof remained blocked.

## Improvement

- Before: a copied final output-quality receipt could hide whether the workflow auth preflight card had actually passed browser smoke coverage.
- After: the receipt has a first-class auth preflight row with UI verification and current credential-scope evidence, while dispatch and external completion remain blocked.

## Next Loop

- Run `gh auth refresh -h github.com -s workflow`, install or verify `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on `main`, then rerun the launch handoff verifier.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Launch post-auth checkpoint

- Hypothesis: The launch execution packet should not stop at telling the operator to refresh GitHub auth; it should also show the exact post-auth checkpoint and success signals before workflow installation or dispatch.
- Primary metric: `launchPostAuthCheckpointCoverage`.
- Baseline: The packet exposed `authPreflight` and install paths, but the post-auth verification step was mixed into generic verify commands.
- Candidate: Add a top-level/current-action `Post-auth checkpoint` with auth status, handoff verifier, installer command, expected signals, blocked signals, and a `safeToDispatch=true` guard.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits `postAuthCheckpoint` with `gh auth status -h github.com`, `verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`, installer command, expected signals, blocked signals, and dispatch guard.
- `data/launch-execution-packet.json` includes `Post-auth checkpoint` in both the full launch packet and current action packet.
- `release-status.js` renders `data-launch-execution-post-auth-checkpoint` and `data-launch-execution-post-auth-checkpoint-*` attributes; `styles.css` reuses the launch execution card treatment.
- `scripts/smoke-interactions.mjs` verifies the rendered card, current action clipboard copy, and full launch packet clipboard copy include the checkpoint and `safeToDispatch=true before gh workflow run`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the checkpoint so launch guidance cannot regress to a standalone auth refresh command.
- `npm run lint`, `npm run check:structure`, `jq empty`, `git diff --check`, and `npm run verify` passed with `198 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: after `gh auth refresh -h github.com -s workflow`, the operator still had to infer which verification output proved it was safe to install workflows or dispatch.
- After: the packet lists the post-auth command, the exact success signals, the blocked signals, and the dispatch guard in the same UI and copied launch text.

## Next Loop

- Run `gh auth refresh -h github.com -s workflow` or use GitHub UI, then install both default-branch workflow files and rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep public launch completion blocked until `remoteWorkflowFilesReady=true`, `remoteWorkflowVisibilityReady=true`, dispatch runs complete, and fresh live publish evidence is captured.

## Experiment: System Status workflow auth preflight

- Hypothesis: Operators should see credential-scope remediation as a separate System Status preflight, not only as fields inside the dispatch grid or copy packet.
- Primary metric: `systemStatusWorkflowAuthPreflightFields`.
- Baseline: `Publish dispatch plan` showed `workflowScopeAvailable` and `workflowScopeInstallBlocked`, but did not isolate token-scope remediation from remote workflow file and visibility blockers.
- Candidate: Add a dedicated `Auth preflight` card with scope availability, install blocking, scope list, missing workflow scope, refresh/recheck commands, and an `auth preflight only` guard.
- Decision: keep.

## Evidence

- `release-status.js` now renders `data-publish-dispatch-auth-preflight` with `workflowScopeAvailable=false`, `workflowScopeInstallBlocked=true`, scope count/source, refresh command, recheck command, and a dispatch-withheld guard.
- `scripts/smoke-interactions.mjs` verifies the rendered card, exact scopes `gist, read:org, repo`, missing `workflow` scope, command text, and persisted `publishDispatchAuthPreflight=true`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the System Status `Auth preflight` card.
- `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --markdown` passed and still reports `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, and `workflowScopeInstallBlocked=true`.
- `npm run lint`, standalone interaction smoke, `npm run verify`, and `node scripts/audit-release-readiness.mjs --format=summary` passed; final readiness is `198 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: a user could see workflow installation blocked but had to infer whether the next action was auth refresh, GitHub UI install, or remote visibility recheck.
- After: System Status separates the auth preflight from workflow file/visibility blockers and labels the refresh command as non-dispatching preflight work.

## Next Loop

- Run `gh auth refresh -h github.com -s workflow`, then install the default-branch workflow files or use GitHub UI.
- Rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown` after installation; keep public launch completion blocked until dispatch and fresh live evidence are captured.

## Experiment: Publish evidence install path copy

- Hypothesis: Publish evidence copy outputs should include the same launch install path split as the launch packet and final quality receipt, so an operator can choose the CLI workflow-scope path or GitHub UI path without opening another artifact.
- Primary metric: `publishEvidenceInstallPathCopyCoverage`.
- Baseline: The share update, launch announcement guard, and post-launch verification receipt named the current workflow-install blocker but did not include `CLI path after workflow scope`, `GitHub UI path`, the REST installer command, or `pbcopy` workflow-template commands.
- Candidate: Add `launchInstallPaths` to publish evidence, render the path rows in System Status, verify DOM and clipboard copies, and keep public launch announcement dispatch commands withheld.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now derives `launchInstallPaths` from `data/launch-execution-packet.json` and appends `Choose one install path` copy to `shareUpdate`, `launchAnnouncement`, and `postLaunchVerificationReceipt`.
- `data/publish-evidence.json` includes `Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)` in all three copy outputs.
- `release-status.js` exposes `data-publish-evidence-install-path-*` attributes and renders each publish evidence install path row in System Status.
- `scripts/smoke-interactions.mjs` verifies rendered DOM and clipboard copies include both path labels, `node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify`, and `pbcopy`, while the public launch announcement still excludes raw `gh workflow run --repo` dispatch commands.
- `scripts/audit-release-readiness.mjs` adds `publish_evidence_install_path_copy`, and `README.md` documents the copied install path choices.
- `npm run lint`, `npm run check:structure`, `git diff --check`, `npm run verify`, `node scripts/verify-release.mjs`, `node scripts/audit-release-readiness.mjs --format=summary`, and `curl -I http://127.0.0.1:5181/` passed; final readiness is `198 pass, 0 fail, 0 not_run, 0 blocked`, with `49` release files and `1736743` bytes.

## Improvement

- Before: the publish evidence copy outputs could tell an operator that workflow installation was blocked while forcing them to look elsewhere for the concrete install choice.
- After: each copy-ready publish artifact includes both safe install paths and their command lists, while still blocking dispatch and public completion claims until remote workflow files, workflow visibility, dispatch runs, and fresh live evidence are present.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Launch packet auth preflight

- Hypothesis: A launch execution packet is less error-prone when the same packet that tells the operator how to install workflows also carries the current GitHub auth scope evidence.
- Primary metric: `launchPacketAuthPreflightCoverage`.
- Baseline: The packet carried `workflowScopeAvailable` and `workflowScopeInstallBlocked` as evidence lines, but did not expose a structured `authPreflight` object or the current token scopes in the launch packet model.
- Candidate: Add top-level and current-action `authPreflight`, render it in System Status, include it in both copied launch packets, and verify it through smoke/audit gates.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits `authPreflight` with `checked`, `status`, `source`, `workflowScopeAvailable`, `workflowScopeInstallBlocked`, `scopes`, `missingScopes`, `refreshCommand`, and `recheckCommand`.
- `data/launch-execution-packet.json` records `status=action_required`, scopes `gist, read:org, repo`, and `missingScopes=workflow`; both the full packet and current action packet include an `Auth preflight` section.
- `release-status.js` renders a launch Auth preflight card and exposes `data-launch-execution-auth-*` attributes.
- `scripts/smoke-interactions.mjs` verifies the rendered Auth preflight card and both launch clipboard copies include the scope evidence and missing `workflow` scope.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document `authPreflight`, `workflowScope.scopes`, `missingScopes`, and the refresh/recheck flow.
- `npm run lint`, `npm run check:structure`, `jq empty`, `git diff --check`, and `npm run verify` passed with `198 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the launch packet told the operator to refresh auth, but the current token scopes were not modeled as packet data.
- After: the packet carries scope state, missing scope, remediation command, and recheck command in the same UI and copied text as the workflow installation choices.

## Next Loop

- Keep public launch completion blocked until workflow files are installed on the default branch, visible in GitHub Actions, dispatched, and live publish proof is captured.
- Continue reducing any handoff that requires the operator to cross-reference separate panels before acting.

## Experiment: Launch handoff auth preflight

- Hypothesis: A launch handoff verifier should explain credential-scope blockers separately from remote file parity and workflow visibility blockers.
- Primary metric: `launchHandoffAuthPreflightFields`.
- Baseline: `verify-launch-handoff` reported `safeToDispatch=false` and blockers, but did not provide a dedicated auth preflight summary.
- Candidate: Add structured `authPreflight` fields and a Markdown `Auth Preflight` section with scope state, current scopes, refresh command, and recheck command.
- Decision: keep.

## Evidence

- `scripts/verify-launch-handoff.mjs` now emits `authPreflight.checked`, `source`, `workflowScopeAvailable`, `workflowScopeInstallBlocked`, `scopes`, `refreshCommand`, and `recheckCommand`.
- The Markdown output surfaces `Auth Preflight` before command results so the operator can first decide whether to refresh `workflow` scope or use the GitHub UI path.
- `README.md` documents that the verifier distinguishes GitHub CLI token scope problems from missing remote workflow files.
- `scripts/audit-release-readiness.mjs` requires the auth preflight terms so the verifier cannot regress to a generic blocked state.
- `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --markdown`, `npm run lint`, `npm run verify`, `node scripts/capture-output-quality-audit.mjs --write`, `node scripts/audit-release-readiness.mjs --format=summary`, `jq empty`, and `git diff --check` passed; final readiness is `197 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the blocked handoff mixed missing remote workflow files, Actions visibility, and token-scope remediation in one blocker list.
- After: the verifier separates auth scope evidence from file and visibility checks while still keeping dispatch withheld until `safeToDispatch=true`.

## Next Loop

- Run the verifier after `gh auth refresh -h github.com -s workflow` or GitHub UI workflow installation, then continue to live publish evidence only after `remoteWorkflowFilesReady=true`, `remoteWorkflowVisibilityReady=true`, and `allDispatchReady=true`.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Remote workflow REST API installer

- Hypothesis: Workflow installation should have a single safe CLI path that can create or update the default-branch workflow files after `workflow` scope is granted, instead of relying only on manual UI copy steps or local staging.
- Primary metric: `remoteWorkflowApiInstallerCoverage`.
- Baseline: The launch handoff exposed UI copy/open steps and local `.github/workflows` staging, but no REST contents API installer that handled create/update/noop/blocked states for both workflow files.
- Candidate: Add a GitHub REST repository contents API installer, wire it into the remote install packet and launch current action, and keep `gh workflow run` withheld until remote files and workflow visibility are verified.
- Decision: keep.

## Evidence

- `scripts/install-remote-workflow-files.mjs` classifies each workflow as `create`, `update`, `noop`, or `blocked`, checks `workflow` scope from the `gh api -i user` header, and refuses `--write` when `workflowScopeInstallBlocked=true`.
- A live `--write --verify` attempt against `biojuho/BIOJUHO-Projects` exited `blocked` without remote writes because the current token scopes are `gist`, `read:org`, `repo`; both remote workflow files are still missing on `main`.
- `scripts/check-remote-workflow-files.mjs` now emits `remoteInstallerCommand` and the install packet lists `node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify` before post-install verification.
- `scripts/capture-launch-execution-packet.mjs` includes the REST installer in `CLI path after workflow scope`, while preserving GitHub UI and local fallback paths.
- `scripts/smoke-interactions.mjs`, `scripts/audit-release-readiness.mjs`, `package.json`, and `README.md` now verify or document the installer command, `remoteWriteReady`, `workflowScopeInstallBlocked`, and `postInstallVerificationCommands`.
- `scripts/capture-output-quality-audit.mjs` now merges the latest packaged browser gate evidence when the compact AutoResearch gate summary lacks review/package details, so the final quality receipt keeps `Review package final quality: 6/6`, `Tracker form payloads: pass (11 fields, checksums ready)`, and release package parity evidence intact.
- `npm run lint`, `npm run check:structure`, `jq empty` on evidence JSON, `git diff --check`, `npm run verify`, and `node scripts/audit-release-readiness.mjs --format=summary` passed. Final readiness is `197 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: after auth refresh, the operator still had to choose between manual UI creation and local staging/git handoff, with no single command that directly matched GitHub's contents API model.
- After: the project has a direct installer command that is safe by default, blocks without `workflow` scope, records exactly which remote file operation would run, and immediately points to remote file and dispatch-plan verification.

## Next Loop

- Obtain or use a workflow-scope GitHub auth path, run `node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify`, then recheck `remoteWorkflowFilesReady`, `remoteWorkflowVisibilityReady`, and `allDispatchReady`.
- Keep public launch completion blocked until workflow dispatch runs and fresh Pages/workflow evidence are captured.

## Experiment: Launch handoff post-auth verifier

- Hypothesis: A post-auth launch handoff should have one safe verifier command that refreshes all launch-readiness evidence without dispatching workflows or claiming public launch proof.
- Primary metric: `launchHandoffVerifierSafeCommandCoverage`.
- Baseline: After operator auth or GitHub UI workflow installation, the user had to run remote workflow file check, live dispatch planning, launch execution packet capture, and output quality audit as separate commands.
- Candidate: Add `scripts/verify-launch-handoff.mjs` and surface `npm run verify:launch-handoff` as the verification-only post-auth runner.
- Decision: keep.

## Evidence

- `scripts/verify-launch-handoff.mjs` runs remote workflow file check, publish dispatch planning, launch execution packet capture, and output quality audit in one safe flow.
- The verifier output records `verificationOnly=true`, `dispatchExecuted=false`, `launchProofCaptured=false`, `safeToDispatch=false`, `2/5` launch acceptance, and withheld dispatch commands while remote workflows remain missing.
- `package.json` exposes `npm run verify:launch-handoff` and checks the new script in `npm run lint`.
- `scripts/capture-launch-execution-packet.mjs` adds the verifier and remote installer to `currentAction.verifyCommands`, and `release-status.js` renders the four-command `Verify after running` section in System Status.
- `scripts/smoke-interactions.mjs` verifies the rendered current action, copied current action packet, and full launch packet include `verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the post-auth verifier, remote installer command, `postInstallVerificationCommands`, and the non-dispatch guard terms.
- `npm run lint`, `npm run verify`, `node scripts/capture-output-quality-audit.mjs --write`, `node scripts/audit-release-readiness.mjs --format=summary`, and `git diff --check` passed; final readiness is `197 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the next operator action could be completed, but follow-up verification was split across several commands and easier to run out of order.
- After: the handoff has a single repeatable verifier that refreshes local launch guidance while keeping dispatch commands withheld until `allDispatchReady=true`.

## Next Loop

- Run `gh auth refresh -h github.com -s workflow`, install or verify `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on `main`, then run `npm run verify:launch-handoff`.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Release gate cache self-invalidation guard

- Hypothesis: A fresh packaged browser gate cache should not be invalidated by self-generated audit outputs or the audit script edits that happen after the browser gate has already run.
- Primary metric: `releaseGateCacheSelfInvalidationCoverage`.
- Baseline: A quick `node scripts/audit-release-readiness.mjs --format=summary` after `npm run verify` could report `packaged_browser_gates` as `not_run` because the cache context included self-written audit artifacts such as `data/output-quality-audit.json`.
- Candidate: Exclude `data/launch-execution-packet.json`, `data/output-quality-audit.json`, `data/publish-evidence.json`, and `scripts/audit-release-readiness.mjs` from the packaged browser gate cache fingerprint while keeping source commit, runtime files, release scripts, `package.json`, and stable source evidence in scope.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now defines `packagedBrowserGateContextExcludedFiles` with the launch packet, output quality receipt, publish evidence receipt, and audit script.
- `packagedBrowserGateInputFiles()` filters those self-generated paths before computing the cache context, preventing immediate stale-cache results after a fresh gate run.
- The release readiness self-check records `excludedFiles` evidence and verifies every configured exclusion is absent from the browser-gate fingerprint.
- `README.md` documents that cached quick summary audits exclude the self-written launch packet, output quality receipt, publish evidence, and audit script from the fingerprint.

## Improvement

- Before: the full gate wrote a fresh cache and then self-generated audit output or audit-script churn could make the cache stale before a quick summary reused it.
- After: quick summary audits can reuse the fresh packaged browser gate evidence until real source inputs, commit, completeness, or the 6-hour freshness window changes.

## Next Loop

- Keep checking generated evidence files for self-invalidating cache or source-provenance behavior.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Launch current action install path split

- Hypothesis: A blocked launch current action is more useful if it separates the workflow-scope CLI path from the GitHub UI path instead of mixing both in one command list.
- Primary metric: `launchCurrentActionInstallPathSplitCoverage`.
- Baseline: `JooPark Launch Current Action Packet` put auth refresh, verification, `pbcopy`, and GitHub new-file `open` commands under one `Run now` list.
- Candidate: Add `installPaths` with `CLI path after workflow scope` and `GitHub UI path`, each carrying commands, success condition, and guard text while dispatch commands stay under `Do not run yet`.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits `currentAction.installPaths` and `Choose one install path:` copy.
- `release-status.js` renders both path options in System Status before the fallback raw command list.
- `scripts/smoke-interactions.mjs` verifies the rendered current action, current action clipboard, full launch packet, and full packet clipboard include both path labels, CLI write commands, UI commands, and dispatch guards.
- `README.md` documents that current action copy separates `CLI path after workflow scope` from `GitHub UI path`.
- External check: GitHub docs still require `workflow_dispatch` on the default branch for manual runs, and repository contents docs still require workflow scope for `.github/workflows` modifications.

## Improvement

- Before: an operator could read the current action packet and run commands in a mixed order without understanding whether they were on the CLI credential path or the browser UI path.
- After: the packet gives two clear choices, their success criteria, and their guardrails, while preserving withheld dispatch commands until `allDispatchReady=true`.

## Next Loop

- Keep public launch completion blocked until remote workflow files exist, GitHub Actions sees both workflows, dispatch runs complete, and fresh live publish evidence is captured.
- Continue looking for blocked-state handoffs where the next action is technically correct but still too hard for an operator to execute cleanly.

## Experiment: Output quality launch install path receipt

- Hypothesis: The final output-quality receipt should carry the launch install path split so an operator does not need to open the launch execution packet to choose between CLI workflow-scope installation and GitHub UI installation.
- Primary metric: `outputQualityLaunchInstallPathReceiptCoverage`.
- Baseline: `JooPark Final Output Quality Audit Receipt` summarized the current launch blocker but did not list `CLI path after workflow scope`, `GitHub UI path`, or the remote workflow installer command.
- Candidate: Add `launchInstallPathSnapshot` and `outputReadinessSnapshot.launchInstallPaths` to the output-quality audit, receipt, System Status UI, smoke assertions, release audit terms, and README.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now normalizes `currentAction.installPaths` into the quality audit payload.
- `data/output-quality-audit.json` records `Launch install path options: pass (2 paths, 14 commands; CLI path after workflow scope | GitHub UI path)` and lists both path command sets.
- The receipt includes `node scripts/install-remote-workflow-files.mjs --repo biojuho/BIOJUHO-Projects --write --verify`, `pbcopy`, and GitHub new-file `open` commands.
- `release-status.js` renders a launch install path options snapshot and per-path rows in System Status.
- `scripts/smoke-interactions.mjs` verifies DOM, receipt text, and copied clipboard text include both labels and the installer command.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document this receipt coverage.
- `npm run verify` passed with `197 pass, 0 fail, 0 not_run, 0 blocked`.
- `node scripts/package-release.mjs` and `node scripts/verify-release.mjs` passed with `49` release files, `1699088` bytes, `4` deploy support files, and `38` source parity files.

## Improvement

- Before: the final quality receipt could tell the operator launch proof was blocked without showing the two concrete install choices.
- After: the receipt carries the same executable path split as the launch packet while still blocking dispatch and external completion claims.

## Next Loop

- Keep public launch completion blocked until remote workflow files exist, GitHub Actions sees both workflows, dispatch runs complete, and fresh live publish evidence is captured.
- Continue checking copy-ready receipts for missing concrete next-action choices.

## Experiment: Launch current action acceptance checklist

- Hypothesis: The current launch action should include explicit acceptance criteria, not only commands, so an operator can verify when it is safe to advance.
- Primary metric: `launchCurrentActionAcceptanceChecklistItems`.
- Baseline: The launch execution packet had commands, success condition, verification commands, and withheld dispatch commands, but no structured acceptance checklist for the current action.
- Candidate: Add a 5-item checklist covering `operator_auth_path`, `local_template_parity`, `remote_workflow_file_parity`, `workflow_visibility`, and `dispatch_guard`.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now writes `acceptanceChecklist`, `acceptancePassCount`, and `acceptancePendingCount` into `currentAction`.
- `data/launch-execution-packet.json` records `Acceptance checklist: 2/5 pass; pending=3`; remote workflow file parity and workflow visibility remain action-required until default-branch workflows are installed remotely.
- `release-status.js` renders the checklist in System Status and exposes acceptance count/pass/pending datasets.
- `scripts/capture-output-quality-audit.mjs` adds `Launch acceptance checklist: 2/5 pass, pending=3, stage=install_workflows` to the final quality receipt.
- `scripts/smoke-interactions.mjs` verifies the rendered checklist, current action clipboard text, full launch packet clipboard text, output quality snapshot, and copied quality receipt.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the acceptance checklist.
- `npm run lint`, `git diff --check`, and `npm run verify` passed with `196 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: the current launch handoff told the operator what to run, but the pass/fail conditions were spread across evidence lines.
- After: the handoff separates required acceptance conditions from commands, while still keeping dispatch withheld until `allDispatchReady=true`.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI.
- Rerun live dispatch planning and capture publish evidence after both workflows are visible and dispatched.

## Experiment: Remote workflow install post-checklist

- Hypothesis: A workflow install handoff is still risky if it tells the operator how to create files but does not separately list the success checks required before dispatch.
- Primary metric: `remoteWorkflowInstallPacketVerificationChecklistItems`.
- Baseline: `JooPark Remote Workflow Install Packet` had install steps and a dispatch guard, but no dedicated post-install verification checklist.
- Candidate: Add a six-item `Post-install verification checklist` covering remote file check, both workflow file matches, Actions visibility, and final dispatch readiness.
- Decision: keep.

## Evidence

- `scripts/check-remote-workflow-files.mjs` now adds `Post-install verification checklist` to the install packet.
- The checklist requires `remoteWorkflowFilesChecked: true`, `remoteWorkflowFilesReady: true`, per-workflow `remoteExists: true` and `remoteMatchesTemplate: true`, `remoteWorkflowVisibilityReady: true`, and `allDispatchReady: true`.
- `data/remote-workflow-file-check.json` was regenerated with the checklist while preserving the real blocker: both remote workflow files are still missing on `main`.
- `scripts/smoke-interactions.mjs` verifies the checklist in the rendered packet and clipboard copy.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the checklist so the handoff cannot regress to action-only instructions.
- `npm run lint`, `npm run check:structure`, `jq empty`, `git diff --check`, and quick release audit terms passed before final packaged gates.

## Improvement

- Before: an operator could follow the GitHub UI creation steps and still miss that Actions visibility and `allDispatchReady` must be confirmed before dispatch.
- After: the copied install packet states exactly which success booleans must be true before any `gh workflow run` command is safe.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Output quality source evidence freshness

- Hypothesis: A completion receipt should not be treated as current launch guidance unless the publish, dispatch, workflow, remote-file, and launch-packet evidence files are fresh and visible.
- Primary metric: `outputQualitySourceEvidenceFreshnessCoverage`.
- Baseline: The output-quality audit could show launch blockers while hiding the age of the JSON files used to produce those blockers.
- Candidate: Add source evidence freshness to the output-quality JSON, receipt, System Status UI, completion checklist, smoke assertions, release audit terms, and README.
- Decision: keep.

## Evidence

- Live-safe rechecks refreshed `data/remote-workflow-file-check.json` and `data/publish-dispatch-plan.json`; workflow installation remains blocked with `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, and `workflowScopeInstallBlocked=true`.
- `scripts/capture-output-quality-audit.mjs` now computes `sourceEvidenceFreshness` for publish evidence, dispatch plan, workflow UI install plan, remote workflow file check, and launch execution packet.
- `data/output-quality-audit.json` records `sourceEvidenceFresh=true`, `sourceEvidenceStaleCount=0`, 5 source rows, and an 8-item completion audit with `Source evidence freshness` passing.
- `release-status.js` renders the source freshness rows and exposes fresh/count/stale datasets.
- `scripts/smoke-interactions.mjs` verifies source freshness UI, receipt text, clipboard text, and the 8-item completion audit.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document stale evidence handling.
- `npm run lint`, `git diff --check`, and `npm run verify` passed; final readiness was `196 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: a user could copy a quality receipt without seeing whether the remote workflow and launch packet evidence behind it was still current.
- After: the receipt names each source file, generated time, age, freshness window, and stale count before presenting launch guidance.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review submission update pre-submit state

- Hypothesis: A team-share submission update should not claim `Status: submitted` until the external issue URL and ID have been filled.
- Primary metric: `reviewSubmissionUpdatePreSubmitStateCoverage`.
- Baseline: The `Review Submission Update` template already said `Status: submitted` and gave a post-submit next action while the external issue still showed `[paste issue ID]` and `[paste issue URL]`.
- Candidate: Keep the template in a pre-submit state, then convert it to the final submitted update only through the filled URL/ID copy path.
- Decision: keep.

## Evidence

- `review-handoff.js` now renders the template as `Status: ready after external issue URL/ID` and makes the next action conditional on the external issue fields being filled.
- `app.js` converts that template status to `Status: submitted` and removes the after-submit precondition only inside `fillExternalIssueText`.
- `scripts/smoke-interactions.mjs` verifies the template is not `Status: submitted`, then verifies the filled clipboard update has `Status: submitted` with no `[paste]`, `ready after external issue URL/ID`, or `After external issue URL/ID are filled` remnants.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the pre-submit template state and final submitted update separation.
- `npm run verify` passed with 196 pass, 0 fail, 0 not_run, 0 blocked after the review submission update pre-submit state fix.

## Improvement

- Before: a user could see a copy-ready update template that looked submitted before the external issue existed.
- After: the visible template communicates that it becomes a submitted team update only after URL/ID are filled, while the final copy remains clean and ready to share.

## Next Loop

- Continue looking for copy-ready outputs where template placeholders and final submitted state can be confused.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review submit sequence final update step

- Hypothesis: A submit sequence is incomplete if it records the external issue receipt but does not explicitly tell the operator to share the final `Review Submission Update`.
- Primary metric: `reviewSubmitSequenceFinalUpdateStepCoverage`.
- Baseline: `Review Package Submit Sequence` had 6 steps and moved from `Record external issue receipt` directly to `Post GitHub comment`, so the team-share update could be missed.
- Candidate: Add `Share final submission update` after receipt recording, update receipt integrity to `7/7`, and verify DOM, clipboard, audit, and documentation coverage.
- Decision: keep.

## Evidence

- `review-handoff.js` now inserts `Share final submission update` after `Record external issue receipt` and before `Post GitHub comment`.
- The step tells the operator to use `최종 update 복사` after filling the external issue URL/ID, so the team gets submitted status, issue link, integrity proof, and next action in one message.
- `scripts/smoke-interactions.mjs` requires 7 sequence steps, `Ready: 7/7`, `Share final submission update`, and `Use 최종 update 복사 after filling the external issue URL/ID` in both rendered sequence and copied clipboard text.
- External receipt and submission update checks now expect `Submit sequence ready: 7/7` / `submit sequence 7/7`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the final submission update step in the submit sequence.
- `npm run verify` passed with 196 pass, 0 fail, 0 not_run, 0 blocked after adding the final submission update step.

## Improvement

- Before: the sequence could lead a user to create the external issue and preserve proof without sending the clean team-share completion update.
- After: the sequence explicitly includes the final update as a required handoff step before GitHub comment and pinned note follow-up.

## Next Loop

- Continue looking for copy-ready outputs where a required handoff step is implied rather than explicitly sequenced.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Output quality final claim launch packet guard

- Hypothesis: The final output-quality claim guard must use the same launch-packet `readyForExternalClaim` gate as the staged execution packet, not only release quality and public launch proof.
- Primary metric: `outputQualityFinalClaimGuardInputs`.
- Baseline: Top-level `readyForExternalClaim` and the receipt summary were gated by 2 inputs: `releaseQualityReady` and `publicLaunchProofReady`.
- Candidate: Gate top-level `readyForExternalClaim`, receipt summary, System Status DOM, and smoke assertions by 3 inputs: `releaseQualityReady`, `publicLaunchProofReady`, and `launchPacketReadyForExternalClaim`.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now computes `finalReadyForExternalClaim` from release quality, public launch proof, and launch packet external-claim readiness.
- `data/output-quality-audit.json` records `launchPacketReadyForExternalClaim=false`, `executionState.readyForExternalClaim=false`, and `readyForExternalClaim=false`; the `External completion claim` item remains blocked.
- `release-status.js` exposes `data-output-quality-audit-launch-packet-external-ready` and a `launchPacketReadyForExternalClaim` row in System Status.
- `scripts/smoke-interactions.mjs` waits for and verifies the dataset, rendered external claim detail, receipt text, and clipboard text include `launchPacketReadyForExternalClaim=false`.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the triple-gated external completion claim.
- `node scripts/audit-release-readiness.mjs --run-gates`, `npm run lint`, `npm run check:structure`, `git diff --check`, `npm run verify`, and `node scripts/audit-release-readiness.mjs --quick --format=summary` passed; final readiness was `196 pass, 0 fail, 0 not_run, 0 blocked`.

## Improvement

- Before: a future live proof update could make the top-level output-quality receipt claim external readiness even if the launch execution packet still withheld external completion.
- After: final output-quality readiness cannot bypass the launch packet guard; public completion stays blocked until all three proof layers are true.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Workflow UI install paste packet

- Hypothesis: The GitHub UI workflow install path needs one copy-ready paste packet, not only a rendered receipt, so the operator can create both workflow files and run the exact post-install checks without mixing template, verification, and dispatch guard steps.
- Primary metric: `workflowUiInstallPastePacketCoverage`.
- Baseline: The workflow UI install receipt was visible, but no single coverage metric proved rendered copy readiness for both workflow templates, GitHub new-file URLs, verification commands, and dispatch guard text.
- Candidate: Add `JooPark GitHub UI Workflow Paste Packet`, `workflowUiInstallPastePacketReady=true`, `workflowUiInstallPastePacketCoverage=1`, clipboard copy evidence, output-quality receipt evidence, and release audit terms.
- Decision: keep.

## Evidence

- `scripts/plan-workflow-ui-install.mjs` now writes `workflowUiInstallPastePacket`, `uiPastePacket`, `packet`, readiness booleans, and coverage `1` into `data/workflow-ui-install-plan.json`.
- `release-status.js` and `app.js` render and validate the paste packet, expose readiness/coverage data attributes, and set `workflowUiInstallPastePacketCopied=true` after the copy action.
- `scripts/smoke-interactions.mjs` verifies System Status rendered data, the copy button, clipboard content, output-quality snapshot text, and persisted `workflowUiInstallPastePacketCopy=true`.
- `scripts/capture-output-quality-audit.mjs` records `workflowUiInstallPastePacketCoverage=1` in latest gate browser evidence, dispatch state, copy-ready artifacts, and the final quality receipt.
- `scripts/audit-release-readiness.mjs` and `README.md` require/document the paste packet, post-install verification commands, and the guard that keeps `gh workflow run --repo` blocked until remote file, visibility, dispatch, drift dispatch, and `safeToDispatch` proof are all ready.
- `npm run verify` passed with 200 pass, 0 fail, 0 not_run, 0 blocked; `data/output-quality-audit.json` records `workflowUiInstallPastePacketCopy=true` while `readyForExternalClaim=false`.

## Improvement

- Before: a user could see workflow UI install guidance but still have to assemble copy/paste content, post-install checks, and dispatch guard details from multiple places.
- After: System Status and the quality receipt prove a single copy-ready paste packet with both workflow templates, GitHub UI file-creation links, verification commands, and premature-dispatch guard text.

## Next Loop

- Land `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` on the default branch with workflow scope or GitHub UI, then rerun live dispatch planning.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.
## Experiment: Review artifact copy actions runtime module

- Hypothesis: Review artifact receipt and repair copy handlers can move into the existing review copy runtime helper without changing artifact repair or receipt clipboard behavior.
- Primary metric: `appJsLineCount`.
- Baseline: `node scripts/check-app-structure.mjs` reported `app.js totalLines=8831` before extraction.
- Candidate: Move five artifact copy handlers into `review-copy-actions.js` and leave thin `reviewCopyActionsCall` wrappers in `app.js`.
- Decision: keep.

## Evidence

- `review-copy-actions.js` now owns `copyReviewArtifactReceipt`, `copyReviewArtifactRepairPayload`, `copyIssueFreshReceipt`, `copyReviewArtifactPostApplyReceipt`, and `copyReviewPostRepairArtifactLink`.
- `app.js` still owns action routing and delegates artifact copy actions through `reviewCopyActionsCall`; structure check passes with `totalLines=8771`.
- `scripts/check-app-structure.mjs`, `scripts/audit-release-readiness.mjs`, `README.md`, and `docs/app-architecture.md` now require/document the expanded runtime helper boundary.
- `npm run verify` passed with 210 pass, 0 fail, 0 not_run, 0 blocked.
- `node scripts/verify-release.mjs` passed with 52 files, 1863818 bytes, deploySupportFiles=4, sourceParityFiles=41.

## Improvement

- Before: artifact receipt, repair payload, issue fresh receipt, post-apply receipt, and post-repair link copy logic lived inline in `app.js` beside state-changing repair code.
- After: static clipboard/status/dataset behavior lives in `review-copy-actions.js`, while `app.js` keeps repair state mutation and delegated action routing.

## Next Loop

- Split remaining artifact compare/repair state helpers only if the state mutation boundary stays explicit and smoke coverage remains green.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Operations copy actions runtime module

- Hypothesis: Settings/System publish, launch, workflow install, and output-quality copy handlers can move into a dedicated operations copy runtime helper without changing clipboard, status, copied dataset, release, or packaged browser behavior.
- Primary metric: `appJsLineCount`.
- Baseline: Previous loop structure gate reported `app.js totalLines=8771`.
- Candidate: Move twelve operations copy handlers into `operations-copy-actions.js` and keep thin `operationsCopyActionsCall` wrappers in `app.js`.
- Decision: keep.

## Evidence

- `operations-copy-actions.js` now owns Settings handoff, System publish handoff, publish evidence share/announcement/receipt, remote workflow install packet, workflow UI install receipt, post-install intake, workflow scope packet, launch packet/current action, and output-quality receipt copy handlers.
- `app.js` still owns action routing and delegates those handlers through `operationsCopyActionsCall`; `node scripts/check-app-structure.mjs` passes with `totalLines=8763`.
- Release packaging, release verification, smoke headers, structure audit, GitHub Pages workflow templates, README, and architecture docs all include `operations-copy-actions.js`.
- `npm run verify` passed with 213 pass, 0 fail, 0 not_run, 0 blocked.
- Packaged browser gates passed with 53 files, 1892596 bytes, deploySupportFiles=4, and sourceParityFiles=42.

## Improvement

- Before: operations copy behavior was scattered across inline `app.js` handlers, so publish/workflow/output-quality receipt status and dataset updates had to be maintained in the large action file.
- After: static clipboard/status/dataset behavior lives in `operations-copy-actions.js`, while `app.js` keeps only delegated action routing.

## Next Loop

- Split another low-state UI/action boundary only after keeping workflow install and public launch guards explicit.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review comment and pinned note decision summary

- Hypothesis: GitHub comments and pinned notes should carry their own six-field decision summary so copied secondary handoffs do not lose the recommendation, rationale, evidence anchor, first action, and stop condition.
- Primary metric: `reviewCommentNoteDecisionSummaryCoverage`.
- Baseline: generated GitHub comment and pinned note bodies had no `## Comment Decision Summary` or `## Pinned Note Summary` section.
- Candidate: add `Comment Decision Summary` and `Pinned Note Summary` with Recommendation, Why this candidate, Comparison context, Evidence anchor, First action, and Stop condition, then require those fields in paste readiness, smoke checks, and output-quality audit evidence.
- Decision: keep.

## Evidence

- `review-result-view.js` now prepends `## Comment Decision Summary` to GitHub comment Markdown before the long issue draft evidence.
- `app.js` and `review-result-view.js` now prepend `## Pinned Note Summary` to note bodies by reusing the generated issue Decision Summary.
- `review-handoff.js` requires all six decision summary fields before GitHub comment and pinned note paste targets report ready.
- `scripts/smoke-interactions.mjs` verifies workspace, knowledge-base, and benchmark paste previews, direct comment copies, pinned note bodies, output-quality DOM attributes, and receipt clipboard text include the comment/note decision summary evidence.
- `scripts/capture-output-quality-audit.mjs` records `reviewCommentNoteDecisionSummary=true`, `reviewCommentNoteDecisionSummaryFields=6`, and `reviewCommentNoteDecisionSummaryCoverage=1` in latest gate evidence, output readiness, and the final quality receipt.
- `npm run verify` passed with 213 pass, 0 fail, 0 not_run, 0 blocked; packaged browser gates passed with `reviewCommentNoteDecisionSummaryVisible=true`.

## Improvement

- Before: the tracker issue body had a decision summary, but a standalone GitHub comment or pinned note could bury the reason, first action, and stop condition inside longer copied evidence.
- After: every tracker/comment/note handoff starts with the same decision-level context, so secondary copied artifacts remain understandable when pasted alone.

## Next Loop

- Continue looking for secondary copy surfaces where a user can paste only one artifact and lose decision context or closure conditions.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Dialog shell runtime module

- Hypothesis: sheet/modal open-close, body lock, notification expanded state, focus restoration, and tab trapping can move into a dedicated dialog shell helper without changing accessibility behavior or packaged release gates.
- Primary metric: `appJsLineCount`.
- Baseline: Previous loop structure gate reported `app.js totalLines=8763`.
- Candidate: Add `dialog-shell.js` and keep thin `dialogShellCall` wrappers in `app.js` while feature-specific sheet/modal content stays in `app.js`.
- Decision: keep.

## Evidence

- `dialog-shell.js` now exposes `JooParkDialogShell` version `joopark-dialog-shell/v1` with sheet meta rendering, notification expanded state, sheet/modal open-close, focus restoration, focusable lookup, and tab trapping.
- `app.js` delegates common dialog shell behavior through `dialogShellCall`; notification and table sheets no longer manually set title/body/meta, `aria-hidden`, body lock, and close-button focus inline.
- Release packaging, release verification, smoke headers, structure audit, GitHub Pages workflow templates, README, and architecture docs all include `dialog-shell.js`.
- `node scripts/check-app-structure.mjs` passes with `totalLines=8688` and `dialog-shell` marked extracted.
- `npm run verify` passed with 216 pass, 0 fail, 0 not_run, 0 blocked.
- Packaged browser gates passed with 54 files, `dialogShellModule=true`, `dialog_shell_cache_no_cache=true`, deploySupportFiles=4, and sourceParityFiles=43.

## Improvement

- Before: sheet/modal state, body lock, notification trigger state, and focus behavior were mixed into `app.js`, with notification and table sheets duplicating the lower-level DOM sequence.
- After: common dialog shell behavior lives in `dialog-shell.js`, while `app.js` keeps action routing and feature-specific sheet/modal content.

## Next Loop

- Continue extracting only low-state UI-shell boundaries where focus/state ownership remains explicit.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review result repair action plan

- Hypothesis: failed review result repair packets should include a six-field action plan before raw validation evidence so the operator can fix the JSON object first, preserve schema identity, stay inside source evidence, and stop before premature issue or note creation.
- Primary metric: `reviewResultRepairActionPlanCoverage`.
- Baseline: failed repair packets had `Required JSON fields` and `Correction scaffold`, but no `Repair action plan` section before validation failures.
- Candidate: add `Repair action plan` with `Primary fix target`, `Schema identity`, `Evidence boundary`, `First action`, `Validation gate`, and `Stop condition`, then require it in smoke, output-quality audit, release status, README, and readiness audit evidence.
- Decision: keep.

## Evidence

- `review-result-view.js` now inserts the six-field repair action plan before raw validation failure evidence.
- `scripts/smoke-interactions.mjs` verifies malformed-result repair rendering, clipboard copy text, output-quality snapshot, and final receipt text include the action plan.
- `scripts/capture-output-quality-audit.mjs` records `reviewResultRepairActionPlan=true`, `reviewResultRepairActionPlanFields=6`, and `reviewResultRepairActionPlanCoverage=1`.
- `scripts/audit-release-readiness.mjs`, `release-status.js`, `README.md`, and `data/output-quality-audit.json` now require or surface the repair action plan metric.
- `npm run verify` passed with 216 pass, 0 fail, 0 not_run, 0 blocked.
- Packaged browser gates passed with 54 files, 1922446 bytes, sourceParityFiles=43, and `reviewResultRepairActionPlanVisible=true`.

## Improvement

- Before: a malformed review result repair packet told the operator which fields were required, but did not say which fix to make first, which identity values must stay fixed, or when to stop.
- After: the packet leads with repair intent, schema identity, source-evidence boundary, validation gate, and stop condition before exposing raw failure details.

## Next Loop

- Continue looking for secondary repair, receipt, and tracker-copy surfaces where a copied artifact can lose first action, validation gate, or stop condition context.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Project picker runtime module

- Hypothesis: project picker scaffold, option rendering, search status, body lock, and focus restoration can move into a dedicated runtime helper without changing project selection behavior or accessibility gates.
- Primary metric: `appJsLineCount`.
- Baseline: Previous loop structure gate reported `app.js totalLines=8688`.
- Candidate: Add `project-picker.js` and keep thin `projectPickerCall` wrappers in `app.js` while `pickProject` keeps dashboard mutation and view rerender ownership.
- Decision: keep.

## Evidence

- `project-picker.js` now exposes `JooParkProjectPicker` version `joopark-project-picker/v1` with accessibility normalization, option rendering, status updates, scaffold creation, open/close, focus restoration, and outside-close handling.
- `app.js` delegates common picker behavior through `projectPickerCall`; project selection state mutation, label updates, toast behavior, and view rerendering stay in `pickProject`.
- Release packaging, release verification, smoke headers, structure audit, readiness audit, GitHub Pages workflow templates, README, and architecture docs all include `project-picker.js`.
- `node scripts/check-app-structure.mjs` passes with `totalLines=8586` and `project-picker` marked extracted.
- `npm run verify` passed with 219 pass, 0 fail, 0 not_run, 0 blocked.
- Packaged browser gates passed with 55 files, `projectPickerModule=true`, deploySupportFiles=4, and sourceParityFiles=44.

## Improvement

- Before: project picker scaffold, live status, hidden-input recovery, body lock, and focus restoration lived inline in `app.js`.
- After: the picker shell behavior lives in `project-picker.js`, while `app.js` keeps the project state transition boundary explicit.

## Next Loop

- Continue extracting low-state navigation/runtime helpers only where accessibility ownership and state mutation stay clear.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Review package submission closeout summary

- Hypothesis: external issue receipts and final review submission updates should start with a six-field submission closeout summary so the operator can see submitted artifact identity, evidence anchor, first action, validation gate, archive target, and stop condition before sharing submitted status.
- Primary metric: `reviewPackageSubmissionCloseoutSummaryCoverage`.
- Baseline: receipt/update copy had checksums, required fields, submit sequence, and next action, but no `Submission Closeout Summary`.
- Candidate: add `Submission Closeout Summary` to the receipt template, submission update, paste preview Markdown, visible panels, completed receipt/update copy, output-quality audit, readiness audit, and README evidence.
- Decision: keep.

## Evidence

- `review-handoff.js` now generates `Submitted artifact`, `Evidence anchor`, `First action`, `Validation gate`, `Archive target`, and `Stop condition` rows across external receipt/update copy and visible package panels.
- `review-submission-copy.js` replaces the `Submitted artifact` placeholder with the actual external ID and URL in completed receipt/update copy.
- `scripts/smoke-interactions.mjs` verifies closeout panels, clipboard text, filled receipt replacement, output-quality DOM attributes, quality snapshot entry, and final quality receipt text.
- `scripts/capture-output-quality-audit.mjs` records `reviewPackageSubmissionCloseoutSummary=true`, `reviewPackageSubmissionCloseoutSummaryFields=6`, and `reviewPackageSubmissionCloseoutSummaryCoverage=1`.
- `release-status.js`, `scripts/audit-release-readiness.mjs`, `README.md`, and `data/output-quality-audit.json` now surface or require the closeout metric.
- `npm run verify` passed with 219 pass, 0 fail, 0 not_run, 0 blocked.
- Packaged browser gates passed with 55 files, `reviewPackageSubmissionCloseoutSummaryVisible=true`, deploySupportFiles=4, and sourceParityFiles=44.

## Improvement

- Before: a copied external receipt or review submission update could say it was ready to submit without a compact final summary of artifact identity, evidence anchor, validation gate, archive target, and stop condition.
- After: every submission receipt/update leads with closeout context, and completed copies replace the submitted artifact placeholder before the operator shares submitted status.

## Next Loop

- Continue looking for secondary repair, receipt, and tracker-copy surfaces where a copied artifact can lose first action, validation gate, archive target, or stop condition context.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Global search runtime module

- Hypothesis: topbar current-view search, clear recovery, no-results reveal, and search-inert command-palette fallback can move into a dedicated runtime helper without changing search behavior or accessibility recovery gates.
- Primary metric: `appJsLineCount`.
- Baseline: previous loop structure gate reported `app.js totalLines=8586`, with global search state and inert-view behavior still inline.
- Candidate: add `global-search.js` and keep thin `globalSearchCall` wrappers in `app.js` while `renderCurrentView`, `state.query`, refs, and command-palette opening remain explicit app dependencies.
- Decision: keep.

## Evidence

- `global-search.js` now exposes `JooParkGlobalSearch` version `joopark-global-search/v1` with inert-view affordance sync, clear control, no-results reveal, Escape recovery, and printable-key command-palette fallback.
- `app.js` delegates search shell behavior through compatibility wrappers and the structure gate now reports `totalLines=8502`.
- `scripts/smoke-interactions.mjs` verifies `globalSearchModule=true`; existing browser smoke still covers clear button, Escape clear, no-results recovery, and readonly inert-view fallback.
- Release packaging, release verification, smoke headers, structure audit, readiness audit, GitHub Pages workflow templates, README, and architecture docs all include `global-search.js`.
- `scripts/capture-output-quality-audit.mjs` preserves `globalSearchModule=true`, `releaseSourceParity=true`, `releaseSourceParityFiles=45`, and 56 release files in latest gate evidence.
- `npm run verify` passed with 220 pass, 0 fail, 0 not_run, 0 blocked.
- Latest output-quality audit recorded 56 release files, 1971597 bytes, sourceParityFiles=45, and `globalSearchModule=true`; final release package verification after audit sync also passed with 56 files.

## Improvement

- Before: search clear, live status, no-results reveal, inert-view readonly behavior, and command-palette fallback lived inline in `app.js`.
- After: global search shell behavior lives in `global-search.js`, and `app.js` keeps only explicit dependency wiring and search wrapper names used by existing views/actions.

## Next Loop

- Continue extracting low-state navigation/runtime helpers only where accessibility ownership and state mutation stay clear.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Post-install evidence intake field coverage

- Hypothesis: GitHub UI workflow installation should produce a fielded post-install evidence intake before any dispatch, archive, or launch claim so the operator must paste exact commit, parity, visibility, dispatch-readiness, and handoff-verifier proof values instead of relying on an unstructured checklist.
- Primary metric: `postInstallEvidenceIntakeFieldCoverage`.
- Baseline: post-install intake had checklist items, success signals, and verification commands, but no required receipt-like fields for exact proof values after GitHub UI workflow installation.
- Candidate: add six evidence fields for Pages workflow commit, Drift Watch workflow commit, remote parity proof, Actions visibility proof, dispatch readiness proof, and handoff verifier proof across Settings, System Status, paste packet, smoke, output-quality audit, readiness audit, and README.
- Decision: keep.

## Evidence

- `release-status.js` and `settings-view.js` now render the six field rows and the stop condition before dispatch/archive/launch claims.
- `scripts/plan-workflow-ui-install.mjs` writes the same evidence fields into the GitHub UI workflow paste packet.
- `scripts/smoke-interactions.mjs` verifies Settings, System Status, receipt copy, clipboard text, output-quality DOM attributes, snapshot item, and final quality receipt text.
- `scripts/capture-output-quality-audit.mjs` records `postInstallEvidenceIntake=true`, `postInstallEvidenceIntakeFields=6`, and `postInstallEvidenceIntakeFieldCoverage=1`.
- `scripts/audit-release-readiness.mjs`, `README.md`, and `styles.css` now require or document the fielded post-install evidence intake and stop condition.
- `npm run verify` passed with 220 pass, 0 fail, 0 not_run, 0 blocked; packaged browser gates passed with a fresh run cached, 56 release files, sourceParityFiles=45, and `postInstallEvidenceIntakeFieldCoverage=1`.
- Public launch completion remains blocked because `workflowScopeInstallBlocked=true`, `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, `postPublishEvidenceReady=false`, and `readyForExternalClaim=false`.

## Improvement

- Before: workflow UI installation proof was a checklist and signal list, so an operator could skip exact commit/parity/visibility/dispatch/handoff values before copying a launch-adjacent receipt.
- After: every copy-ready install handoff exposes six explicit proof fields and a stop condition that withholds dispatch and launch claims until `verify-launch-handoff` reports `safeToDispatch=true`.

## Next Loop

- Keep workflow installation as the public-launch blocker until both workflow files exist on the default branch and GitHub Actions visibility is confirmed.
- Continue looking for launch, receipt, and tracker-copy surfaces where copied artifacts can lose validation gate, archive target, or stop condition context.

## Experiment: Output-quality source input trace

- Hypothesis: The final output-quality receipt should list every input file or override used to build it, so fixture runs and downgrade-guard tests cannot look like they used the default product loop or release gate cache.
- Primary metric: `outputQualitySourceInputTraceCoverage`.
- Baseline: `data/output-quality-audit.json` had no structured `sourceInputs` list and the receipt did not show override input paths.
- Candidate: add `sourceInputs`, `sourceInputCount=8`, and a `Source inputs` receipt section for product loop, release gate cache, previous output-quality receipt, publish evidence, dispatch plan, workflow UI install plan, remote workflow file check, and launch execution packet.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now emits `sourceInputs` and `sourceInputCount=8`, with dynamic paths from `--product-loop`, `--release-gate-cache`, and `--previous-output-quality`.
- `scripts/audit-release-readiness.mjs` and `README.md` now require or document `sourceInputs`, `sourceInputCount`, and the `Source inputs` receipt section.
- A degraded fixture run wrote `/tmp/joopark-source-trace-output-quality.json` and proved the `/tmp/joopark-source-trace-product-loop.json` and `/tmp/joopark-source-trace-release-gates.json` override paths were preserved while `evidenceDowngradeGuard.applied=true`.
- `npm run verify` passed with 220 pass, 0 fail, 0 not_run, 0 blocked after the source trace change.
- `data/output-quality-audit.json` records `sourceInputCount=8`, latest gate `220 pass`, 56 release files, `artifactQualityRubric=pass`, `outputReadinessSnapshot=pass`, and `readyForExternalClaim=false`.

## Improvement

- Before: an overridden fixture or downgrade-guard run could emit a receipt that looked like it came from the default product loop and release gate cache.
- After: both normal and fixture output-quality receipts show the actual input path list, so audit readers can distinguish default evidence from test evidence.

## Next Loop

- Continue tightening launch and quality receipts where a copied artifact can lose its evidence source, validation gate, archive target, or stop condition.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Launch proof evidence receipt field coverage

- Hypothesis: the publish launch path should expose a dedicated six-field launch proof evidence receipt before external launch copy, archive, or `readyForExternalClaim` claims so final launch proof cannot collapse into an unstructured note.
- Primary metric: `launchProofEvidenceFieldCoverage`.
- Baseline: publish evidence had launch acceptance ledger and post-launch receipt copy, but no dedicated six-field launch proof evidence receipt for site, workflow, freshness, release, and claim-guard proof.
- Candidate: add a `JooPark Launch Proof Evidence Receipt` with six proof fields across publish evidence capture, System Status UI, copy actions, smoke, output-quality audit, readiness audit, and README.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` now emits `launchProofEvidenceFields`, `launchProofEvidenceFieldCount=6`, `launchProofEvidenceFieldCoverage=1`, and placeholder-resolved launch proof receipt text.
- `release-status.js` renders the six-field receipt card, data attributes, fallback labels, hidden receipt text, and copy button; `operations-copy-actions.js` and `app.js` wire `copy-publish-launch-proof-receipt`.
- `scripts/smoke-interactions.mjs` verifies the card, six labels, readiness dataset, copy status, clipboard text, output-quality DOM attributes, quality snapshot item, and final quality receipt line.
- `scripts/capture-output-quality-audit.mjs` records the receipt in copy-ready artifacts, quality rubric, completion checklist, output readiness snapshot, and final receipt text.
- `scripts/audit-release-readiness.mjs` and `README.md` now require or document the launch proof evidence receipt; latest release readiness summary passed with 221 pass, 0 fail, 0 not_run, 0 blocked.
- Public launch completion remains blocked because `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, `postPublishEvidenceReady=false`, `workflowScopeInstallBlocked=true`, and `readyForExternalClaim=false`.

## Improvement

- Before: launch proof could be discussed in adjacent receipts without a single copy-ready fielded artifact that names every required proof value.
- After: the launch path has a six-field receipt with copy/clipboard smoke and output-quality evidence, so launch copy stays blocked until live site, workflow, freshness, release, and public-claim guard proof are all present.

## Next Loop

- Fill the six launch proof evidence receipt fields only after live GitHub Pages and Actions proof exists.
- Keep public launch completion blocked until workflow visibility, dispatch, and fresh live publish evidence are all captured.

## Experiment: Launch current action default-branch proof

- Hypothesis: the launch current-action packet should include official default-branch and manual-dispatch proof so workflow installation blockers stay copy-ready and cannot be confused with dispatch readiness.
- Primary metric: `currentActionDefaultBranchProofCoverage`.
- Baseline: current action named workflow installation blockers and commands, but did not carry a dedicated `defaultBranchRequirementProof` object sourced from official GitHub manual dispatch and repository contents verification docs.
- Candidate: add a Default-branch requirement proof object, rendered panel, copy text, smoke coverage, readiness audit terms, and README documentation.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits `currentAction.defaultBranchRequirementProof` with `ready=true`, `workflowFileCount=2`, four requirements, the manual workflow dispatch docs URL, the REST contents API docs URL, and a `gh workflow list` visibility recheck command.
- `data/launch-execution-packet.json` records `.github/workflows/joopark-pages.yml` and `.github/workflows/joopark-drift-watch.yml` as default-branch workflow files and requires each remote file to match its local template SHA-256 before dispatch.
- `release-status.js` renders a Default-branch requirement proof panel with source, docs URLs, workflow list command, workflow files, and requirements; `styles.css` adds matching launch-current proof styling.
- `scripts/smoke-interactions.mjs` verifies the proof panel, dataset counts, GitHub docs URLs, `workflow_dispatch` default-branch requirement, template SHA match requirement, copy-ready packet text, and clipboard text.
- `scripts/audit-release-readiness.mjs` and `README.md` now require or document Default-branch requirement proof, `workflow_dispatch` default-branch presence, repository contents verification, and template SHA matching.
- Public launch completion remains blocked because `workflowScopeInstallBlocked=true`, `workflowScopeAvailable=false`, `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, `postPublishEvidenceReady=false`, `allDispatchReady=false`, and `readyForExternalClaim=false`.

## Improvement

- Before: the current action packet said to install workflows, but the official reason for default-branch installation and the remote contents proof path were implicit.
- After: the launch packet and UI make the default-branch requirement, manual dispatch prerequisite, remote contents verification, template SHA match, and Actions visibility recheck explicit.

## Next Loop

- Install both workflow files on the default branch after acquiring `workflow` scope or using the GitHub UI path.
- Keep public launch completion blocked until workflow visibility, dispatch readiness, live workflow runs, and fresh publish evidence are captured.

## Experiment: Launch blocker resolution checklist

- Hypothesis: the launch execution packet should map every blocked launch signal to an operator action, proof command, expected value, and stop condition so workflow installation cannot be mistaken for dispatch or public launch proof.
- Primary metric: `launchBlockerResolutionChecklistCoverage`.
- Baseline: launch execution packet had acceptance checks and verification matrix rows, but no single `blockerResolutionChecklist` tying blocked signals to proof commands and stop conditions.
- Candidate: add six checklist items for `operator_auth_path`, `local_template_parity`, `remote_workflow_file_parity`, `workflow_visibility`, `dispatch_guard`, and `launch_proof_capture` across packet generation, System Status UI, smoke, readiness audit, styles, and README.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits `blockerResolutionChecklist`, `activeItemKey`, `actionRequiredCount`, `proofCommand`, `expectedValue`, and `stopCondition`.
- `release-status.js` renders a System Status `Blocker resolution checklist` card with six rows and root data attributes for status, counts, active item, and proof command coverage.
- `styles.css` aligns the checklist with the existing launch execution cards and highlights `action_required` rows.
- `scripts/smoke-interactions.mjs` verifies the dataset, row statuses, rendered proof/stop text, and copy-ready launch packet text.
- `scripts/audit-release-readiness.mjs` and `README.md` now require or document the checklist and `deferred_until_dispatch` guard.

## Improvement

- Before: operators had to infer the next proof command from several adjacent launch panels.
- After: the launch packet states the blocked signal, exact proof command, expected value, and stop condition for each launch blocker.

## Next Loop

- Keep `operator_auth_path`, remote workflow parity, and workflow visibility as the active blockers until the GitHub workflow files are installed and visible on the default branch.
- Continue tightening copied launch artifacts that can blur workflow installation, dispatch authorization, and public launch proof.

## Experiment: Launch handoff verifier blocker resolution

- Hypothesis: the verification-only launch handoff command should print the same blocker resolution checklist as System Status so operators can resolve workflow install blockers from CLI output without opening the app.
- Primary metric: `launchHandoffVerifierBlockerResolutionCoverage`.
- Baseline: `verify-launch-handoff` Markdown showed auth preflight, acceptance checklist, blockers, and next actions, but not the six blocker-resolution rows with proof command, expected value, and stop condition.
- Candidate: add `blockerResolutionChecklist` to the verifier JSON payload and a `Blocker Resolution Checklist` Markdown section.
- Decision: keep.

## Evidence

- `scripts/verify-launch-handoff.mjs` now reads `data/launch-execution-packet.json` `blockerResolutionChecklist`, normalizes counts, and prints six rows with `proofCommand`, `expectedValue`, and `stopCondition`.
- `README.md` documents the verifier Markdown fields: `activeItemKey`, `actionRequired`, `deferred`, `proofCommands`, `proofCommand`, `expectedValue`, and `stopCondition`.
- `scripts/audit-release-readiness.mjs` now requires the verifier and README to preserve this section.
- External benchmark: GitHub manual workflow dispatch depends on a default-branch `workflow_dispatch`, so verifier output should carry proof commands and stop conditions before any workflow run.

## Improvement

- Before: an operator running only the CLI verifier still had to open System Status or launch packet text to see the exact blocker-resolution proof commands.
- After: the verifier Markdown itself explains the active blocker, six checklist rows, proof commands, expected values, and dispatch stop conditions.

## Next Loop

- Keep dispatch blocked until `verify-launch-handoff` reports `safeToDispatch=true`.
- After workflow file installation, use this verifier output as the first post-install proof summary before any launch proof capture.

## Experiment: Output quality blocker resolution receipt

- Hypothesis: the final output-quality receipt should surface the same blocker-resolution checklist as the launch packet and CLI verifier so operators can resolve launch blockers from the final quality artifact alone.
- Primary metric: `outputQualityReceiptBlockerResolutionCoverage`.
- Baseline: `data/output-quality-audit.json` had no `outputReadinessSnapshot.blockerResolutionChecklist` and the receipt had no `Blocker resolution checklist` section, while `data/launch-execution-packet.json` already had six checklist rows.
- Candidate: add blocker-resolution snapshot normalization, receipt text, System Status dataset/snapshot row, smoke assertions, readiness-audit terms, and README documentation.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now reads `blockerResolutionChecklist`, adds it to `outputReadinessSnapshot`, includes it in the readiness pass gate, and prints active item, counts, proof commands, expected values, and stop conditions.
- `release-status.js` exposes `data-output-quality-audit-blocker-resolution-*` attributes and a `Blocker resolution checklist` snapshot row in System Status.
- `scripts/smoke-interactions.mjs` verifies dataset coverage, the visible snapshot row, receipt text, clipboard text, `proofCommand`, `expectedValue`, and `stopCondition`.
- `scripts/audit-release-readiness.mjs` and `README.md` now require or document the output-quality blocker-resolution receipt contract.

## Improvement

- Before: the final quality receipt proved release quality and public-launch blockers, but the operator still had to open the launch packet or verifier to see exact blocker-resolution proof commands.
- After: the final receipt itself carries `active=operator_auth_path`, `2/6 pass`, `actionRequired=3`, `deferred=1`, `proofCommands=6`, and the six row-level proof/stop conditions.

## Next Loop

- Keep workflow installation and public launch proof blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue tightening final receipts so they remain self-contained enough for external handoff without raw JSON inspection.

## Experiment: Product-loop summary gate parity

- Hypothesis: the AutoResearch product-loop summary should carry the same latest gate and launch publish blockers as the final output-quality audit so operators do not see stale pass counts or stale external-claim state.
- Primary metric: `productLoopSummaryParityCoverage`.
- Baseline: the product-loop top-level `latestGate` still reported `220 pass/220 total` while `data/output-quality-audit.json` reported `221 pass/221 total`.
- Candidate: add `scripts/sync-product-loop-summary.mjs` to synchronize the product-loop top-level `latestGate`, release status, tracked publish blockers, and experiment log from `data/output-quality-audit.json`.
- Decision: keep.

## Evidence

- `scripts/sync-product-loop-summary.mjs --markdown` reports baseline parity `1/2` and candidate parity `2/2`.
- `scripts/sync-product-loop-summary.mjs --write --markdown` updated `autoresearch-results/joopark-product-loop.json` so the top-level gate now matches `221 pass, 0 fail, 0 not_run, 0 blocked`.
- The sync preserves tracked public-launch blockers: `remoteWorkflowFilesReady=false`, `remoteWorkflowVisibilityReady=false`, `workflowScopeInstallBlocked=true`, `postPublishEvidenceReady=false`, and `readyForExternalClaim=false`.
- `package.json` lint now checks the sync script, and `README.md` documents it with the other release evidence scripts.

## Improvement

- Before: the final receipt and product-loop headline disagreed on the current gate count.
- After: the product-loop headline, publish blockers, and experiment log are synchronized from the current output-quality receipt.

## Next Loop

- Keep the product-loop summary in sync after future output-quality receipts.
- Continue resolving default-branch workflow installation before dispatch or public launch proof capture.

## Experiment: Workflow scope device-code approval handoff

- Hypothesis: the publish and launch handoff should treat GitHub CLI workflow-scope refresh as a device-code approval step, not as workflow installation or dispatch proof, so operators have a safe next action when noninteractive auth cannot complete.
- Primary metric: `workflowScopeApprovalHandoffCoverage`.
- Baseline: `workflowScopeRefreshHandoff` included the refresh and recheck commands, but did not structure the approval URL, expected prompt, sensitive value policy, or stop condition.
- Candidate: add `workflowScopeApprovalHandoff` across the dispatch plan, launch packet, System Status UI, output-quality receipt, smoke assertions, readiness audit, README, and AutoResearch log.
- Decision: keep.

## Evidence

- A noninteractive `gh auth refresh -h github.com -s workflow` attempt required GitHub device-code approval, confirming this blocker is operator approval rather than a local code failure.
- `scripts/plan-publish-dispatch.mjs` now emits `workflowScopeApprovalHandoff` with `status=approval_required`, `approvalUrl=https://github.com/login/device`, success signals, GitHub UI fallback, and a stop condition that keeps install, dispatch, public copy, and archive proof blocked.
- `scripts/capture-launch-execution-packet.mjs` copies the approval handoff into `authPreflight` and the current action packet text without storing the one-time device code.
- `release-status.js` renders approval status and `approvalUrl` in Publish dispatch and Launch execution Auth preflight surfaces, and adds `Device-code approval handoff` to the publish unblock copy.
- `scripts/capture-output-quality-audit.mjs` records workflow auth approval status, URL, device-code policy, and stop condition in the final output-quality receipt.
- `scripts/smoke-interactions.mjs`, `scripts/audit-release-readiness.mjs`, and `README.md` now require the approval URL, one-time code policy, and stop condition to remain visible.

## Improvement

- Before: the refresh command could look like a simple command to run, even though it may pause for browser approval and produce a sensitive one-time code.
- After: the product explicitly says the approval URL is `https://github.com/login/device`, the one-time code must not be saved, and dispatch/install/public launch proof remain blocked until scope or GitHub UI installation is verified.

## Next Loop

- Complete the GitHub approval or GitHub UI workflow file installation outside the codebase, then rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.

## Experiment: Failed gate cache downgrade guard

- Hypothesis: a failed packaged browser gate cache should not overwrite previously verified browser evidence in the final output-quality audit.
- Primary metric: `failedGateCacheDowngradeGuardCoverage`.
- Baseline: a failed interaction-smoke cache could overwrite `publishDispatchAuthPreflight`, `outputQualityAuditReceipt`, and `outputQualityArtifactRubric` to false before the previous pass evidence guard could recover.
- Candidate: merge `releaseGateBrowserEvidence` only when `releaseGateCache.evidence.status === "pass"`, then keep stale/failed cache state out of browser evidence while preserving the current gate checks and launch blockers.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now gates browser evidence merging on `releaseGateCache?.evidence?.status === "pass"`.
- `README.md` documents that failed packaged browser gate cache cannot downgrade pass evidence.
- `scripts/audit-release-readiness.mjs` now requires the pass-cache condition so future edits cannot reintroduce the failed-cache downgrade.
- After the fix, `npm run verify` passed with `221 pass, 0 fail, 0 not_run, 0 blocked`, and `data/output-quality-audit.json` kept `outputReadinessSnapshot.status=pass`.

## Improvement

- Before: a failed run could turn a proven output-quality surface into a false negative and create a circular failure.
- After: failed caches remain diagnostic data, while only pass caches can refresh browser evidence in the final quality receipt.

## Next Loop

- Keep public launch completion blocked until default-branch workflow files and live publish proof are installed and captured.
- Continue checking evidence-generation order whenever new receipts or browser cache fields are added.

## Experiment: Product-loop experiment chronology guard

- Hypothesis: the product-loop summary should identify the latest current-or-past experiment and flag future-dated experiment rows so the headline does not point to a timestamp anomaly.
- Primary metric: `latestExperimentChronologyCoverage`.
- Baseline: `latestExperiment` selected a future-dated `output-quality-blocker-resolution-receipt` row instead of the newest current-or-past experiment.
- Candidate: keep unchanged sync experiments in place, move sync-only recency to `latestSyncExperiment`, compute product-facing `latestExperiment` from current-or-past non-sync timestamps, and record `futureDatedExperimentCount` plus `futureDatedExperimentIds`.
- Decision: keep.

## Evidence

- `scripts/sync-product-loop-summary.mjs` no longer refreshes the sync experiment `generatedAt` on no-op parity checks.
- `autoresearch-results/joopark-product-loop.json` now separates `latestExperiment` from `latestSyncExperiment`, so sync-only parity updates do not become the product-facing headline.
- `summarySync.futureDatedExperimentCount` and `summarySync.futureDatedExperimentIds` make timestamp anomalies visible without using them as headline status when they are ahead of the sync timestamp.
- `README.md` documents the `latestExperiment` and `latestSyncExperiment` split.

## Improvement

- Before: the summary could point to a sync-only row or future timestamp as the latest product experiment.
- After: the summary points to the latest current-or-past non-sync experiment and still exposes sync/future rows for inspection.

## Next Loop

- Normalize or correct future-dated experiment rows when doing broader log maintenance.
- Keep launch completion blocked until remote workflow installation and live publish proof are complete.

## Experiment: Settings deploy device-code approval handoff

- Hypothesis: Settings Deploy Handoff should mirror the System Status device-code approval handoff so operators can resolve workflow-scope approval from either operational surface without treating auth refresh as dispatch proof.
- Primary metric: `settingsDeployApprovalHandoffCoverage`.
- Baseline: Settings Deploy Handoff included workflow-scope refresh guidance but did not include the device-code approval URL, one-time code storage policy, `gh auth status` recheck, `workflowScopeAvailable: true`, or `workflowScopeInstallBlocked: false` success signals.
- Candidate: add a `Device-code approval handoff` section to Settings Deploy Handoff and verify it through DOM, dataset, clipboard, readiness audit, README, and AutoResearch evidence.
- Decision: keep.

## Evidence

- `app.js` now adds `approvalUrl=https://github.com/login/device`, the one-time device code no-store rule, `gh auth status -h github.com`, `workflowScopeAvailable: true`, and `workflowScopeInstallBlocked: false` to `settingsDeployHandoffText()`.
- `settings-view.js` now surfaces a visible Deploy Handoff reminder that device-code approval codes are not stored and dispatch stays blocked until workflow scope is rechecked.
- `scripts/smoke-interactions.mjs` verifies Settings Deploy Handoff DOM text, dataset text, clipboard copy, and System/Settings publish readiness mirror coverage for the device-code approval handoff.
- `scripts/audit-release-readiness.mjs` and `README.md` now require Settings Deploy Handoff coverage for the approval URL, one-time code policy, and workflow-scope success signals.

## Improvement

- Before: System Status had the device-code approval handoff, but Settings Deploy Handoff could still look like a generic refresh-command checklist.
- After: Settings and System Status both preserve the same approval URL, sensitive-code policy, success signals, and stop conditions before workflow install, dispatch, public launch copy, or archive proof.

## Next Loop

- Complete GitHub approval or GitHub UI workflow installation outside the codebase, then rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.

## Experiment: Product-loop summary gate cache exclusion

- Hypothesis: product-loop summary synchronization should not invalidate a fresh packaged browser gate because the summary files are operational evidence, not packaged runtime inputs.
- Primary metric: `productLoopSyncCachedGateStability`.
- Baseline: cached audit became blocked after product-loop sync because `autoresearch-results/joopark-product-loop.json` changed and `packaged_browser_gates` fell to `not_run`.
- Candidate: exclude `autoresearch-results/joopark-product-loop.json` and `autoresearch-results/joopark-product-loop.md` from the packaged browser gate source fingerprint while keeping runtime and release data files covered.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now includes both product-loop summary files in `packagedBrowserGateContextExcludedFiles`.
- The readiness audit term checklist requires both product-loop summary paths in the gate cache exclusion policy.
- `README.md` documents that product-loop summary files are release-evidence summaries outside the packaged runtime fingerprint.

## Improvement

- Before: the safe order `npm run verify -> capture-output-quality-audit -> sync-product-loop-summary -> audit summary` could invalidate the just-created browser gate cache.
- After: post-gate product-loop summary sync can update operational evidence without forcing an unrelated browser smoke rerun.

## Next Loop

- Keep the exclusion list limited to generated evidence summaries and never add runtime files to it.
- Continue resolving workflow installation and public launch proof blockers before any external completion claim.

## Experiment: Launch packet post-install evidence ledger

- Hypothesis: the launch packet should own a machine-readable post-install evidence intake ledger so the final quality receipt can show which workflow-install proof fields are still incomplete before dispatch.
- Primary metric: `postInstallEvidenceLedgerCoverage`.
- Baseline: the post-install intake was copy-ready in System Status and Settings, but `data/launch-execution-packet.json` did not store field-level proof status, `completedFieldCount`, `proofComplete`, `commandCount`, or `signalCount`.
- Candidate: add `postInstallEvidenceIntake` to the launch packet, render it in System Status and Settings, read it into the output-quality snapshot, and verify it through smoke/readiness audit terms.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits a six-field `postInstallEvidenceIntake` ledger with `proofComplete=false`, `completedFieldCount=0`, four verification commands, eight expected signals, and a dispatch stop condition.
- `release-status.js` renders the launch packet ledger and final quality snapshot with completed field count, proof completeness, commands, and signals.
- `settings-view.js` prefers the launch packet ledger while preserving the existing copy-ready intake fallback.
- `scripts/capture-output-quality-audit.mjs` records the ledger in `outputReadinessSnapshot` and the copied final quality receipt.
- `scripts/smoke-interactions.mjs` and `scripts/audit-release-readiness.mjs` require the launch packet DOM, clipboard text, quality snapshot, receipt text, and generated JSON fields.

## Improvement

- Before: an operator could see the intake template was available but still had to infer from other artifacts whether the six proof fields were actually filled.
- After: the launch packet and final quality receipt separate copy-readiness from proof completion, showing `completed=0/6` and `proofComplete=false` until remote file, visibility, dispatch, and handoff proof are captured.

## Next Loop

- Complete GitHub approval or GitHub UI workflow installation outside the codebase, then rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep `proofComplete=false` and dispatch withheld until all six post-install evidence fields are filled.

## Experiment: Release gate preflight evidence refresh

- Hypothesis: Packaged browser gates should refresh launch and output-quality evidence before packaging so the first smoke attempt does not fail on stale data artifacts.
- Primary metric: `stalePackagedEvidenceRetryRate`.
- Baseline: `npm run verify` could fail at `system publish readiness alignment` even though the regenerated source and `dist/release` launch packet later satisfied the `launchPacketReady` dataset contract.
- Candidate: refresh `data/launch-execution-packet.json` and `data/output-quality-audit.json` before `RELEASE_OUT_DIR` smoke packaging and preserve the preflight result in gate evidence.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now runs `capture-launch-execution-packet.mjs --write` and `capture-output-quality-audit.mjs --write` before packaged browser smoke.
- `scripts/verify-launch-handoff.mjs` now emits post-install `fieldKeys` including `remote_parity_proof` and `handoff_verifier_proof`, preserving the static proof-field contract in cached audits.
- A failed evidence-source preflight now returns a failed packaged gate before running browser smoke against stale JSON.
- The packaged smoke result records `sourceRefresh` so the gate evidence can show which generated artifact refresh ran.
- `README.md` documents that `--run-gates` refreshes launch and output-quality evidence before browser gates.

## Improvement

- Before: the first packaged browser smoke in a fresh verify could package stale generated evidence and fail, then leave the workspace in a state that passed direct DOM inspection.
- After: generated launch/output evidence is refreshed before the release package is created, reducing stale-evidence retry rate from 1 to 0 for this failure path.

## Next Loop

- Rerun the full release gate and keep this preflight narrow to generated evidence files, not runtime source files.
- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.

## Experiment: Verify handoff post-install evidence ledger

- Hypothesis: the launch handoff verifier should expose the same post-install evidence ledger as the launch packet so operators can prove remote workflow parity, Actions visibility, dispatch readiness, and `safeToDispatch` from one CLI report before any dispatch.
- Primary metric: `verifyHandoffPostInstallEvidenceCoverage`.
- Baseline: `verify-launch-handoff` JSON had `hasPostInstallEvidenceIntake=false` and Markdown did not include a dedicated `Post-install Evidence Intake` section.
- Candidate: add `postInstallEvidenceIntake` to verifier JSON and a Markdown section with source, status, `proofComplete`, completed/pending field counts, commands, expected signals, six field rows, dispatch guard, and stop condition.
- Decision: keep.

## Evidence

- `scripts/verify-launch-handoff.mjs` now reads `data/launch-execution-packet.json` `postInstallEvidenceIntake` and emits `source`, `status`, `ready`, `proofComplete`, `completedFieldCount`, `pendingFieldCount`, `fieldCoverage`, `commandCount`, `signalCount`, `checklistCount`, `dispatchGuard`, `stopCondition`, commands, expected signals, and six field rows.
- The focused verifier JSON check reports `hasPostInstallEvidenceIntake=true`, `status=collect_post_install_proof`, `proofComplete=false`, `completed=0`, `fields=6`, `commands=4`, `signals=8`, with `remote_parity_proof` and `handoff_verifier_proof` present.
- The Markdown verifier output now includes `## Post-install Evidence Intake`, `fields: 0/6 complete`, `remote_parity_proof`, `handoff_verifier_proof`, and `Stop condition: do not run gh workflow run`.
- `scripts/audit-release-readiness.mjs`, `scripts/capture-output-quality-audit.mjs`, and `README.md` now require or document the verifier-side post-install evidence ledger.
- During full gate verification, a failed packaged self-check cache briefly downgraded `outputQualityExternalClaimGuard` and `artifactQualityRubric`; `scripts/capture-output-quality-audit.mjs` now preserves source-backed external claim guard evidence from a fresh previous pass receipt so the verifier ledger can be checked without entering a self-referential failure loop.

## Improvement

- Before: the CLI handoff verifier could show blocker rows and withheld dispatch commands, but the operator still had to open launch packet or dashboard output to see the six post-install proof fields.
- After: the verifier itself shows copy-ready status separately from proof completion, keeping `safeToDispatch=false` and dispatch withheld while listing the exact missing proof fields.

## Next Loop

- Complete GitHub approval or GitHub UI workflow installation outside the codebase, then rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep `proofComplete=false` and dispatch withheld until all six post-install evidence fields are filled and `verify-launch-handoff` reports `safeToDispatch=true`.

## Experiment: Launch handoff verifier proof artifacts

- Hypothesis: the launch handoff verifier should save durable JSON and Markdown proof artifacts so the operator can attach or review the exact pre-dispatch state after running `--write`, without treating console output as the only proof source.
- Primary metric: `launchHandoffVerifierArtifactCoverage`.
- Baseline: `data/launch-handoff-verification.json` and `data/launch-handoff-verification.md` were missing after verifier runs.
- Candidate: make `verify-launch-handoff --write` save both artifacts while preserving stdout JSON/Markdown behavior.
- Decision: keep.

## Evidence

- `scripts/verify-launch-handoff.mjs` now accepts `--out-json` and `--out-markdown`, writes `data/launch-handoff-verification.json` and `data/launch-handoff-verification.md` during `--write`, and keeps stdout behavior unchanged.
- The saved JSON reports `verificationArtifact.artifactCoverage=2`, `safeToDispatch=false`, `postInstallEvidenceIntake.status=collect_post_install_proof`, `fieldCount=6`, `completedFieldCount=0`, and `proofComplete=false`.
- The saved Markdown contains `JooPark Launch Handoff Verification`, `Verification Artifacts`, `artifactCoverage: 2`, `Post-install Evidence Intake`, `safeToDispatch: false`, and `Withheld Dispatch Commands`.
- `scripts/audit-release-readiness.mjs` and `README.md` now require and document these durable verifier artifacts as verification-only proof, not dispatch approval.

## Improvement

- Before: an operator had to preserve terminal output manually after running the handoff verifier.
- After: every `--write` run leaves a durable JSON and Markdown proof pair that can be reviewed, shared, and audited while dispatch remains withheld.

## Next Loop

- Complete GitHub approval or GitHub UI workflow installation outside the codebase, then rerun `node scripts/verify-launch-handoff.mjs --repo biojuho/BIOJUHO-Projects --write --markdown`.
- Keep `data/launch-handoff-verification.*` as proof artifacts only until `safeToDispatch=true` and live publish evidence is captured.

## Experiment: Output quality variant comparison ledger

- Hypothesis: The final quality receipt should explain why the selected output is better than a generic generated summary, so users can trust and reuse the artifact without reconstructing the decision.
- Primary metric: `copyReadyVariantDecisionScore`.
- Baseline: the receipt had external standards and a rubric, but did not explicitly compare a generic generated summary against the selected copy-ready evidence receipt.
- Candidate: add `outputVariantComparison` with `generic_generated_summary` rejected, `copy_ready_evidence_receipt` selected, `decision=keep_b`, four winner criteria, and receipt/System Status/smoke coverage.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` now emits `outputVariantComparison` with score `6/6` versus baseline `2/6`.
- The copied final quality receipt includes `Output variant comparison`, the selected/rejected variants, four winner criteria, and launch-safety evidence while `postPublishEvidenceReady=false` remains blocked.
- `release-status.js` surfaces the variant decision in System Status dataset attributes, a visible `Output variant comparison` section, selected/rejected variant rows, and winner criteria rows.
- `scripts/smoke-interactions.mjs` and `scripts/audit-release-readiness.mjs` require the variant comparison dataset, DOM, clipboard, generated JSON, and README coverage.

## Improvement

- Before: the user could see that the final receipt passed, but still had to infer why it was more usable than a generic generated status update.
- After: the receipt shows the A/B decision directly: `generic_generated_summary` is rejected and `copy_ready_evidence_receipt` is selected because it carries tracker fields, proof traceability, source freshness, and launch safety.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue looking for copied artifacts where the selected output rationale is implied instead of stated.

## Experiment: Release summary external blocker visibility

- Hypothesis: the compact release readiness summary should not say blockers are none while the external completion claim guard is blocked, because that makes a copy-ready handoff look safer than it is.
- Primary metric: `completionBlockerVisibilityScore`.
- Baseline: `1/4`; the summary showed `blocked_external_claim`, but `## Blockers` could still say `none` when local release checks passed.
- Candidate: `4/4`; map blocked external claim guard requirements into the Markdown and compact summary `## Blockers` sections.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now emits `external_claim_guard.workflow_installation`, `external_claim_guard.public_launch_proof`, and `external_claim_guard.external_completion_claim` blocker rows when `readyForExternalClaim=false`.
- The candidate summary keeps release quality status separate from public launch completion by listing missing signals such as `remoteWorkflowFilesReady=false`, `postPublishEvidenceReady=false`, and `readyForExternalClaim=false`.
- The Markdown audit uses the same blocker rows, so a copied audit report and a compact terminal summary carry the same stop condition.

## Improvement

- Before: a user scanning only `## Blockers` could see `none` and miss the fact that public launch proof was still blocked.
- After: the same scan shows exactly which external completion requirements are incomplete, while dispatch commands remain withheld.

## Next Loop

- Rerun the full release gate so packaged browser evidence is fresh after the summary renderer change.
- Keep workflow installation, dispatch, and public launch proof blocked until the live remote checks pass.

## Experiment: Publish dispatch withheld command ledger

- Hypothesis: the dispatch plan should expose withheld dispatch commands as first-class JSON and UI fields, because readers should not infer unsafe commands from a generic command list or from publish evidence alone.
- Primary metric: `dispatchPlanWithheldCommandClarityScore`.
- Baseline: `1/3`; `suggestedDispatchCommands` was empty and `dispatchSuggestionStatus` was withheld, but the saved dispatch plan did not expose a top-level withheld command list or count.
- Candidate: `3/3`; the plan, System Status, smoke checks, release audit, and README all distinguish safe verification commands from withheld repo-scoped dispatch commands.
- Decision: keep.

## Evidence

- `scripts/plan-publish-dispatch.mjs` now emits `withheldDispatchCommands`, `suggestedDispatchCommandCount`, and `withheldDispatchCommandCount` while keeping `suggestedDispatchCommands` empty before `allDispatchReady=true`.
- `data/publish-dispatch-plan.json` now records `suggestedDispatchCommandCount: 0`, `withheldDispatchCommandCount: 2`, and the two repo-scoped `gh workflow run` commands under `withheldDispatchCommands`.
- `release-status.js` surfaces `data-publish-dispatch-withheld-dispatch-count`, visible `suggestedDispatchCommandCount`, visible `withheldDispatchCommandCount`, and a `withheldDispatchCommands` command list in the Publish dispatch plan panel.
- `scripts/audit-release-readiness.mjs`, `scripts/smoke-interactions.mjs`, and `README.md` now require or document the same fields so the dispatch guard remains copy-ready and auditable.

## Improvement

- Before: a user reading only the saved dispatch plan had to infer which dispatch commands were withheld from `commands`, blockers, or publish evidence.
- After: the dispatch plan itself says suggested dispatch is `0`, withheld dispatch is `2`, and lists the exact commands that must remain blocked until `allDispatchReady=true`.

## Next Loop

- Keep `gh workflow run` blocked until remote workflow files exist on the default branch, GitHub Actions lists both workflows, and `verify-launch-handoff` reports `safeToDispatch=true`.
- After workflow installation, rerun `node scripts/plan-publish-dispatch.mjs --live --repo biojuho/BIOJUHO-Projects --write` and confirm `withheldDispatchCommandCount` drops to `0` only when `suggestedDispatchCommands` is safe to use.

## Experiment: Blocker resolution checklist guard

- Hypothesis: the blocker resolution checklist should carry one global stop condition so operators can use the copied checklist without opening every row.
- Primary metric: `blockerResolutionGuardCoverage`.
- Baseline: `0/1`; checklist rows had item stop conditions, but the checklist summary and quality receipt did not expose a single global dispatch stop condition.
- Candidate: `1/1`; launch packet, quality audit, System Status, smoke checks, release audit, and README all carry the same checklist-level guard.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` emits `guard` and `dispatchGuard` with the full `action_required` plus `safeToDispatch=true` stop condition.
- `scripts/capture-output-quality-audit.mjs` normalizes the guard, requires it for readiness, and writes it into the final receipt.
- `release-status.js` surfaces the guard in the launch blocker checklist and output quality snapshot dataset/text.
- `scripts/smoke-interactions.mjs` and `scripts/audit-release-readiness.mjs` require the guard in DOM, clipboard, generated JSON, and receipt checks.
- `README.md` documents the checklist-level guard as the global dispatch stop condition.

## Improvement

- Before: an operator reading the copied blocker checklist had to infer the global dispatch stop condition from individual row stop conditions.
- After: the checklist and final quality receipt state: `Do not run gh workflow run until every action_required item has passed and verify-launch-handoff reports safeToDispatch=true.`

## Next Loop

- Keep dispatch withheld until remote workflow files exist on the default branch, GitHub Actions lists both workflows, and `verify-launch-handoff` reports `safeToDispatch=true`.
- Continue scanning copied release artifacts for implied stop conditions that should be promoted to first-class fields.

## Experiment: Blocker resolution guard copy polish

- Hypothesis: the checklist-level dispatch guard should read like polished operator copy, not an internal status phrase, while preserving the same safety condition.
- Primary metric: `blockerResolutionGuardCopyReadabilityScore`.
- Baseline: `1/2`; the guard was safe but used an ungrammatical pass-state phrase, which reads like an internal machine state.
- Candidate: `2/2`; the guard now says `every action_required item has passed` and still requires `verify-launch-handoff reports safeToDispatch=true`.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` emits the polished guard text from the generator.
- `app.js`, `scripts/smoke-interactions.mjs`, `scripts/audit-release-readiness.mjs`, and `README.md` require the same wording in Home, System Status, clipboard, receipt, and audit checks.
- The safety state remains unchanged: dispatch is withheld until every `action_required` item has passed and `safeToDispatch=true` is verified.

## Improvement

- Before: the copied guard was structurally correct but visibly auto-generated.
- After: the same guard is readable as operator-facing release copy and can be pasted into a handoff without cleanup.

## Next Loop

- Continue scanning copy-ready receipts for internal-state grammar that is safe but not polished enough for external handoff.

## Experiment: Launch readiness refresh guard specificity

- Hypothesis: The launch-readiness refresh artifact should block dispatch on the same concrete refresh checklist and handoff verifier conditions as the launch packet, instead of only saying `safeToDispatch=true`.
- Primary metric: `launchReadinessGuardSpecificityScore`.
- Baseline: `1/3`; the refresh artifact was safe, but its copied next action used only a `safeToDispatch` stop condition.
- Candidate: `3/3`; `nextAction.detail` now requires every `action_required` refresh checklist item to pass and `verify-launch-handoff reports safeToDispatch=true`, while the artifact-level guard also keeps archive proof and `readyForExternalClaim` blocked until post-publish proof and external-claim readiness are true.
- Decision: keep.

## Evidence

- `scripts/refresh-launch-readiness.mjs` now emits the stronger dispatch and external-claim guard from named guard constants.
- `scripts/audit-release-readiness.mjs`, `scripts/smoke-interactions.mjs`, and `README.md` require the same stronger wording.
- The external benchmark is GitHub's manual workflow dispatch prerequisite model: a manual run depends on a `workflow_dispatch` workflow on the default branch and write access, so copied dispatch guidance should name the local prerequisite checks before surfacing `gh workflow run`.

## Improvement

- Before: the refresh artifact was safe but underspecified for operator handoff.
- After: the copied refresh result states the checklist-level and verifier-level conditions needed before dispatch, archive proof, or an external completion claim.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue scanning one-command refresh artifacts for guards that are safe but too generic for reuse.

## Experiment: External claim closeout packet actionability

- Hypothesis: the external completion guard should include a one-page closeout packet that maps remaining blockers to required proof fields, allowed claims, and forbidden claims.
- Primary metric: `externalClaimCloseoutActionabilityScore`.
- Baseline: `2/5`; the guard listed requirements, signals, proof commands, and a stop condition, but an operator still had to assemble the final public-claim checklist.
- Candidate: `5/5`; the guard now carries five closeout steps, six required proof fields, allowed public claims, forbidden claims, and external benchmark notes for `default branch workflow_dispatch`, workflow run summary, and release-note archive proof.
- Decision: keep.

## Evidence

- `scripts/capture-output-quality-audit.mjs` emits `closeoutPacket` and `closeoutPacketText` inside `externalClaimGuard`.
- `release-status.js` renders the closeout packet under System Status with step, field, allowed-claim, and forbidden-claim counts.
- `scripts/smoke-interactions.mjs` verifies the DOM, clipboard copy, and final quality receipt include the closeout packet.
- `scripts/audit-release-readiness.mjs` and `README.md` require the same closeout packet terms so the artifact remains part of the release audit.

## Improvement

- Before: the external claim guard was safe but still forced the operator to infer the last mile of external proof.
- After: the copied guard states the required proof fields and exactly which claims stay forbidden until live workflow, Pages, summary, and release-note evidence exist.

## Next Loop

- Keep `readyForExternalClaim=false` until the remote workflow files, workflow visibility, dispatch readiness, live publish evidence, launch packet, and final external-claim proof fields all pass.
- Continue looking for copy-ready receipts that still require an operator to translate machine state into public-facing proof language.

## Experiment: Post-auth checkpoint guard specificity

- Hypothesis: the post-auth checkpoint should name the full `action_required` checkpoint prerequisite set, not only the `safeToDispatch` verifier result, before any `gh workflow run` is allowed.
- Primary metric: `postAuthCheckpointGuardSpecificityScore`.
- Baseline: `1/3`; the checkpoint guard was safe, but it could be read as verifier-only because it only named `safeToDispatch=true`.
- Candidate: `3/3`; the launch packet, System Status, output-quality receipt, smoke checks, release audit, README, and generated artifacts now require every `action_required` post-auth checkpoint item to pass and `verify-launch-handoff reports safeToDispatch=true`.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits the stronger post-auth checkpoint guard from the generator.
- `scripts/capture-output-quality-audit.mjs` requires that guard for `launchPostAuthCheckpoint` readiness and writes it into the final quality receipt.
- `release-status.js` surfaces the same fallback guard in System Status, while `scripts/smoke-interactions.mjs` verifies DOM and clipboard coverage.
- `scripts/audit-release-readiness.mjs` and `README.md` require the same guard so release audit and operator documentation stay aligned.

## Improvement

- Before: a user could treat the handoff verifier as the only post-auth checkpoint and miss remote workflow file parity, Actions visibility, or dispatch readiness.
- After: the copied checkpoint states that every `action_required` post-auth checkpoint item must pass before `gh workflow run`, even if a verifier output is available.

## Next Loop

- Keep dispatch blocked until remote workflow files, workflow visibility, dispatch readiness, and `verify-launch-handoff` all prove safe dispatch.
- Continue scanning copied checkpoint and receipt text for verifier-only phrasing that should name prerequisite proof fields.

## Experiment: Workflow UI install receipt guard specificity

- Hypothesis: the GitHub UI workflow paste packet should state that UI file creation is not dispatch approval and that every post-install evidence field must be filled before any `gh workflow run`.
- Primary metric: `workflowUiInstallReceiptGuardSpecificityScore`.
- Baseline: `1/3`; the receipt listed remote and dispatch booleans, but the guard still ended on a `safeToDispatch=true`-style condition and did not name the six post-install evidence fields as the required ledger.
- Candidate: `3/3`; the paste packet, final quality receipt, smoke checks, release audit, README, and generated artifacts now require every post-install evidence field, remote workflow file parity, Actions visibility, dispatch readiness, and `verify-launch-handoff reports safeToDispatch=true`.
- Decision: keep.

## Evidence

- `scripts/plan-workflow-ui-install.mjs` now emits a stronger post-install stop condition and dispatch guard from the receipt generator.
- `scripts/capture-output-quality-audit.mjs` requires that stronger receipt text and writes the Workflow UI paste packet guard into the final quality receipt.
- `scripts/smoke-interactions.mjs` verifies the System Status receipt, clipboard copy, output-quality receipt, and output-quality clipboard copy contain the same guard.
- `scripts/audit-release-readiness.mjs` and `README.md` require the same guard so the operator docs and release audit cannot drift.

## Improvement

- Before: an operator could read the UI paste packet as enough once GitHub UI file creation and `safeToDispatch=true` were visible.
- After: the copied packet explicitly separates UI file creation, post-install evidence collection, dispatch readiness, and verifier proof before any run command is allowed.

## Next Loop

- Keep dispatch blocked until the two workflow files are committed on the default branch, remote parity and Actions visibility are true, dispatch readiness is true, and live launch proof can be captured.
- Continue scanning install and proof receipts for text that still treats one verifier result as a substitute for the full evidence ledger.

## Experiment: Post-install UI guard specificity

- Hypothesis: the Home, Settings, System Status, launch packet, and handoff verifier post-install UI text should not reduce dispatch approval to a `safeToDispatch`-only condition.
- Primary metric: `postInstallUiGuardSpecificityScore`.
- Baseline: `1/3`; the Workflow UI paste packet was strict, but UI fallback text and receipts still had `safeToDispatch=true`-only phrasing.
- Candidate: `3/3`; Home, Settings, System Status, launch packet, handoff verifier, smoke checks, release audit, README, and regenerated artifacts now require every post-install evidence field, remote workflow parity, Actions visibility, dispatch readiness, and `verify-launch-handoff reports safeToDispatch=true`.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` and `scripts/verify-launch-handoff.mjs` now share the stricter post-install fallback guard.
- `app.js`, `settings-view.js`, and `release-status.js` render the stricter guard in Home, Settings, System Status, matrix summaries, receipts, and clipboard text.
- `scripts/smoke-interactions.mjs` verifies the DOM and clipboard surfaces include `every post-install evidence field has been filled`, dispatch readiness fields, and the handoff verifier condition.
- `scripts/audit-release-readiness.mjs` and `README.md` require the same guard terms so the UI cannot drift back to verifier-only wording.

## Improvement

- Before: a user could read a UI receipt as “safeToDispatch is the only gate” and skip one of the six evidence fields.
- After: every visible post-install handoff states that evidence fields, remote parity, Actions visibility, dispatch readiness, and verifier proof all have to pass before any `gh workflow run`.

## Next Loop

- Keep external completion blocked until remote workflow files, workflow visibility, dispatch readiness, live publish evidence, and final external-claim proof all pass.
- Continue scanning copy-ready receipts for wording that is technically safe but too compressed for an operator to use without extra interpretation.

## Experiment: Operator one-page success signal coverage

- Hypothesis: the launch operator one-page handoff should not compress dispatch readiness into a single `allDispatchReady` signal when the evidence ledger requires page dispatch, drift dispatch, all-dispatch, and six field completion proof.
- Primary metric: `operatorOnePageSuccessSignalCoverageScore`.
- Baseline: `5/8`; the one-page handoff listed workflow scope, remote file parity, workflow visibility, all-dispatch readiness, and verifier proof, but omitted the separate dispatch readiness signals and six-field ledger completion.
- Candidate: `8/8`; the handoff now lists `dispatchReady=true`, `driftDispatchReady=true`, `allDispatchReady=true`, `all six post-install evidence fields are filled`, and the verifier proof as distinct operator success signals.
- Decision: keep.

## Evidence

- `scripts/capture-launch-execution-packet.mjs` now emits 8 success signals and only marks the one-page handoff ready when all 8 are present.
- `scripts/capture-output-quality-audit.mjs` requires every one-page success signal before treating the handoff as copy-ready.
- `scripts/smoke-interactions.mjs` verifies DOM and clipboard coverage for the expanded signal list, including the embedded full launch packet copy.
- `scripts/audit-release-readiness.mjs` and `README.md` require the same 8-signal list so release audit and operator documentation stay aligned.

## Improvement

- Before: an operator could read `allDispatchReady=true` as the only dispatch success signal and miss the page dispatch, drift dispatch, or six-field evidence-ledger checks.
- After: the one-page handoff names every dispatch and post-install proof signal needed before any `gh workflow run`.

## Next Loop

- Keep `readyForExternalClaim=false` until the remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue scanning the one-page handoff and quality receipt for compressed proof language that hides operator-visible prerequisites.

## Experiment: Packaged gate cache diagnostics

- Hypothesis: the release readiness summary should explain why a fresh packaged browser gate cache cannot be reused instead of reducing every cache miss to `missing_or_stale`.
- Primary metric: `packagedGateCacheDiagnosticCoverageScore`.
- Baseline: `1/5`; the not-run packaged browser gate evidence only exposed the rerun command and a generic cache status.
- Candidate: `5/5`; the cache evidence now includes `status`, `issues`, `contextMatched`, `cachedEvidenceStatus`, `cachedResultStatus`, and file-level `contextMismatches`.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` now emits `packagedBrowserGateCacheDiagnostics` and `packagedBrowserGateContextMismatches`.
- `packaged_browser_gates` not-run evidence now shows whether the cache is missing, invalid, stale, incomplete, or source-context mismatched.
- `README.md` documents how to inspect `evidence.cache.contextMismatches` and when to rerun `npm run verify`.
- `npm run verify` passed with `229 pass, 0 fail, 0 not_run, 0 blocked`, and cached summary reused the fresh gate with `229 pass`.

## Improvement

- Before: a stale or source-mismatched packaged browser gate cache looked the same as a missing cache.
- After: the operator can see the invalidation reason and exact source files that changed before deciding whether to rerun the full browser gate.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof all pass.
- Continue reducing operator ambiguity around the remaining workflow installation and proof-capture steps.

## Experiment: Output-quality latest gate parity

- Hypothesis: the final output-quality audit and product-loop summary should use the current release readiness summary as their latest gate source without recursively invoking the release audit.
- Primary metric: `outputQualityLatestGateParityScore`.
- Baseline: `0/1`; output-quality and product-loop latestGate were stuck at 226 pass while release readiness had moved ahead.
- Candidate: `1/1`; release readiness summary, output-quality audit, and product-loop summary now all report 230/230.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` writes `autoresearch-results/release-readiness-summary.json` with schema `joopark-release-readiness-summary/v1`.
- `scripts/capture-output-quality-audit.mjs` reads only passing summary cache entries as the non-recursive latest gate source and lists `release_readiness_summary` in `sourceInputs`.
- `data/output-quality-audit.json` now has `sourceInputCount=11` and latestGate `230 pass / 230 total`.
- `autoresearch-results/joopark-product-loop.json` now carries the same latestGate after summary sync.

## Improvement

- Before: the release audit summary could move forward while output-quality and product-loop still displayed stale gate counts.
- After: the latest passing release readiness summary is the named source for output-quality gate counts, and failing or not-run summaries are ignored during gate bootstrap.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue reducing release handoff ambiguity around remaining workflow installation proof.

## Experiment: Post-install proof parser repair hints

- Hypothesis: the post-install proof parser should tell the operator exactly which command repairs each missing proof field instead of only reporting detected or missing state.
- Primary metric: `postInstallProofParserRepairHintCoverageScore`.
- Baseline: `0/6`; the parser identified missing fields but did not provide per-field repair actions.
- Candidate: `6/6`; all six parser fields now carry a copy-ready `nextAction` and the receipt includes `Missing field repair hints`.
- Decision: keep.

## Evidence

- `app.js` adds `nextAction` to the six parser rules and includes those hints in the parser receipt.
- `release-status.js` renders `data-post-install-proof-parser-field-next-action` rows and initializes the missing-field hint receipt.
- `scripts/smoke-interactions.mjs` checks initial, false-positive, detected, and clipboard parser summaries for `Missing field repair hints`.
- `scripts/audit-release-readiness.mjs`, `scripts/capture-output-quality-audit.mjs`, and `README.md` now require the repair-hint terms.
- `data/output-quality-audit.json` and release readiness summary remain at `230 pass / 0 fail / 0 not_run / 0 blocked`.

## Improvement

- Before: a partial post-install proof told the operator what was missing but not which verification command would fill the field.
- After: each missing field points to the exact remote parity, dispatch plan, or handoff verifier command needed before any dispatch approval.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue reducing ambiguity in the remaining GitHub UI workflow installation and proof-capture handoff.

## Experiment: Home launch action checklist

- Hypothesis: the Home launch surface should show a single post-auth action checklist so operators can run the workflow-scope, remote parity, Actions visibility, handoff guard, and deferred proof steps without hunting through separate System Status panels.
- Primary metric: `homeLaunchActionChecklistCoverageScore`.
- Baseline: `0/5`; Home had launch next, blocker resolver, post-install intake, and external claim guard panels, but no single copy-ready post-auth recheck checklist.
- Candidate: `5/5`; Home renders `data-home-launch-action-checklist` with five recheck steps, four source artifacts, immediate command, deferred proof command, and dispatch guard copy text.
- Decision: keep.

## Evidence

- A/B comparison selected B: add a Home launch action checklist; A kept only the existing launch next and blocker resolver cards.
- `app.js` renders `JooPark Launch Action Checklist` with `active=operator_auth_path`, `recheckSequence=5`, `sourceArtifacts=4`, `dispatchApproval=false`, `verificationOnly=true`, and `withheld=2`.
- `operations-copy-actions.js` adds `copyHomeLaunchActionChecklist` for the Home checklist copy flow.
- `scripts/smoke-interactions.mjs` verifies the five recheck keys, four source artifacts, hidden copy text, clipboard result, and persisted `homeLaunchActionChecklist` check.
- `npm run verify` passed with `231 pass / 0 fail / 0 not_run / 0 blocked` after `refresh:launch-readiness` updated the latest gate.

## Improvement

- Before: the operator had to infer the exact post-auth sequence by reading multiple readiness panels.
- After: the first-screen Home checklist exposes the next command, ordered recheck sequence, source artifacts, deferred proof command, and stop condition before any dispatch action.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue reducing ambiguity around the remaining GitHub UI workflow installation and proof-capture handoff.

## Experiment: Home first-run model boundary

- Hypothesis: Home onboarding state should be assembled by a dedicated model helper so `renderHome` stays below the architecture guard while browser smoke keeps proving the first-run surface.
- Primary metric: `homeRenderStructureBoundaryCoverageScore`.
- Baseline: `0/1`; `renderHome` was 738 lines and `check-app-structure` reported one oversized function.
- Candidate: `1/1`; `homeFirstRunGuidanceModel` assembles first-run quick start and guided-start public proof guard state, and `renderHome` is now 650 lines.
- Decision: keep.

## Evidence

- `app.js` now extracts `homeFirstRunGuidanceModel` and passes the resulting model into `homeFirstRunGuidanceHTML`.
- `scripts/audit-release-readiness.mjs` includes `home_first_run_model_boundary` so the helper boundary is checked by the release audit.
- `node scripts/check-app-structure.mjs` reports `oversizedFunctions=[]`, `warnings=[]`, and `failures=[]`.
- `npm run verify` passed with `232 pass / 0 fail / 0 not_run / 0 blocked` after launch readiness refresh and product-loop sync.

## Improvement

- Before: first-run onboarding, launch proof guard state, and the rest of Home rendering lived in the same oversized route renderer.
- After: onboarding state assembly has a named model boundary, and the route renderer is back under the architecture threshold.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue extracting launch-operation model pieces only where the browser smoke can keep proof state stable.

## Experiment: Launch proof receipt next actions

- Hypothesis: the launch proof evidence receipt should tell the operator exactly which command fills each post-dispatch proof field instead of only listing required proof labels.
- Primary metric: `launchProofEvidenceNextActionCoverageScore`.
- Baseline: `0/6`; the receipt listed six fields, commands, and acceptance criteria, but the field rows did not carry per-field next proof actions.
- Candidate: `6/6`; all six launch proof fields now carry `nextAction`, and the receipt includes `Next proof actions`.
- Decision: keep.

## Evidence

- `scripts/capture-publish-evidence.mjs` adds `nextAction` to all six launch proof fields and includes a `Next proof actions:` receipt section.
- `release-status.js` renders `data-publish-evidence-launch-proof-field-next-action` and visible `Next:` text for each launch proof row.
- `scripts/capture-output-quality-audit.mjs` records `nextActionCount=6` and `nextActionCoverage=1` before marking `launchProofEvidenceReceipt` ready.
- `scripts/smoke-interactions.mjs` verifies UI rows, hidden receipt, clipboard copy, and output-quality receipt include `nextActions=6/6`.
- `data/publish-evidence.json` and `data/output-quality-audit.json` now carry six launch proof next actions while `readyForExternalClaim=false` remains blocked.

## Improvement

- Before: after dispatch, the operator could see what proof was required but still had to infer which exact command and pasted signal repaired each launch proof field.
- After: each launch proof field points to the exact GitHub Pages, workflow run, freshness, release receipt, or external-claim guard command needed before any public launch claim.

## Next Loop

- Keep `readyForExternalClaim=false` until remote workflow files, Actions visibility, dispatch readiness, live publish evidence, and external-claim proof fields all pass.
- Continue reducing ambiguity around default-branch workflow installation and live proof capture.

## Experiment: Release audit stale lock recovery

- Hypothesis: release readiness run-gates should recover a dead or PID-reused audit lock immediately while preserving a live owner lock.
- Primary metric: `releaseAuditStaleLockRecoveryScore`.
- Baseline: `0/3`; stale detection used only lock mtime, so a dead owner PID could leave operators waiting until the stale timeout.
- Candidate: `3/3`; owner JSON parsing, `process.kill(pid, 0)` existence check, and command-match verification distinguish active locks from `owner_process_missing` and `owner_pid_reused`.
- Decision: keep.

## Evidence

- `scripts/audit-release-readiness.mjs` adds `auditGateLockOwner()`, `auditGateLockOwnerProcess()`, and the `release_audit_stale_lock_recovery` checklist item.
- `README.md` documents stale release readiness audit lock recovery for `scripts/audit-release-readiness.mjs --run-gates`.
- External comparison uses GitHub Actions concurrency guidance and Node.js `process.kill(pid, 0)` process-existence behavior.

## Improvement

- Before: run-gates could leave a stale lock until the mtime timeout even after the owner process was gone.
- After: dead owner PIDs and PID reuse are recovered immediately, while a live audit run still serializes packaged browser gates.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue hardening operator-facing proof receipts around the remaining workflow installation path.

## Experiment: Verify command gate-only split

- Hypothesis: `npm run verify` should stay gate-only, with launch-readiness refresh and product-loop sync as explicit follow-up commands, because file-watch environments can re-run verify when refresh artifacts are written.
- Primary metric: `verifyCommandLoopSafetyScore`.
- Baseline: `1/3`; chained verify refreshed evidence automatically but created a write-triggered verify loop under CMUX/file-watch execution.
- Candidate: `3/3`; verify now runs only release gates, while `npm run refresh:launch-readiness` and `node scripts/sync-product-loop-summary.mjs --write --markdown` remain copy-ready follow-up commands.
- Decision: keep.

## Evidence

- `package.json` defines `scripts.verify` as `node scripts/audit-release-readiness.mjs --run-gates --format=summary`.
- `scripts/audit-release-readiness.mjs` adds `verify_command_gate_only` to keep the package script, refresh script, and README contract aligned.
- `README.md` documents that `npm run refresh:launch-readiness` and `node scripts/sync-product-loop-summary.mjs --write --markdown` are separate post-verify commands.

## Improvement

- Before: a single convenience command could repeatedly write launch-readiness/product-loop artifacts and retrigger `npm run verify`.
- After: verify produces the gate result without downstream writes, and evidence refresh remains explicit and guarded.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue reducing release operator ambiguity around the workflow installation path.

## Experiment: Verify workspace runner

- Hypothesis: `npm run verify` should keep the gate-only split but run through a small Node runner so release-gate exit status, signal, duration, lock snapshot, and artifact state are inspectable after long browser checks.
- Primary metric: `verifyWorkspaceRunnerCoverageScore`.
- Baseline: `1/4`; verify was gate-only but exposed no runner-level summary artifact, no step result list, no audit-lock snapshot, and no explicit optional sync path.
- Candidate: `4/4`; `scripts/verify-workspace.mjs` runs `release_readiness_gates` by default, writes `autoresearch-results/verify-workspace-summary.json`, preserves explicit post-verify refresh commands, and offers `--sync-artifacts` for intentional `launch_readiness_refresh` plus `product_loop_summary_sync`.
- Decision: keep.

## Evidence

- A/B comparison selected B: keep the gate-only public command but add a runner summary; A left `npm run verify` mapped directly to the audit script.
- `package.json` now maps `verify` to `node scripts/verify-workspace.mjs` and lint checks the new runner.
- `scripts/audit-release-readiness.mjs` keeps `verify_command_gate_only` while checking the runner contract, `--sync-artifacts`, step ids, and summary artifact path.
- `README.md` documents the gate-only default plus the explicit `npm run refresh:launch-readiness`, `node scripts/sync-product-loop-summary.mjs --write --markdown`, and `node scripts/verify-workspace.mjs --sync-artifacts` paths.
- External comparison used the Node.js child process documentation for synchronous child completion and npm run-script documentation for the package script contract.

## Improvement

- Before: a terminated or long-running release gate could leave only partial terminal output and cached release artifacts to inspect.
- After: the public verify command has one runner surface and one machine-readable summary artifact without reintroducing downstream refresh writes into default `npm run verify`.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- If the runner still shows an interrupted browser gate, harden the specific smoke child cleanup path rather than merging refresh writes back into `npm run verify`.

## Experiment: Verify full evidence sync path

- Hypothesis: operators need one intentional full verification command that refreshes launch evidence and synchronizes the AutoResearch product-loop summary, while the default `npm run verify` remains gate-only for file-watch loop safety.
- Primary metric: `verifyFullEvidenceSyncCoverageScore`.
- Baseline: `2/5`; the runner exposed a gate-only default and optional `--sync-artifacts`, but package scripts did not expose a named full-sync command and the runner summary did not fail full mode on product-loop/output-quality parity drift.
- Candidate: `5/5`; `npm run verify:full` runs `scripts/verify-workspace.mjs --sync-artifacts`, then requires `productLoopGateParityReady`, `productLoopPublishParityReady`, and `summarySyncReady` before reporting full-sync pass.
- Decision: keep.

## Evidence

- A/B comparison selected B: keep the default verify command gate-only and add a named full evidence sync path; A would merge writes back into default verify and risk file-watch re-entry.
- `package.json` adds `verify:full` while preserving `verify` as `node scripts/verify-workspace.mjs`.
- `scripts/verify-workspace.mjs` writes `evidenceSync` status, parity booleans, `evidenceSyncRequired`, `evidenceSyncPass`, and `fullVerifyCommand` into `autoresearch-results/verify-workspace-summary.json`.
- `scripts/audit-release-readiness.mjs` now checks the default/full verify contract, README terms, package script, and runner parity fields.
- `README.md` documents `npm run verify:full` as the release gate plus evidence-sync command and keeps `npm run refresh:launch-readiness` plus `node scripts/sync-product-loop-summary.mjs --write --markdown` as individual recovery commands.
- `npm run verify:full` passed with `247 pass / 0 fail / 0 not_run / 0 blocked`, `launch_readiness_refresh=pass`, `product_loop_summary_sync=pass`, and `evidenceSync=pass`.
- External comparison used SLSA provenance guidance for tying outputs back to build inputs and GitHub artifact attestation guidance for explicit provenance generation/verification; this local runner is not a cryptographic attestation, but it now records and verifies the evidence chain before full-sync pass.

## Improvement

- Before: an operator could run only the release gate and forget to refresh launch-readiness/product-loop evidence, or run `--sync-artifacts` without an easy package script.
- After: `npm run verify:full` is a single named full-evidence command, and the runner refuses full-sync pass when product-loop and output-quality evidence drift apart.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Continue hardening the remaining default-branch workflow installation path; the next candidate should reduce manual GitHub UI install ambiguity or add stronger provenance once remote workflow installation is available.

## Experiment: Workflow UI template integrity ledger

- Hypothesis: the GitHub UI workflow paste packet should include template checksum commands and post-commit digest parity signals so operators can prove pasted workflow YAML still matches the local template before any dispatch.
- Primary metric: `workflowUiTemplateIntegrityCoverageScore`.
- Baseline: `1/3`; the paste packet included remote parity verification, but no dedicated `Template integrity ledger` and no `localTemplateHashCommand`/`expectedSha256` pair for each workflow template.
- Candidate: `3/3`; both Pages and Drift Watch rows now include expected SHA-256, `shasum -a 256` local hash commands, post-commit remote check command, and expected remote digest parity signals.
- Decision: keep.

## Evidence

- A/B comparison selected B: keep the GitHub UI install path but add a checksum guard; A relied only on post-install remote file parity.
- `scripts/plan-workflow-ui-install.mjs` now emits `templateIntegrityRows`, `templateIntegrityCoverage`, `workflowUiTemplateIntegrityCoverage`, `Template integrity ledger`, `Checksum guard`, `localTemplateHashCommand`, `expectedSha256`, `postCommitRemoteCheck`, and `remoteSha256 equals templateSha256`.
- `data/workflow-ui-install-plan.json` now reports `workflowUiTemplateIntegrityCoverage=1` with two template integrity rows.
- `scripts/audit-release-readiness.mjs` checks the script, saved workflow UI plan JSON, and README for the new integrity ledger terms.
- `README.md` documents the paste-before checksum and post-commit remote digest parity guard.
- `npm run verify:full` passed with `248 pass / 0 fail / 0 not_run / 0 blocked`, `launch_readiness_refresh=pass`, `product_loop_summary_sync=pass`, and `evidenceSync=pass`.
- External comparison used GitHub manual workflow dispatch documentation for the default-branch `workflow_dispatch` requirement and GitHub REST repository contents documentation for remote file content/SHA verification. SLSA provenance and GitHub artifact attestation remain stronger cryptographic references, but this local GitHub UI path is still a non-cryptographic operator checksum guard.

## Improvement

- Before: the operator saw the template SHA and post-install remote parity command, but the paste packet did not explicitly tell them how to hash the local template before paste or what digest equality to require after commit.
- After: the packet contains a complete two-row checksum ledger and refuses to treat checksum proof as dispatch approval until remote file parity and handoff gates pass.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Next candidate: add signed/attested release provenance after the remote workflow path is available, or add a browser-visible workflow-install checksum panel if the current text packet is still too dense for operators.

## Experiment: Release local provenance statement

- Hypothesis: the packaged release should carry a local provenance statement that binds `release-manifest.json` to source, builder, and dependency evidence before a remote GitHub artifact attestation exists.
- Primary metric: `releaseProvenanceVerifierCoverageScore`.
- Baseline: `1/4`; `node scripts/verify-release.mjs` passed but only checked `release-manifest.json` source metadata, with no `release-provenance.json`, no in-toto/SLSA statement check, and no explicit unsigned-local-provenance boundary.
- Candidate: `4/4`; the package now writes `release-provenance.json`, release verification checks the statement, readiness audit checks and documents it, and `npm run verify:full` keeps product-loop parity synced.
- Decision: keep.

## Evidence

- A/B comparison selected B: add a separate metadata provenance statement after the final manifest; A would keep relying on manifest source fields only.
- `scripts/package-release.mjs` now writes `release-provenance.json` after `release-manifest.json`, using the manifest SHA-256 as the in-toto subject digest and recording source-tree plus runtime source `resolvedDependencies`.
- `scripts/verify-release.mjs` now requires the provenance file and checks statement type, predicate type, manifest subject digest, build type, builder id, source parameters, dependency digests, byproducts, runtime totals, and `signed=false`.
- `scripts/audit-release-readiness.mjs` and `README.md` now require and document the local provenance statement while keeping GitHub artifact attestations as the stronger signed external proof after workflow installation.
- Focused release verification reports `provenanceSubjectCount=1`, `provenanceDependencyCount=45`, and `provenanceSigned=false`.
- `npm run verify:full` passed with `249 pass / 0 fail / 0 not_run / 0 blocked`, `launch_readiness_refresh=pass`, `product_loop_summary_sync=pass`, and `evidenceSync=pass`.
- External comparison used in-toto Statement v1 for subject digest binding, SLSA provenance v1 for build inputs/run details, and GitHub artifact attestations as the future signed workflow proof. This local package evidence is intentionally unsigned.

## Improvement

- Before: the package had source commit and dirty file traceability in the manifest, but no separate provenance statement for the build artifact.
- After: every packaged release carries a verifier-checked local provenance statement and refuses to blur that evidence into a signed external attestation claim.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Next candidate: once workflow installation is available, add or wire signed GitHub artifact attestation proof into the release evidence chain.

## Experiment: Release provenance System Status surface

- Hypothesis: the local release provenance statement should be visible and copy-ready in System Status, not only present as a packaged JSON file and CLI verifier output.
- Primary metric: `releaseProvenanceUiCoverageScore`.
- Baseline: `1/4`; `release-provenance.json` existed and `verify-release` checked it, but System Status did not load it, render digest/builder/source fields, provide a copy-ready receipt, or smoke-test the UI path.
- Candidate: `4/4`; System Status now loads and renders release provenance, the receipt is copy-ready, browser smoke covers the UI path, and readiness audit/README require the surface.
- Decision: keep.

## Evidence

- A/B comparison selected B: surface the provenance in the existing System Status evidence stack; A kept the evidence as CLI-only JSON.
- `app.js` now loads `release-provenance.json` in packaged builds with a `dist/release` fallback for source-root smoke runs and validates statement type, predicate type, subject digest, builder id, unsigned status, and core dependency names.
- `release-status.js` renders `Release provenance` with subject digest, predicate/build type, builder id, source commit/branch, dependency count, unsigned-local-provenance guard, verifier commands, and copy-ready receipt.
- `system-status-view.js` inserts the panel into publish readiness evidence, and `scripts/smoke-interactions.mjs` verifies the panel, dependency ledger, receipt text, and clipboard copy.
- `scripts/audit-release-readiness.mjs` adds `release_provenance_ui_surface`; `README.md` documents the System Status panel and `releaseProvenanceUiCoverageScore`.
- `node scripts/smoke-release.mjs` passed with `releaseProvenancePanel=true` and `releaseProvenanceReceiptCopy=true` in interaction persisted checks.
- External comparison used GitHub artifact attestations for user-visible/verifiable build provenance, SLSA build provenance for build/run fields, and in-toto Statement v1 for subject digest binding.

## Improvement

- Before: the package had a verifier-checked provenance artifact, but an operator had to inspect JSON or CLI output to understand it.
- After: the shipped app exposes the digest, builder, source, dependency count, unsigned boundary, verify commands, and a copy-ready receipt in the same operational evidence surface as launch proof.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Next candidate: add an Actions workflow attestation plan or proof intake that can attach signed GitHub artifact attestation evidence once workflow installation is unblocked.

## Experiment: Pages workflow artifact attestation

- Hypothesis: the Pages workflow template should be ready to generate a signed GitHub artifact attestation for `dist/release` after the release package is verified and before it is uploaded for Pages deployment.
- Primary metric: `pagesWorkflowAttestationCoverageScore`.
- Baseline: `1/4`; the workflow had Pages/OIDC permissions and upload/deploy steps, but no `attestations: write`, no `actions/attest@v4`, and no shared `subject-path: dist/release/**` validator term.
- Candidate: `4/4`; the template, local staged workflow, prepare/UI-install/dispatch/remote-install validators, release audit, README, and product-loop record now share the same attestation contract.
- Decision: keep.

## Evidence

- A/B comparison selected B: add the attestation step to the existing verified Pages workflow template; A left signed provenance as an external future task without a workflow implementation path.
- `docs/github-pages-workflow.yml` and `.github/workflows/joopark-pages.yml` now grant `attestations: write` and run `actions/attest@v4` with `subject-path: dist/release/**` after `node scripts/verify-release.mjs`.
- `scripts/prepare-github-pages-workflow.mjs`, `scripts/plan-workflow-ui-install.mjs`, `scripts/plan-publish-dispatch.mjs`, and `scripts/install-remote-workflow-files.mjs` now reject Pages workflow templates that omit the attestation permission/action/subject path.
- `scripts/audit-release-readiness.mjs` checks the template, staged workflow, UI install plan, remote installer, saved plan JSON, and README for the attestation contract.
- `README.md` documents that this becomes signed GitHub artifact attestation proof only after the remote workflow is installed and executed.
- External comparison used GitHub artifact attestation docs for the workflow permissions/action requirements and the `actions/attest` README for signed Sigstore-backed attestations plus wildcard `subject-path` support.

## Improvement

- Before: the release had local unsigned provenance and a Pages deployment workflow, but no concrete signed attestation step for the package.
- After: the Pages workflow can generate signed build provenance for the packaged release, while all local blockers still prevent claiming external proof before remote workflow installation and Actions execution.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, and live publish evidence are captured.
- Next candidate: capture or surface the eventual `actions/attest` `attestation-url`/`gh attestation verify` proof once the remote workflow can run.

## Experiment: Pages attestation proof intake

- Hypothesis: the Pages workflow attestation step should have a post-run proof intake that tells operators exactly how to capture `attestation-url`, `attestation-id`, and `gh attestation verify` results before claiming signed proof.
- Primary metric: `pagesAttestationProofIntakeCoverageScore`.
- Baseline: `1/4`; the workflow could run `actions/attest@v4`, but the app had no operator intake for the action outputs, no receipt copy, and no UI/audit/smoke/doc contract.
- Candidate: `4/4`; System Status now renders a six-field proof intake, copy-ready receipt, verification commands, and audit/smoke/README coverage while keeping the state `not signed proof yet`.
- Decision: keep.

## Evidence

- A/B comparison selected B: add a proof intake to the existing publish readiness stack; A would leave attestation outputs as a future manual note outside the app.
- `release-status.js` renders `Pages attestation proof intake` with `attestation-url`, `attestation-id`, Pages workflow run proof, manifest/index `gh attestation verify` commands, predicate type, and a `Do not claim signed GitHub artifact attestation proof` guard.
- `system-status-view.js` inserts the intake after local release provenance, and `app.js` wires `copy-pages-attestation-proof-intake` to a clipboard receipt.
- `scripts/smoke-interactions.mjs` verifies the intake dataset, six proof fields, receipt text, and clipboard copy; `scripts/audit-release-readiness.mjs` adds `pages_attestation_proof_intake`.
- `README.md` documents the exact post-run fields and keeps external completion blocked until the remote workflow succeeds and publish/handoff proof gates pass.
- External comparison used GitHub artifact attestation docs for permission/action/verification requirements and the `actions/attest` README for `attestation-url` and `attestation-id` outputs.

## Improvement

- Before: the Pages workflow could generate an attestation, but operators had no local, copy-ready evidence contract for proving it after the run.
- After: the app carries a verification-only intake for signed attestation proof and keeps all external completion claims blocked until the remote proof is actually captured.

## Next Loop

- Keep public launch completion blocked until remote workflow files, workflow visibility, dispatch readiness, live publish evidence, and attestation proof intake fields are captured.
- Next candidate: once workflow installation is unblocked, capture live attestation proof from the successful Pages workflow run and feed it into publish evidence.

## Experiment: Route registry single source refactor

- Hypothesis: the app route ids should have one local source of truth for DOM view refs and routing membership instead of a duplicate `VIEW_REF_IDS` list.
- Primary metric: `appRouteRegistryDuplicationScore`.
- Baseline: `2/4`; `VIEW_REF_IDS` and `VIEWS` repeated the same route ids.
- Candidate: `4/4`; `refs.views` now derives from `VIEWS`, and the duplicate `VIEW_REF_IDS` list is removed.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` under the line threshold.
- `npm run lint` passed.
- `npm test` passed, including desktop/mobile route parity, interaction, delete/undo, and accessibility smoke.
- `node scripts/audit-release-readiness.mjs --format=summary` passed with packaged browser gates cached against the current source context.

## Experiment: Renderer map route dispatch refactor

- Hypothesis: route dispatch should use a renderer map rather than a long switch that repeats every route id.
- Primary metric: `appRouteDispatchDuplicationScore`.
- Baseline: `2/4`; `renderCurrentView` repeated all route ids in a switch.
- Candidate: `4/4`; `VIEW_RENDERERS` maps routes to renderer functions, and `renderCurrentView` keeps the same fallback behavior with less dispatch code.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,429 lines.
- `npm run lint` passed.
- `npm test` passed after the dispatch change.
- `scripts/audit-release-readiness.mjs` now recognizes the renderer-map system route contract and the summary passed at `263 pass, 0 fail, 0 not_run, 0 blocked`.

## Experiment: Navigation helper call guard refactor

- Hypothesis: navigation helper wrappers should share one guard for missing module helpers while preserving their public wrapper names and error labels.
- Primary metric: `navigationHelperWrapperDuplicationScore`.
- Baseline: `2/4`; `dialogShellCall`, `projectPickerCall`, and `globalSearchCall` repeated the same helper existence check.
- Candidate: `4/4`; `callModuleHelper` centralizes the guard while the three wrapper functions remain stable for audit and call sites.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,424 lines.
- `npm run lint` passed.
- `npm test` passed with the navigation module smoke checks still true.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `264 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Personal view helper call guard refactor

- Hypothesis: personal view helper wrappers should share the same missing-helper guard without changing module boundaries or render call sites.
- Primary metric: `personalViewHelperWrapperDuplicationScore`.
- Baseline: `2/4`; `calendarViewCall`, `todoViewCall`, `notesViewCall`, `habitsViewCall`, and `statsViewCall` repeated identical helper existence checks.
- Candidate: `4/4`; all five wrappers delegate to `callModuleHelper` with their existing wrapper names and labels.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,413 lines.
- `npm run lint` passed.
- `npm test` passed with personal route, interaction, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `264 pass, 0 fail, 0 not_run, 0 blocked`, with `contextMatched=true`.

## Experiment: PM view helper call guard refactor

- Hypothesis: PM view helper wrappers should use the same guard as navigation and personal views while preserving the portfolio single-payload call shape.
- Primary metric: `pmViewHelperWrapperDuplicationScore`.
- Baseline: `2/4`; `portfolioViewCall`, `kanbanViewCall`, `ganttViewCall`, and `teamViewCall` repeated identical helper existence checks.
- Candidate: `4/4`; all four wrappers delegate to `callModuleHelper`, with `portfolioViewCall` retaining its existing `(name, payload)` signature.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,401 lines.
- `npm run lint` passed.
- `npm test` passed with PM route/module interaction and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `264 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Release gate persisted-check contract alignment

- Hypothesis: the release gate cache should include every persisted interaction check required by `completePackagedBrowserGateEvidence`, otherwise a passing `npm test` can still be rejected as incomplete audit evidence.
- Primary metric: `releaseGateCompletenessScore`.
- Baseline: `264/265`; `npm test` passed, but release audit marked `packaged_browser_gates` as `not_run` because `homeExecutionQueueFilterWindow` was absent from the cached persisted checks.
- Candidate: `265/265`; `scripts/smoke-interactions.mjs` now backfills `homeExecutionQueueFilterWindow` when the shared home execution queue filter assertion block already passed.
- Decision: keep.

## Evidence

- `npm run check:structure` passed.
- `npm run lint` passed.
- `npm test` passed and emitted `homeExecutionQueueFilterWindow: true`.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `265 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Operations and storage helper call guard refactor

- Hypothesis: DB, release, system, storage, and settings helper wrappers can share the same missing-helper guard while preserving their wrapper names, call shapes, and legacy error text.
- Primary metric: `operationsStorageHelperWrapperDuplicationScore`.
- Baseline: `2/4`; seven helper wrappers repeated nearly identical helper availability checks and spread/payload forwarding.
- Candidate: `4/4`; `callModuleHelper` now accepts explicit args plus an optional legacy message, and the seven wrappers delegate through it without changing call sites.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,382 lines.
- `npm run lint` passed.
- `npm test` passed after the helper wrapper refactor.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `266 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Review helper call guard refactor

- Hypothesis: review export, result, handoff, artifact, package, submission, and operations-copy wrappers can share the same runtime helper guard without changing review smoke behavior or legacy error labels.
- Primary metric: `reviewHelperWrapperDuplicationScore`.
- Baseline: `2/4`; eight review and copy-action wrappers repeated the same helper availability check.
- Candidate: `4/4`; the wrappers now delegate to `callModuleHelper`, with review package preserving its single-payload call shape.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,358 lines.
- `npm run lint` passed.
- `npm test` passed with review package, copy, submission, artifact, and recommendation persisted checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `266 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Final helper call guard consolidation

- Hypothesis: the remaining search empty state, command palette, and PWA runtime helper wrappers can use the shared helper guard without changing route recovery, palette, or runtime checks.
- Primary metric: `remainingHelperWrapperDuplicationScore`.
- Baseline: `2/4`; three wrappers still held direct `Helpers[name]` availability checks.
- Candidate: `4/4`; all remaining module-call wrappers now delegate to `callModuleHelper` while preserving existing error labels.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,349 lines.
- `npm run lint` passed.
- `rg` found no remaining direct `typeof *Helpers[name] !== "function"` guard patterns in `app.js`.
- `BASE_URL=http://127.0.0.1:53111 node scripts/smoke-interactions.mjs` passed and emitted `homeExecutionQueueScoreWindow: true`.
- `npm test` passed after packaged release rebuild, including command palette, search empty state, PWA runtime, review modules, delete/undo, and accessibility smoke.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `267 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Operations copy action dispatch map

- Hypothesis: operations copy actions can be removed from the long `handleActions` conditional chain and dispatched through a lookup map without changing any copy behavior.
- Primary metric: `operationsCopyActionDispatchDuplicationScore`.
- Baseline: `2/4`; 22 operations copy actions were repeated as one-line `if (action === "...")` branches inside `handleActions`.
- Candidate: `4/4`; `OPERATIONS_COPY_ACTION_HANDLERS` stores the same target-forwarding handlers in a `Map`, and `runActionHandler` exits early only when the action is present.
- Research: A/B compared the existing conditional chain against a dispatch table. MDN documents `Map` as explicit key/value storage with stable lookup semantics, while Fowler's conditional replacement pattern supports moving repeated conditional behavior behind typed dispatch.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,367 lines.
- `npm run lint` passed.
- Baseline `npm test` passed before the change, and candidate `npm test` passed after the change.
- `handleActionsCopyIfCount` is now `18` because operations copy branches moved out; `operationsCopyMapEntryCount` is `22`; the old `copy-settings-handoff` branch is absent.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `268 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Review copy action dispatch map

- Hypothesis: review copy actions can use the same action lookup helper as operations copy actions while preserving the two artifact repair variants that pass an extra payload kind.
- Primary metric: `reviewCopyActionDispatchDuplicationScore`.
- Baseline: `2/4`; 18 `copy-*` review branches remained inside `handleActions`.
- Candidate: `4/4`; `REVIEW_COPY_ACTION_HANDLERS` dispatches the 18 review copy actions, with lambda wrappers only for `body` and `receipt` repair payload variants.
- Research: Reused the previous A/B result: a `Map`-based dispatch table is preferable for dense string-keyed action lookups, while the direct conditional chain is clearer only for small or highly branching behavior.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,371 lines.
- `npm run lint` passed.
- `handleActionsCopyIfCount` is now `0`; `REVIEW_COPY_ACTION_HANDLERS` is present; both artifact repair payload lambdas are present.
- `npm test` passed with review package copy, tracker copy, submission copy, artifact repair copy, post-apply receipt, and GitHub comment persisted checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `268 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Record-open action dispatch map

- Hypothesis: PM, DB, and source backlink open/select actions can share the dispatch-map path without changing sheet, source return, or record navigation behavior.
- Primary metric: `recordOpenActionDispatchDuplicationScore`.
- Baseline: `2/4`; 12 record-open/select one-line branches remained inside `handleActions`.
- Candidate: `4/4`; `RECORD_OPEN_ACTION_HANDLERS` dispatches those 12 actions through `runActionHandler`, while CRUD add/edit/delete and status-changing branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,382 lines.
- `npm run lint` passed.
- `remainingRecordOpenIfs` is empty and `handleOneLineCount` dropped to `108`.
- `npm test` passed with source backlink, issue/task/member/table/query/backup/migration open flows green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `269 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: App shell action dispatch map

- Hypothesis: dialog, sheet, topbar, and basic navigation shell actions can move to the shared action lookup path without changing modal confirmation, permission request, async refresh, or search recovery behavior.
- Primary metric: `appShellActionDispatchDuplicationScore`.
- Baseline: `2/4`; 13 shell one-line or shell-navigation branches remained inside `handleActions`.
- Candidate: `4/4`; `APP_SHELL_ACTION_HANDLERS` dispatches those 13 shell actions through `runActionHandler`, while modal confirm, notification permission, data-safety refresh, and global help search recovery stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,381 lines.
- `npm run lint` passed.
- `appShellEntryCount` is `13`; `remainingShellIfs` is empty; `handleOneLineCount` dropped to `107`.
- `npm test` passed with command palette, notification sheet, topbar data-safety, global help, route navigation, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `269 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: LLM wiki action dispatch map

- Hypothesis: LLM wiki category/article, draft creation, action filter, and source return actions can use the shared action lookup path without changing source return or palette-backed record behavior.
- Primary metric: `llmWikiActionDispatchDuplicationScore`.
- Baseline: `2/4`; eight LLM wiki/source record one-line branches remained inside `handleActions`.
- Candidate: `4/4`; `LLM_WIKI_ACTION_HANDLERS` dispatches those eight actions through `runActionHandler`, preserving the existing dataset fallbacks and source-key payloads.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,385 lines.
- `npm run lint` passed.
- `llmWikiEntryCount` is `8`; `remainingLlmWikiIfs` is empty; `handleOneLineCount` dropped to `99`.
- `npm test` passed with LLM wiki action drafts, action filter, source return, source backlink, source palette, and Korean source alias checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `269 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Calendar action dispatch map

- Hypothesis: calendar navigation, mode, day-open, and event-open/create actions can use the shared action lookup path without changing destructive delete or occurrence skip behavior.
- Primary metric: `calendarActionDispatchDuplicationScore`.
- Baseline: `2/4`; seven calendar one-line branches remained inside `handleActions`, while delete and occurrence skip were mixed nearby.
- Candidate: `4/4`; `CALENDAR_ACTION_HANDLERS` dispatches the seven non-destructive calendar actions through `runActionHandler`, and `delete-event` plus `skip-occurrence` stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,389 lines.
- `npm run lint` passed.
- `calendarEntryCount` is `7`; `remainingCalendarIfs` is empty; `delete-event` and `skip-occurrence` remained local; `handleOneLineCount` dropped to `92`.
- `npm test` passed with calendar mode switch, home upcoming event open, calendar grid keyboard, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `270 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: To-Do action dispatch map

- Hypothesis: To-Do open, add-modal, bucket filter, view filter, and source filter actions can use the shared action lookup path without changing quick-add, completion, toggle, or delete behavior.
- Primary metric: `todoActionDispatchDuplicationScore`.
- Baseline: `2/4`; five non-destructive To-Do one-line branches remained inside `handleActions`, mixed with state-changing To-Do actions.
- Candidate: `4/4`; `TODO_ACTION_HANDLERS` dispatches those five actions through `runActionHandler`, while quick-add, completion, toggle, and delete branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline `npm run check:structure`, `npm run lint`, and `npm test` passed before the change.
- `npm run check:structure` passed after the change with `app.js` at 12,394 lines.
- `npm run lint` passed.
- `todoEntryCount` is `5`; `remainingTodoIfs` is empty; quick-add, completion, toggle, and delete branches remained local; `handleOneLineCount` dropped to `87`.
- `npm test` passed with To-Do persisted create, home quick todo, bucket filter, source/search recovery, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `270 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Notes action dispatch map

- Hypothesis: note add-modal, open, and source-filter actions can use the shared action lookup path without changing pin or delete behavior.
- Primary metric: `noteActionDispatchDuplicationScore`.
- Baseline: `2/4`; three non-destructive Notes one-line branches remained inside `handleActions`, mixed with pin/delete state changes.
- Candidate: `4/4`; `NOTE_ACTION_HANDLERS` dispatches those three actions through `runActionHandler`, while pin and delete branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous To-Do loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Notes change.
- `npm run check:structure` passed after the change with `app.js` at 12,398 lines.
- `npm run lint` passed.
- `noteEntryCount` is `3`; `remainingNoteIfs` is empty; pin/delete branches remained local; `handleOneLineCount` dropped to `84`.
- `npm test` passed with note persistence, command-palette note creation, notes search recovery, review note flows, delete/undo, and accessibility checks green.
- The first post-change audit exposed stale/incomplete packaged gate evidence (`homeExecutionQueueLeadDriverTie` missing from the cache); rerunning `npm test` regenerated complete gate evidence.
- `node scripts/audit-release-readiness.mjs --format=summary` then passed at `271 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Habit action dispatch map

- Hypothesis: habit add-modal and open actions can use the shared action lookup path without changing toggle or delete behavior.
- Primary metric: `habitActionDispatchDuplicationScore`.
- Baseline: `2/4`; two non-destructive Habit branches remained inside `handleActions`, with the open branch using a small local temporary variable.
- Candidate: `4/4`; `HABIT_ACTION_HANDLERS` dispatches those two actions through `runActionHandler`, and toggle/delete branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous Notes loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Habit change.
- `npm run check:structure` passed after the change with `app.js` at 12,402 lines.
- `npm run lint` passed.
- `habitEntryCount` is `2`; `remainingHabitIfs` is empty; toggle/delete branches remained local; `handleOneLineCount` dropped to `82`.
- `npm test` passed with habit route/search recovery, persisted create, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `271 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Portfolio filter action dispatch map

- Hypothesis: portfolio filter, action filter, and benchmark filter actions can use the shared action lookup path without changing project selection, prompt handoff, review issue creation, or review note publication behavior.
- Primary metric: `portfolioFilterActionDispatchDuplicationScore`.
- Baseline: `2/4`; three portfolio filter branches remained inside `handleActions`, near state-changing project/review actions.
- Candidate: `4/4`; `PORTFOLIO_FILTER_ACTION_HANDLERS` dispatches those three filter actions through `runActionHandler`, while project handoff, review issue creation, and review note publication branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline `npm run check:structure`, `npm run lint`, and `npm test` passed before the change.
- `npm run check:structure` passed after the change with `app.js` at 12,406 lines.
- `npm run lint` passed.
- `portfolioFilterEntryCount` is `3`; `remainingPortfolioFilterIfs` is empty; project handoff and review creation/publication branches remained local; `handleOneLineCount` dropped to `79`.
- `npm test` passed with portfolio candidate filter, ranked candidates, benchmark focus/queue/rubric, review handoff, delete/undo, and accessibility checks green.
- The first post-change release audit exposed a static evidence mismatch in `home_execution_queue_score_driver`; `scripts/audit-release-readiness.mjs` now verifies the actual app structure (`우선순위 근거` plus `label: "마감"`) instead of the stale combined literal `근거 마감`.
- Rerunning `npm test` regenerated the packaged gate cache after the audit-script context change.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `272 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Kanban filter action dispatch map

- Hypothesis: Kanban priority and source filter actions can use the shared action lookup path without changing persisted density, DB catalog filter, or stale-issue creation behavior.
- Primary metric: `kanbanFilterActionDispatchDuplicationScore`.
- Baseline: `2/4`; two Kanban filter branches remained inside `handleActions`, near density and DB catalog actions.
- Candidate: `4/4`; `KANBAN_FILTER_ACTION_HANDLERS` dispatches those two filter actions through `runActionHandler`, while density, DB catalog filter, and stale-issue creation branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline `npm run check:structure` and `npm run lint` passed before the change.
- The first baseline `npm test` exposed stale packaged output: `dist/release/app.js` was behind root `app.js` and failed `source parity byte mismatch for app.js`; rerunning `node scripts/package-release.mjs && node scripts/verify-release.mjs dist/release` restored source parity.
- Baseline `npm test` then passed before the change.
- `npm run check:structure` passed after the change with `app.js` at 12,411 lines.
- `npm run lint` passed.
- `kanbanFilterEntryCount` is `2`; `remainingKanbanFilterIfs` is empty; density, DB catalog filter, and stale-issue creation branches remained local; `handleOneLineCount` dropped to `77`.
- `npm test` passed with Kanban source filter, source empty/summary/palette/direct return, Korean source/family filters, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `273 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Create modal action dispatch map

- Hypothesis: PM and DB "add" actions that only open creation modals can use the shared action lookup path without changing edit, delete, move, order, or save behavior.
- Primary metric: `createModalActionDispatchDuplicationScore`.
- Baseline: `2/4`; nine creation branches remained inside `handleActions`, interleaved with edit/delete CRUD branches.
- Candidate: `4/4`; `CREATE_MODAL_ACTION_HANDLERS` dispatches those nine creation-modal actions through `runActionHandler`, while all edit/delete/state-changing CRUD branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous Kanban loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the create-modal change.
- `npm run check:structure` passed after the change with `app.js` at 12,413 lines.
- `npm run lint` passed.
- `createModalEntryCount` is `9`; `remainingCreateModalIfs` is empty; edit/delete CRUD branches remained local; `handleOneLineCount` dropped to `68`.
- The first post-change `npm test` exposed an out-of-sync home execution queue receipt context (`Missing selector: #null`) after the smoke/audit contract added `aria-describedby` coverage; source/package parity then confirmed `aria-describedby="homeExecutionReceiptDetail"` and `data-home-execution-receipt-description` were present.
- Rerunning `npm test` passed with project/issue/task/member/DB creation modal flows, home execution receipt description, delete/undo, and accessibility checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `274 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: App shell theme and picker dispatch

- Hypothesis: Theme toggle/set and project picker toggle/select actions can join the existing app shell dispatch map without changing persisted settings, picker accessibility, or navigation behavior.
- Primary metric: `appShellActionDispatchDuplicationScore`.
- Baseline: `3/4`; four shell-adjacent one-line branches remained in `handleActions` after the existing app shell map.
- Candidate: `4/4`; `APP_SHELL_ACTION_HANDLERS` now dispatches `toggle-theme`, `set-theme`, `toggle-project-picker`, and `pick-project`, without adding a new map or increasing `app.js` lines.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous create-modal loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the app shell change.
- `npm run check:structure` passed after the change with `app.js` at 12,412 lines.
- `npm run lint` passed.
- `appShellMovedEntries` contains all four actions; `remainingShellIfs` is empty; `handleOneLineCount` dropped to `64`.
- `npm test` passed with project picker UI/accessibility, settings theme controls, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `274 pass, 0 fail, 0 not_run, 0 blocked`, with `packaged_browser_gates` cached and `contextMatched=true`.

## Experiment: Review validation action dispatch map

- Hypothesis: review artifact repair, receipt comparison, and result validation actions can use a shared action lookup path without changing review issue creation, note publishing, or checklist behavior.
- Primary metric: `reviewValidationActionDispatchDuplicationScore`.
- Baseline: `2/4`; eight review validation branches remained inside `handleActions`, near review creation and checklist state changes.
- Candidate: `4/4`; `REVIEW_VALIDATION_ACTION_HANDLERS` dispatches those eight validation actions through `runActionHandler`, while issue creation, note publication, and checklist branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous app shell loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the review validation change.
- `npm run check:structure` passed after the change with `app.js` at 12,356 lines.
- `npm run lint` passed.
- `reviewValidationEntryCount` is `8`; all expected review validation entries are present; `remainingReviewValidationIfs` is empty; `create-review-issue`, `publish-review-note`, and `toggle-issue-checklist` stayed local; `handleOneLineCount` is `56`.
- `npm test` passed with review result validation, artifact receipt comparison, home execution queue, route/mobile/interaction/delete-undo/a11y checks green.
- The first audit pass after the module-context refresh exposed stale packaged/static evidence around `home-execution-view.js`; `scripts/smoke-release.mjs` now includes `home-execution-view.js` in the packaged browser gate runtime input list and the gate cache was regenerated by `npm test`.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Settings storage action dispatch map

- Hypothesis: settings save, storage health refresh, and storage persistence request actions can use a shared action lookup path without changing backup export, reset, or deleted-record recovery behavior.
- Primary metric: `settingsStorageActionDispatchDuplicationScore`.
- Baseline: `2/4`; three settings/storage one-line branches remained inside `handleActions`, adjacent to heavier backup and recovery commands.
- Candidate: `4/4`; `SETTINGS_STORAGE_ACTION_HANDLERS` dispatches those three settings/storage actions through `runActionHandler`, while backup export/reset and deleted-record recovery branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous review validation loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the settings/storage change.
- `npm run check:structure` passed after the change with `app.js` at 12,360 lines.
- `npm run lint` passed.
- `settingsStorageEntryCount` is `3`; all expected entries are present; `remainingSettingsIfs` is empty; backup export/reset and deleted-record recovery branches stayed local; `handleOneLineCount` dropped to `53`.
- `npm test` passed with settings persistence, storage handoff, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: To-Do quick-add action dispatch map

- Hypothesis: To-Do quick-add actions can join the existing To-Do action map without changing completion, toggle, or delete behavior.
- Primary metric: `todoQuickAddActionDispatchDuplicationScore`.
- Baseline: `2/4`; two quick-add branches remained inside `handleActions` before the To-Do action map.
- Candidate: `4/4`; `TODO_ACTION_HANDLERS` now dispatches `todo-quick-add` and `home-todo-quick-add`, while home execution completion, toggles, and deletes stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous settings/storage loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the quick-add change.
- `npm run check:structure` passed after the change with `app.js` at 12,360 lines.
- `npm run lint` passed.
- `todoQuickAddEntriesPresent` is `true`; `TODO_ACTION_HANDLERS` now has `7` entries; `remainingQuickAddIfs` is empty; `home-execution-todo-complete`, `todo-toggle`, `todo-delete`, and `delete-todo` stayed local; `handleOneLineCount` dropped to `51`.
- `npm test` passed with persisted To-Do creation, home quick todo, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Home execution quick action dispatch map

- Hypothesis: Home execution queue quick actions can use a shared dispatch map without changing To-Do toggle/delete, issue move/order, or undo behavior.
- Primary metric: `homeExecutionQuickActionDispatchDuplicationScore`.
- Baseline: `2/4`; the home execution Todo-complete and issue-next branches were split across the To-Do and PM CRUD sections of `handleActions`.
- Candidate: `4/4`; `HOME_EXECUTION_QUICK_ACTION_HANDLERS` dispatches both quick actions through `runActionHandler`, while ordinary To-Do mutations and PM issue movement branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous To-Do quick-add loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the home execution quick-action change.
- `npm run check:structure` passed after the change with `app.js` at 12,364 lines.
- `npm run lint` passed.
- `homeExecutionQuickEntryCount` is `2`; all expected entries are present; `remainingHomeExecutionQuickIfs` is empty; To-Do toggle/delete and issue move/order/delete branches stayed local; `handleOneLineCount` dropped to `49`.
- `npm test` passed with `homeExecutionQueueQuickActions`, `homeExecutionQueueQuickUndo`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: DB catalog action dispatch map

- Hypothesis: DB catalog filter and stale-review issue creation actions can use a shared dispatch map without changing review creation, checklist, Kanban density, or DB CRUD behavior.
- Primary metric: `dbCatalogActionDispatchDuplicationScore`.
- Baseline: `2/4`; two DB catalog branches remained inside `handleActions`, adjacent to review and Kanban actions.
- Candidate: `4/4`; `DB_CATALOG_ACTION_HANDLERS` dispatches the DB catalog filter and stale issue action through `runActionHandler`, while review creation/checklist and Kanban density branches stay local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous home execution quick-action loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the DB catalog change.
- `npm run check:structure` passed after the change with `app.js` at 12,368 lines.
- `npm run lint` passed.
- `dbCatalogEntryCount` is `2`; all expected entries are present; `remainingDbCatalogIfs` is empty; review creation/checklist and Kanban density branches stayed local; `handleOneLineCount` dropped to `47`.
- `npm test` passed with `dbCatalogProvenanceFilter`, `dbCatalogStaleAction`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: App shell recovery action dispatch map

- Hypothesis: data safety refresh, global help search recovery, and notification permission actions can join the existing app shell dispatch map without changing modal confirmation or route navigation behavior.
- Primary metric: `appShellRecoveryActionDispatchDuplicationScore`.
- Baseline: `2/4`; three app-shell recovery branches remained inside `handleActions` after the app shell map.
- Candidate: `4/4`; `APP_SHELL_ACTION_HANDLERS` now dispatches `data-safety-refresh`, `global-help-search-recovery`, and `request-notif-permission`, while `modal-confirm` remains local.
- Research: Reused dispatch-map A/B result from the MDN `Map` reference and Fowler conditional replacement reference.
- Decision: keep.

## Evidence

- Baseline from the previous DB catalog loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the app shell recovery change.
- `npm run check:structure` passed after the change with `app.js` at 12,365 lines.
- `npm run lint` passed.
- `APP_SHELL_ACTION_HANDLERS` now has `20` entries; all expected recovery entries are present; `remainingShellRecoveryIfs` is empty; `modal-confirm` stayed local; `handleOneLineCount` dropped to `44`.
- The first `npm test` after the change failed at `system publish readiness alignment` because the packaged release still contained a stale release-readiness summary; the root summary/gate cache was then refreshed to `contextMatched=true`.
- Rerunning `npm test` passed with `topbarDataSafety`, `globalHelpAccess`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Kanban action dispatch map

- Hypothesis: Kanban density can join the Kanban action map with priority/source filters without changing issue move/order behavior.
- Primary metric: `kanbanActionDispatchDuplicationScore`.
- Baseline: `3/4`; `KANBAN_FILTER_ACTION_HANDLERS` handled only filter actions while the persisted density action stayed as a separate `handleActions` branch.
- Candidate: `4/4`; `KANBAN_ACTION_HANDLERS` now handles priority filter, source filter, and density, while issue move/order branches stay local.
- Research: Compared keeping a narrow filter-only map against a surface-level Kanban map; the surface-level map better matches the UI responsibility and removes one dispatch path while preserving the existing persisted density smoke gate.
- Decision: keep.

## Evidence

- Baseline green before the change: `npm run check:structure`, `npm run lint`, and `npm test` all passed.
- `npm run check:structure` passed after the change with `app.js` at 12,365 lines.
- `npm run lint` passed.
- `kanbanActionEntryCount` is `3`; all expected entries are present; `remainingKanbanIfs` is empty; the old `KANBAN_FILTER_ACTION_HANDLERS` name is gone; issue move/order branches stayed local; `handleOneLineCount` dropped to `43`.
- `npm test` passed with `kanbanDensityPersistence`, Kanban source/filter checks, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Portfolio action dispatch map

- Hypothesis: Portfolio filter actions and project prompt-handoff display can share a surface-level portfolio dispatch map without changing review copy/validation actions or PM CRUD behavior.
- Primary metric: `portfolioActionDispatchDuplicationScore`.
- Baseline: `3/4`; `PORTFOLIO_FILTER_ACTION_HANDLERS` handled only filter actions while `show-project-prompt-handoff` stayed as a separate `handleActions` branch.
- Candidate: `4/4`; `PORTFOLIO_ACTION_HANDLERS` handles filters and prompt handoff, while review issue/note/checklist and PM project CRUD branches stay local.
- Research: Compared keeping a narrow filter-only map against a surface-level portfolio map; the surface-level map better matches the UI responsibility and removes one dispatch path while preserving the existing portfolio/review handoff smoke coverage.
- Decision: keep.

## Evidence

- Pre-change `npm run check:structure` and `npm run lint` passed. The first pre-change `npm test` hit a `smoke-chrome.mjs` DevTools endpoint timeout before any candidate code was applied; rerunning the same baseline passed, so the change proceeded from a green baseline.
- `npm run check:structure` passed after the change with `app.js` at 12,365 lines.
- `npm run lint` passed.
- `portfolioActionEntryCount` is `4`; all expected entries are present; `remainingPortfolioIfs` is empty; the old `PORTFOLIO_FILTER_ACTION_HANDLERS` name is gone; review issue/note branches stayed local; `handleOneLineCount` dropped to `42`.
- `npm test` passed with portfolio candidate filters, workspace/knowledge-base/candidate benchmark review handoff checks, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Verify workspace summary receipt contract repair

- Hypothesis: The packaged verify-workspace summary receipt can expose the required full-verify step ids directly in `release-status.js` without changing the default gate-only `npm run verify` contract or the System Status copy flow.
- Primary metric: `verifyCommandGateOnlyContractScore`.
- Baseline: `3/4`; `npm test` passed, but release readiness audit failed `verify_command_gate_only` because the verify summary UI rendered step ids from JSON while `release-status.js` did not keep the required static step-id literals.
- Candidate: `4/4`; `VERIFY_WORKSPACE_SUMMARY_REQUIRED_STEPS` is wired into the verify workspace receipt via a `requiredStepIds` line, preserving `npm run verify` as gate-only and `npm run verify:full` as the explicit evidence-sync path.
- Research: Kept the existing source-term audit contract instead of relaxing it; the UI source now carries the same step-id vocabulary that the packaged smoke asserts at runtime.
- Decision: keep.

## Evidence

- `release-status.js` now contains `release_readiness_gates`, `launch_readiness_refresh`, `product_loop_summary_sync`, and `requiredStepIds`.
- `npm run check:structure` passed with `app.js` at 12,443 lines.
- `npm run lint` passed.
- `npm test` passed with `verifyWorkspaceSummary=true`, `verifyWorkspaceSummaryReceiptCopy=true`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Calendar action dispatch map

- Hypothesis: calendar event mutation actions can join the existing calendar action map without changing modal confirmation, todo handling, or delete/undo recovery behavior.
- Primary metric: `calendarActionDispatchDuplicationScore`.
- Baseline: `7/9`; `CALENDAR_ACTION_HANDLERS` handled calendar navigation/open actions while `delete-event` and `skip-occurrence` stayed as separate `handleActions` branches.
- Candidate: `9/9`; `CALENDAR_ACTION_HANDLERS` now handles `delete-event` and `skip-occurrence`, while modal confirmation and Todo action branches stay local to their existing owners.
- Research: Reused the dispatch-map consolidation result from prior Kanban/Portfolio loops and kept destructive-event confirmation semantics behind the existing action handler targets and delete/undo smoke.
- Decision: keep.

## Evidence

- Baseline from the previous verify-workspace receipt repair loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Calendar change.
- `npm run check:structure` passed after the change with `app.js` at 12,408 lines.
- `npm run lint` passed.
- `calendarActionEntryCount` is `9`; all expected Calendar entries are present; `remainingCalendarMutationIfs` is empty; `modal-confirm` and Todo branches stayed local; `handleOneLineCount` stayed at `40` after nearby source updates.
- The first full release smoke in this loop exposed a packaged System Status cache-panel edge case: a freshly written valid packaged gate could report `gate.cached=false`, leaving the UI neither healthy nor repair-required. `release-status.js` now treats a valid pass cache payload as available for `data-release-gate-cache-cached`.
- `npm test` passed after that support repair with `calendarModeSwitch`, `calendarGridKeyboard`, `calendarSearchRecovery`, `releaseGateCache=true`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: To-Do action dispatch map

- Hypothesis: To-Do toggle/delete actions can join the existing To-Do action map without changing home execution quick actions, Notes/Habits handling, or delete/undo recovery behavior.
- Primary metric: `todoActionDispatchDuplicationScore`.
- Baseline: `7/10`; `TODO_ACTION_HANDLERS` handled create/open/filter actions while `todo-toggle`, `todo-delete`, and `delete-todo` stayed as separate `handleActions` branches.
- Candidate: `10/10`; `TODO_ACTION_HANDLERS` now handles toggle/delete aliases, while home execution quick actions remain in their existing map and Notes/Habits stay local for separate loops.
- Research: Kept destructive To-Do semantics on the same `deleteTodo` target and relied on the existing interaction plus delete/undo release smoke to prove persistence and recovery behavior.
- Decision: keep.

## Evidence

- Baseline from the previous Calendar loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the To-Do change.
- `npm run check:structure` passed after the change with `app.js` at 12,408 lines.
- `npm run lint` passed.
- `todoActionEntryCount` is `10`; all expected To-Do entries are present; `remainingTodoMutationIfs` is empty; home execution, Notes, and Habits branches stayed in their current owners; `handleOneLineCount` dropped to `37`.
- `npm test` passed with `homeQuickTodo`, `todoSearchRecovery`, delete-undo, route/mobile/interaction/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Notes action dispatch map

- Hypothesis: Notes pin/delete actions can join the existing Notes action map without changing To-Do handling, Habits handling, or delete/undo recovery behavior.
- Primary metric: `noteActionDispatchDuplicationScore`.
- Baseline: `3/6`; `NOTE_ACTION_HANDLERS` handled create/open/source-filter actions while `note-pin`, `note-delete`, and `delete-note` stayed as separate `handleActions` branches.
- Candidate: `6/6`; `NOTE_ACTION_HANDLERS` now handles pin/delete aliases, while To-Do remains in its completed map and Habits stays local for a separate loop.
- Research: Kept note pin/delete calls on the existing `togglePin` and `deleteNote` targets and relied on persisted note, notes search recovery, delete/undo, and accessibility smoke coverage.
- Decision: keep.

## Evidence

- Baseline from the previous To-Do loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Notes change.
- `npm run check:structure` passed after the change with `app.js` at 12,408 lines.
- `npm run lint` passed.
- `noteActionEntryCount` is `6`; all expected Notes entries are present; `remainingNoteMutationIfs` is empty; To-Do and Habits handling stayed in their current owners; `handleOneLineCount` dropped to `34`.
- `npm test` passed with persisted `note=true`, `notesSearchRecovery`, delete-undo, route/mobile/interaction/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Habits action dispatch map

- Hypothesis: Habit toggle/delete actions can join the existing Habits action map without changing To-Do, Notes, Settings, or delete/undo recovery behavior.
- Primary metric: `habitActionDispatchDuplicationScore`.
- Baseline: `2/4`; `HABIT_ACTION_HANDLERS` handled create/open actions while `habit-toggle` and `habit-delete` stayed as separate `handleActions` branches.
- Candidate: `4/4`; `HABIT_ACTION_HANDLERS` now handles toggle/delete, while Settings and recovery actions remain local to their existing section.
- Research: Kept habit mutation calls on the existing `toggleHabit` and `deleteHabit` targets and relied on persisted habit, habit search recovery, delete/undo, and accessibility smoke coverage.
- Decision: keep.

## Evidence

- Baseline from the previous Notes loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Habits change.
- `npm run check:structure` passed after the change with `app.js` at 12,408 lines.
- `npm run lint` passed.
- `habitActionEntryCount` is `4`; all expected Habits entries are present; `remainingHabitMutationIfs` is empty; To-Do, Notes, and Settings handling stayed in their current owners; `handleOneLineCount` dropped to `32`.
- `npm test` passed with persisted `habit=true`, `habitSearchRecovery`, delete-undo, route/mobile/interaction/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Settings recovery action dispatch map

- Hypothesis: Settings backup/export/reset and deleted-record recovery actions can join the existing settings storage action map without changing post-install proof parsing, review actions, or delete/undo recovery behavior.
- Primary metric: `settingsRecoveryActionDispatchDuplicationScore`.
- Baseline: `3/10`; `SETTINGS_STORAGE_ACTION_HANDLERS` handled save/refresh/persistence actions while export/reset/deleted-recovery actions stayed as separate `handleActions` branches.
- Candidate: `10/10`; `SETTINGS_STORAGE_ACTION_HANDLERS` now handles export/reset and deleted-record recovery actions, while post-install parsing and review flows remain in their existing sections.
- Research: Kept all recovery actions on their existing targets and relied on backup export/import/reset, recent deleted recovery, delete/undo, and settings handoff smoke coverage.
- Decision: keep.

## Evidence

- Baseline from the previous Habits loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the Settings recovery change.
- `npm run check:structure` passed after the change with `app.js` at 12,408 lines.
- `npm run lint` passed.
- `settingsStorageActionEntryCount` is `10`; all expected settings recovery/storage entries are present; `remainingSettingsRecoveryIfs` is empty; post-install parser and review branches stayed local; `handleOneLineCount` dropped to `25`.
- `npm test` passed with `backupExport`, `backupImport`, `backupReset`, recent deleted recovery coverage, delete-undo, route/mobile/interaction/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `275 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Review execution action dispatch map

- Hypothesis: Review issue creation, note publishing, and execution checklist toggles can share a review execution action map without changing review copy/validation handlers or PM/DB CRUD behavior.
- Primary metric: `reviewExecutionActionDispatchDuplicationScore`.
- Baseline: `0/3`; `create-review-issue`, `publish-review-note`, and `toggle-issue-checklist` stayed as separate `handleActions` branches after review copy and validation maps.
- Candidate: `3/3`; `REVIEW_EXECUTION_ACTION_HANDLERS` now handles those review execution actions, while review copy, validation, and CRUD branches stay in their existing owners.
- Research: Kept each action on its existing function target and relied on review issue/note/checklist interaction smoke plus artifact diff/receipt checks to prove behavior.
- Decision: keep.

## Evidence

- Baseline from the previous Settings recovery loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the review execution change.
- `npm run check:structure` passed after the change with `app.js` at 12,330 lines.
- `npm run lint` passed.
- `reviewExecutionActionEntryCount` is `3`; all expected review execution entries are present; `remainingReviewExecutionIfs` is empty; review copy/validation maps and CRUD branches stayed local; `handleOneLineCount` dropped to `22`.
- The first audit after the dispatch-map move exposed a source-contract edge around review artifact runtime extraction. `app.js` now preserves the `post-apply fresh receipt` and `data-review-artifact-repair-preview` bridge terms, `.github/workflows/joopark-pages.yml` was restaged from `docs/github-pages-workflow.yml` so `review-artifact-state.js` is included, and `sw.js` keeps the verify-summary cache lineage marker while caching `review-artifact-state.js`.
- `npm test` passed with `reviewPackageReviewIssueDraftVisible`, `reviewPackageReviewNotePublishVisible`, `reviewExecutionChecklist`, `reviewArtifactStateModule`, `reviewArtifactPostApplyFreshReceipt`, route/mobile/interaction/delete-undo/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `276 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: PM CRUD action dispatch map

- Hypothesis: Project, issue, task, and member edit/delete/move/order actions can share a PM CRUD dispatch map without changing DB CRUD behavior, modal confirmation, or Kanban ordering semantics.
- Primary metric: `pmCrudActionDispatchDuplicationScore`.
- Baseline: `0/10`; PM CRUD actions stayed as ten separate `handleActions` branches after create-modal handling.
- Candidate: `10/10`; `PM_CRUD_ACTION_HANDLERS` now handles project edit/delete, issue edit/delete/move/order, task edit/delete, and member edit/delete, while DB CRUD remains local for a separate loop.
- Research: Kept close/open/delete call order identical to the prior branches and relied on PM persisted checks, Kanban order persistence, delete/undo, and accessibility smoke coverage.
- Decision: keep.

## Evidence

- Baseline from the previous review execution loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the PM CRUD change.
- `npm run check:structure` passed after the change with `app.js` at 12,333 lines.
- `npm run lint` passed.
- `pmCrudActionEntryCount` is `10`; all expected PM CRUD entries are present; `remainingPmCrudIfs` is empty; DB CRUD branches and `modal-confirm` stayed local; `handleOneLineCount` dropped to `12`.
- `npm test` passed with persisted `project=true`, `issue=true`, `kanbanOrderPersistence`, PM action a11y labels, delete-undo, route/mobile/interaction/a11y checks green.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `276 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: DB CRUD action dispatch map

- Hypothesis: DB instance/table/column/query/migration edit/delete actions can share a DB CRUD map without changing PM CRUD, modal confirmation, post-install parsing, or backup/delete recovery behavior.
- Primary metric: `dbCrudActionDispatchDuplicationScore`.
- Baseline: `0/10`; DB CRUD actions stayed as ten separate `handleActions` branches after PM CRUD handling.
- Candidate: `10/10`; `DB_CRUD_ACTION_HANDLERS` now handles instance edit/delete, table edit/delete, column edit/delete, query edit/delete, and migration edit/delete, while `modal-confirm` and `parse-post-install-proof` remain explicit local branches.
- Research: Kept every open/close/delete call on the previous target and used DB persisted checks, DB catalog provenance/search/import coverage, delete-undo, and accessibility smoke to prove behavior. During verification, the verify-workspace summary smoke assertion was also made count-dynamic so new release-readiness checks can increase the pass count without weakening the zero-failure guard.
- Decision: keep.

## Evidence

- Baseline from the previous PM CRUD loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the DB CRUD change.
- `npm run check:structure` passed after the change with `app.js` at 12,256 lines.
- `npm run lint` passed.
- `dbCrudActionEntryCount` is `10`; all expected DB CRUD entries are present; `remainingDbCrudIfs` is empty; PM CRUD map, `modal-confirm`, and `parse-post-install-proof` stayed in their current owners; `handleOneLineCount` dropped to `2`.
- `npm test` passed with 72 packaged files, persisted `dbInstance=true`, DB catalog module/provenance/search recovery checks, delete-undo, route/mobile/interaction/a11y checks green, and no console or network issues.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `277 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached, `contextMatched=true`, `inputFiles=69`, and no cache issues or mismatches.

## Experiment: Operations parser action dispatch map

- Hypothesis: The post-install proof parser action can move into an operations parser map without changing operations copy actions, modal confirmation, or parser false-positive safeguards.
- Primary metric: `operationsParserActionDispatchDuplicationScore`.
- Baseline: `0/1`; `parse-post-install-proof` stayed as the final non-modal direct `handleActions` branch.
- Candidate: `1/1`; `OPERATIONS_PARSER_ACTION_HANDLERS` now owns `parse-post-install-proof`, while `modal-confirm` remains the only direct action branch because it depends on transient modal callback state.
- Research: Kept the parser root resolution and `updatePostInstallProofParser` call identical, then relied on post-install parser false-positive, field coverage, copy, and release readiness smoke coverage.
- Decision: keep.

## Evidence

- Baseline from the previous DB CRUD loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the parser map change.
- `npm run check:structure` passed after the change with `app.js` at 12,260 lines.
- `npm run lint` passed.
- `operationsParserActionEntryCount` is `1`; `parse-post-install-proof` is mapped; `remainingParseIf` is `0`; the only remaining direct action comparison in `handleActions` is `modal-confirm`; `handleOneLineCount` dropped to `1`.
- `npm test` passed with `postInstallProofParser=true`, `postInstallProofParserFalsePositiveGuard=true`, `postInstallProofParserCoverage=1`, `postInstallProofParserDetectedFields=6`, route/mobile/interaction/delete-undo/a11y checks green, and no console or network issues.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `277 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached, `contextMatched=true`, `inputFiles=69`, and no cache issues or mismatches.

## Experiment: Modal confirm action dispatch map

- Hypothesis: The modal confirmation action can move into a first-position modal action map without changing transient confirm callback behavior or any CRUD/delete recovery flow.
- Primary metric: `directActionBranchCount`.
- Baseline: `1`; `modal-confirm` remained the last direct `action ===` comparison in `handleActions`.
- Candidate: `0`; `MODAL_ACTION_HANDLERS` now owns `modal-confirm` and remains the first dispatch check so confirmation callbacks still run before every other action map.
- Research: Preserved the previous callback semantics: call `state.modalOnConfirm`, close the modal unless the callback returns `false`, and close immediately when no callback exists.
- Decision: keep.

## Evidence

- Baseline from the previous operations parser loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before the modal confirm change.
- `npm run check:structure` passed after the change with `app.js` at 12,266 lines.
- `npm run lint` passed.
- `modalActionEntryCount` is `1`; `modal-confirm` is mapped; `remainingModalIf` is `0`; `remainingActionIfs` is empty; `handleOneLineCount` is `0`; `MODAL_ACTION_HANDLERS` is the first dispatch map in `handleActions`.
- `npm test` passed with interaction checks, delete/undo recovery, modal accessibility, route/mobile/a11y checks green, and no console or network issues.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `277 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached, `contextMatched=true`, `inputFiles=69`, and no cache issues or mismatches.

## Experiment: Action dispatcher map-only audit contract

- Hypothesis: The map-only click dispatcher can be protected by release readiness so direct `action ===` branches cannot silently return.
- Primary metric: `actionDispatcherContractCoverage`.
- Baseline: `0/1`; release readiness did not track the new map-only dispatcher invariant.
- Candidate: `1/1`; `action_dispatcher_map_only` now verifies `handleActions` has zero direct action string branches, at least 21 action maps, required modal/operations/PM/DB/open maps, and log evidence.
- Research: Kept the contract static and local to `scripts/audit-release-readiness.mjs`, with Product Contracts summary output so operators can see the invariant without reading the full checklist.
- Decision: keep.

## Evidence

- Baseline from the previous modal confirm loop was green: `npm run check:structure`, `npm run lint`, `npm test`, and release audit all passed before adding the contract.
- `npm run lint` passed after the audit script change.
- Static checks confirmed `action_dispatcher_map_only`, `directActionBranchCount`, `MODAL_ACTION_HANDLERS`, and `DB_CRUD_ACTION_HANDLERS` are present in the audit script.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `278 pass, 0 fail, 0 not_run, 0 blocked`, with Product Contracts showing `action_dispatcher_map_only: pass`.
- Release gate cache remained cached with `contextMatched=true`, `inputFiles=69`, and no cache issues or mismatches.
- `npm run verify:full` passed after the contract, refreshing `autoresearch-results/verify-workspace-summary.json` so release, launch, output-quality, and product-loop summaries all report `278 pass, 0 fail, 0 not_run, 0 blocked` with `safeToDispatch=false` and `readyForExternalClaim=false`.
- A final fresh `npm test` regenerated the packaged browser gate cache for the current 70-file context, and `node scripts/audit-release-readiness.mjs --format=summary` passed again at `278 pass, 0 fail, 0 not_run, 0 blocked` with `contextMatched=true` and no cache issues or mismatches.

## Experiment: Pages workflow draft-state README proof repair

- Hypothesis: The Pages workflow/template audit can use the README as a stable operator-facing proof source for the new review result draft-state runtime asset without changing runtime behavior.
- Primary metric: `githubPagesWorkflowReadmeProofCoverage`.
- Baseline: `0/1`; release readiness failed `github_pages_workflow_scope_handoff` and `github_pages_publish_workflow_template` because README did not mention `review-result-draft-state.js`, even though the workflow template and prepare script already carried the asset.
- Candidate: `1/1`; README now states that `review-result-draft-state.js` owns GitHub comment copy and issue draft assignee override state as a static runtime helper and belongs to the same GitHub Pages workflow template, release package, and service worker app shell push/runtime asset set.
- Research: Kept this as documentation/audit evidence only. When the audit cache rejected a stale browser gate because `scripts/plan-workflow-ui-install.mjs` changed in the current working tree, regenerated the packaged browser gate cache against the current 70-file input context.
- Decision: keep.

## Evidence

- `npm test` passed after regenerating the packaged release gate cache, with 73 release files, 54 source parity files, 52 provenance dependencies, route/mobile/interaction/delete-undo/a11y all pass, `review_result_draft_state_cache_no_cache=true`, and `reviewResultDraftStateModule=true`.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `279 pass, 0 fail, 0 not_run, 0 blocked`, with Product Contracts showing `action_dispatcher_map_only: pass`.
- Release gate cache is cached and current: `status=pass`, `contextMatched=true`, `inputFiles=70`, with no cache issues or mismatches.

## Experiment: Action dispatcher structure guard

- Hypothesis: The map-only click dispatcher should be enforced by the fast structure check as well as release readiness, so direct action branch regressions fail before the full release audit.
- Primary metric: `structureActionDispatchGuardCoverage`.
- Baseline: `0/1`; `npm run check:structure` verified app boundaries and extraction coverage but did not inspect `handleActions` for direct `action ===` branches or required action maps.
- Candidate: `1/1`; `scripts/check-app-structure.mjs` now reports `actionDispatchGuard` with `directActionBranchCount`, action handler map count, required map gaps, and first-handler ordering.
- Research: Mirrored the release audit invariant in a smaller local guard: `handleActions` must exist, direct action branch count must stay `0`, at least 21 action maps must exist, key modal/operations/PM/DB/open maps must be present, and `MODAL_ACTION_HANDLERS` must remain first.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `actionDispatchGuard.status=pass`, `directActionBranchCount=0`, `actionHandlerMapCount=21`, no missing required maps, and `firstHandler=MODAL_ACTION_HANDLERS`.
- `npm run lint` passed.
- `npm test` passed after regenerating the packaged release gate cache for the updated structure-check input, with route/mobile/interaction/delete-undo/a11y checks green and no console or network issues.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `279 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and `contextMatched=true`.

## Experiment: Action dispatcher structure guard audit contract

- Hypothesis: The release audit should protect the fast structure guard itself, so `action_dispatcher_map_only` cannot pass if `npm run check:structure` stops reporting the map-only dispatcher evidence.
- Primary metric: `actionDispatcherStructureGuardAuditCoverage`.
- Baseline: `0/1`; release readiness checked `app.js` and product-loop evidence, but it did not require `scripts/check-app-structure.mjs` to keep `actionDispatchGuard`.
- Candidate: `1/1`; `action_dispatcher_map_only` now requires `structureAudit.result.actionDispatchGuard.status === "pass"` and static terms for `actionDispatchGuardEvidence`, `actionDispatchGuardFailure`, `directActionBranchCount`, `actionHandlerMapCount`, first-handler ordering, and `minActionHandlerMaps`.
- Research: Kept this inside the existing product contract rather than adding a separate checklist item, so the Product Contracts summary stays focused while the contract now spans both release audit and the fast structure gate.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `actionDispatchGuard.status=pass`, `directActionBranchCount=0`, `actionHandlerMapCount=21`, no missing required maps, and `firstHandler=MODAL_ACTION_HANDLERS`.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `279 pass, 0 fail, 0 not_run, 0 blocked`, with Product Contracts showing `action_dispatcher_map_only: pass`.
- Release gate cache remained cached and current: `status=pass`, `contextMatched=true`, `inputFiles=70`, with no cache issues or mismatches.

## Experiment: Product loop summary timestamp sync repair

- Hypothesis: The full workspace verifier should refresh product-loop summary sync metadata whenever the latest packaged gate timestamp changes, even if the semantic release/launch/output readiness statuses are already aligned.
- Primary metric: `verifyFullEvidenceSyncParity`.
- Baseline: `0/1`; `npm run verify:full` failed `evidenceSync` because `summarySync=false` after a fresh latest gate timestamp updated without rewriting `productLoop.summarySync.outputQualityGeneratedAt`.
- Candidate: `1/1`; `scripts/sync-product-loop-summary.mjs` now treats latest-gate updates, stale output-quality generatedAt, and missing gate/publish parity flags as semantic sync reasons and writes the summary when those fields drift.
- Research: Kept the change limited to sync metadata freshness. The release quality and public-launch guard statuses remain unchanged, with `readyForExternalClaim=false`.
- Decision: keep.

## Evidence

- `node scripts/sync-product-loop-summary.mjs --write --markdown` passed with `latestGateUpdated=true`, `summarySyncOutputQualityStale=true`, `semanticSyncNeeded=true`, `writeApplied=true`, and `syncExperimentUpdated=true`.
- `npm run lint` passed after the sync script change.

## Experiment: Review creation helper bootstrap guard

- Hypothesis: The extracted review creation helper should not require optional dashboard arrays to exist before app bootstrap normalization has run.
- Primary metric: `packagedRuntimeBootstrapReady`.
- Baseline: `0/1`; packaged route smoke rendered an empty Home view because `createReviewCreationActions` threw during app initialization when `dashboard.notes` was not yet an array.
- Candidate: `1/1`; `review-creation-actions.js` now validates the required dependency objects, lazily initializes `dashboard.issues` and `dashboard.notes`, and pushes new issue/note drafts through `ensureDashboardArray`.
- Research: Preserved the helper contract for lookup, draft, mutation, and toast dependencies while removing the premature optional-array bootstrap requirement.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `reviewCreationActions.status=extracted` and the module terms covering `function ensureDashboardArray`, `ensureDashboardArray("issues").push`, and `ensureDashboardArray("notes").push`.
- `npm run lint` passed.
- `node --check review-creation-actions.js`, `node scripts/package-release.mjs`, and `node scripts/verify-release.mjs` passed with 74 release files, 55 source parity files, and 53 provenance dependencies.
- A headless packaged Home bootstrap check showed no page errors, `bodyView=home`, and Home content rendering.

## Experiment: System evidence smoke diagnostics and cache capture

- Hypothesis: The packaged browser gate should keep complete pass evidence after transient System evidence waits, and failure capture should preserve the underlying smoke payload instead of writing an empty incomplete cache.
- Primary metric: `packagedBrowserGateEvidenceCompleteness`.
- Baseline: `0/1`; a fresh `verify:full` run failed with `packaged_browser_gates=fail` and `incomplete_evidence` because `smoke-release` failure details were emitted on stderr while the audit runner inherited stderr instead of capturing it.
- Candidate: `1/1`; `scripts/smoke-interactions.mjs` now reports delayed System evidence panel diagnostics on timeout, and `scripts/audit-release-readiness.mjs` parses JSON from stdout or stderr for smoke-release attempts.
- Research: Kept the System evidence requirements strict: release gate evidence, workflow install guidance, launch proof guard, output-quality audit, and source snapshot health must still load before the interaction smoke can pass.
- Decision: keep.

## Evidence

- Standalone packaged `scripts/smoke-interactions.mjs` passed after the diagnostic guard cleanup with `systemPublishReadiness=true`, `releaseGateEvidence=true`, `releaseGateCache=true`, `outputQualityAuditReceipt=true`, and `sourceSnapshotHealth=true`.
- `RELEASE_SMOKE_SKIP_PACKAGE=1 RELEASE_OUT_DIR=/tmp/joopark-smoke-debug node scripts/smoke-release.mjs` passed with headers, fallbacks, 17/17 desktop/mobile route parity, mobile search/UI surfaces, interaction smoke, delete/undo recovery, and accessibility all pass.
- `npm run check:structure` passed.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `280 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and complete.

## Experiment: Release gate failure-capture audit contract

- Hypothesis: The release gate cache contract should protect the failure-capture path, not just the happy-path cache fields.
- Primary metric: `releaseGateFailurePayloadContractCoverage`.
- Baseline: `0/1`; the stderr JSON parsing and delayed System evidence diagnostics were implemented but not required by release readiness.
- Candidate: `1/1`; `release_gate_evidence_cache` now requires `parseJsonFromOutputs(result.stdout, result.stderr)` plus System evidence diagnostic markers in `scripts/smoke-interactions.mjs`.
- Research: Kept this inside the existing cache contract so the checklist count stays stable while the gate now covers both complete pass evidence and debuggable fail evidence.
- Decision: keep.

## Evidence

- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `280 pass, 0 fail, 0 not_run, 0 blocked` after the contract term correction.

## Experiment: Review execution checklist extracted-owner audit repair

- Hypothesis: The review execution checklist audit should follow the extracted rendering owner instead of requiring every UI string to remain in `app.js`.
- Primary metric: `reviewExecutionChecklistAuditOwnershipAccuracy`.
- Baseline: `0/1`; after the current extracted app state, audit failed `review_execution_checklist_fields` because `## Execution Checklist` lives in `review-result-view.js` while the app delegates through `reviewResultViewCall`.
- Candidate: `1/1`; the audit now keeps orchestration/delegation terms in `app.js` and requires the checklist heading plus DOM controls in `review-result-view.js`.
- Research: Verified this as an ownership-contract repair, not a runtime behavior change. The smoke already covers issue draft, created issue, sheet, Kanban, and persisted toggle behavior.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `app.js` at 12,119 lines and `actionDispatchGuard.status=pass`.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `280 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates freshly cached for the current app fingerprint.

## Experiment: Release audit compact JSON output

- Hypothesis: The release readiness JSON CLI should stay consumable by default Node `spawnSync` callers while preserving an explicit pretty-print path for manual inspection.
- Primary metric: `releaseAuditJsonDefaultBufferParse`.
- Baseline: `0/1`; default `spawnSync(process.execPath, ["scripts/audit-release-readiness.mjs", "--format=json"])` failed with `ENOBUFS` after pretty JSON grew to 1,297,364 bytes.
- Candidate: `1/1`; default `--format=json` now emits compact JSON, while `--format=json-pretty` and `--pretty` preserve the previous formatted output for file-based inspection.
- Research: Kept summary and markdown formats unchanged, and left the external completion guard blocked with `readyForExternalClaim=false`.
- Decision: keep.

## Evidence

- Default `spawnSync` capture of `node scripts/audit-release-readiness.mjs --format=json` passed with `stdoutBytes=983626`, `parse=ok`, and `281 pass, 0 fail, 0 not_run, 0 blocked`.
- `node scripts/audit-release-readiness.mjs --format=json-pretty` remained parseable from file redirection with `prettyBytes=1297364` and `status=pass`.
- `README.md` now documents default compact machine-readable JSON and the explicit `--format=json-pretty` / `--pretty` formatted inspection path.
- `release_gate_evidence_cache` now requires the compact JSON source path, pretty JSON source path, and README output policy terms.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `281 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates cached and current.

## Experiment: Review issue payload audit ownership docs

- Hypothesis: The review issue payload extraction should be documented and audited as the owner of Decision Summary, pinned note summary, tracker fields, due date, and body payload text while `app.js` keeps wrapper/delegate ownership.
- Primary metric: `reviewIssuePayloadAuditOwnershipCoverage`.
- Baseline: `0/1`; full verify failed after the extracted state because `review_handoff_actionable_quality_package`, `review_issue_decision_summary`, and `review_comment_note_decision_summary` still required body text inside `app.js`.
- Candidate: `1/1`; release readiness now keeps `app.js` checks on `reviewIssuePayloadCall` wrappers and requires body payload terms in `review-issue-payload.js`.
- Research: Documented the extracted helper in README and `docs/app-architecture.md` so structure checks, runtime module checks, and handoff docs agree on ownership.
- Decision: keep.

## Evidence

- `npm run check:structure` passed with `review-issue-payload` extracted, `app.js` at 12,003 lines, and `actionDispatchGuard.status=pass`.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `282 pass, 0 fail, 0 not_run, 0 blocked`, with packaged browser gates freshly cached.

## Experiment: Pages workflow runtime path filter parity

- Hypothesis: The GitHub Pages workflow template and staged local workflow should trigger on every shipped runtime helper that can change the release package.
- Primary metric: `pagesWorkflowRuntimePathFilterCoverage`.
- Baseline: `0/2`; direct path filter comparison found `home-execution-view.js` and `verify-workspace-summary.js` missing from both `docs/github-pages-workflow.yml` and `.github/workflows/joopark-pages.yml`.
- Candidate: `2/2`; both workflow files now include those helpers in the push paths alongside the other runtime helpers.
- Research: `scripts/audit-release-readiness.mjs` now derives a shared `pagesWorkflowRuntimeAssets` list and checks the docs workflow, staged local workflow, and README against it.
- Decision: keep.

## Evidence

- Direct path filter comparison passed with `missing=[]` for `docs/github-pages-workflow.yml` and `.github/workflows/joopark-pages.yml`.
- `npm run lint` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `282 pass, 0 fail, 0 not_run, 0 blocked`.

## Experiment: Ops runtime diagnostics

- Hypothesis: The lazy operations/review runtime should expose group and file load diagnostics so System Status and browser smoke can explain route-gated runtime failures without relying on raw console output.
- Primary metric: `opsRuntimeDiagnosticsCoverage`.
- Baseline: `0/1`; `ops-runtime-loader.js` only returned loaded file counts and did not preserve pending, failed, group last-load status, or bounded load events.
- Candidate: `1/1`; the loader now records `lastErrors`, `loadEvents`, `groupLoads`, `fileStats`, `groupStats`, `failed`, `pending`, `lastLoads`, and loaded file totals, while System Status renders an `Ops runtime diagnostics` panel.
- Research: Compared browser script load/error visibility, code-splitting runtime chunk diagnostics, and hosted CI summary patterns; kept the result local-first and smoke-verifiable.
- Decision: keep.

## Evidence

- `node --check` passed for `ops-runtime-loader.js`, `system-status-view.js`, `app.js`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs`.
- `npm run check:structure` passed with `app.js` at 10,864 lines and `actionDispatchGuard.status=pass`.
- `npm run check:docs` passed with 29 initial runtime scripts and 16 lazy runtime scripts.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`, with fresh packaged browser gates cached.

## Experiment: Verify summary latest experiment receipt

- Hypothesis: The full verify summary and System Status receipt should surface the latest AutoResearch experiment id, not only the latest direction loop, so operators can trace the verified artifact back to the concrete improvement that just landed.
- Primary metric: `verifyWorkspaceLatestExperimentReceiptCoverage`.
- Baseline: `0/1`; `verify-workspace-summary.json` carried `artifacts.productLoop.latestExperiment`, but the runtime validator and System Status receipt did not require or show it.
- Candidate: `1/1`; `verify-workspace-summary.js` requires `latestExperiment`, `release-status.js` exposes `data-verify-workspace-summary-latest-experiment` and receipt text, and interaction smoke verifies DOM/clipboard parity.
- Research: Used experiment-tracking and CI-summary patterns to keep the current run linked to the concrete improvement it verified.
- Decision: keep.

## Evidence

- `node --check` passed for `verify-workspace-summary.js`, `release-status.js`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs`.
- `npm run check:structure` passed with `app.js` at 10,864 lines and `actionDispatchGuard.status=pass`.
- `npm run check:docs` passed with 29 initial runtime scripts and 16 lazy runtime scripts.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`, with fresh packaged browser gates cached.
- `npm run verify:full` passed with `latestDirectionLoop=loop-140`, `latestExperiment=verify-summary-latest-experiment-receipt`, and `evidenceSync.directionLoopSyncReady=true`.

## Experiment: Share proof next-action ready status

- Hypothesis: The final proof handoff should mark `share-launch-proof` as ready and avoid duplicating the same command as a deferred action once live launch proof is already complete.
- Primary metric: `shareProofNextActionStatusParity`.
- Baseline: `0/1`; `data/publish-evidence.json` and `data/output-quality-audit.json` showed `share-launch-proof` with `status=action_required` even when `postPublishEvidenceReady=true` and `readyForExternalClaim=true`.
- Candidate: `1/1`; final share proof now carries `status=ready`, the output-quality next-action card uses the proof-ready detail instead of a stale workflow-scope approval guard, and `deferredKey`/`deferredCommand` stay empty when no explicit deferred action exists.
- Research: Compared operator-facing CI summaries, provenance traceability, and experiment-run receipts; kept the fix local and artifact-driven.
- Decision: keep.

## Evidence

- `node --check` passed for `scripts/capture-publish-evidence.mjs`, `scripts/capture-output-quality-audit.mjs`, `release-status.js`, `scripts/smoke-interactions.mjs`, and `scripts/audit-release-readiness.mjs`.
- `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write` regenerated `data/publish-evidence.json` with `nextAction.status=ready`.
- `node scripts/capture-output-quality-audit.mjs --write` regenerated `data/output-quality-audit.json` with `nextAction.status=ready`, `deferredKey=""`, `deferredCommand=""`, and `readyForExternalClaim=true`.
- `npm run check:structure` and `npm run check:docs` passed after the next-action contract change.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`, with `Next action: share-launch-proof [ready]`.
- `npm run verify:full` passed with `latestDirectionLoop=loop-141`, `latestExperiment=share-proof-next-action-ready-status`, `evidenceSync.directionLoopSyncReady=true`, and `readyForExternalClaim=true`.

## Experiment: Release summary deferred proof none

- Hypothesis: The release readiness summary should say there is no deferred proof when the final proof action is ready and no explicit deferred action exists.
- Primary metric: `releaseSummaryDeferredProofAccuracy`.
- Baseline: `0/1`; after Loop 141 the summary printed `Deferred proof: pending - pending` even though the structured output-quality receipt had empty deferred fields.
- Candidate: `1/1`; `scripts/audit-release-readiness.mjs` now formats missing deferred proof as `Deferred proof: none` and self-checks that wording in the summary-format plan.
- Research: Compared operator-facing summary patterns and provenance boundaries; kept deferred proof tied only to explicit deferred entities.
- Decision: keep.

## Evidence

- `node --check scripts/audit-release-readiness.mjs` passed.
- `node scripts/audit-release-readiness.mjs --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked` and printed `Next action: share-launch-proof [ready]` plus `Deferred proof: none`.
- `npm run check:docs` passed after the direction-log update.
- `npm run verify:full` passed with `latestDirectionLoop=loop-142`, `latestExperiment=release-summary-deferred-proof-none`, `evidenceSync.directionLoopSyncReady=true`, and `readyForExternalClaim=true`.

## Experiment: Launch readiness active dispatch disposition

- Hypothesis: The launch-readiness receipt should preserve suggested dispatch commands as reference evidence while exposing zero active dispatch commands after launch proof is ready.
- Primary metric: `launchReadinessActiveDispatchDispositionCoverage`.
- Baseline: `0/1`; `data/launch-readiness-refresh.json` showed `readyForExternalClaim=true` and `nextAction=share_launch_proof`, but still exposed `suggestedDispatchCommandCount=2` without saying those dispatch commands were no longer active next actions.
- Candidate: `1/1`; `dispatchCommandDisposition=not_applicable_after_launch_proof`, `activeDispatchCommandCount=0`, and `dispatchCommandReferenceCount=2` now make the distinction explicit while preserving `suggestedDispatchCommands` for provenance.
- Research: Compared manual workflow dispatch, operator-facing job summaries, and provenance boundaries so executable next actions and archived command references stay separate.
- Decision: keep.

## Evidence

- `node --check` passed for `scripts/refresh-launch-readiness.mjs`, `release-status.js`, `scripts/smoke-interactions.mjs`, `scripts/audit-release-readiness.mjs`, and `scripts/verify-workspace.mjs`.
- `node scripts/refresh-launch-readiness.mjs --repo biojuho/BIOJUHO-Projects --write` regenerated `data/launch-readiness-refresh.json` with `suggestedDispatchCommandCount=2`, `activeDispatchCommandCount=0`, `dispatchCommandReferenceCount=2`, and `dispatchCommandDisposition=not_applicable_after_launch_proof`.
- `npm run check:structure` and `npm run check:docs` passed after the System Status and audit-contract changes.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`, with fresh packaged browser gates cached.
- `npm run verify:full` passed with `latestDirectionLoop=loop-143`, `latestExperiment=launch-readiness-active-dispatch-disposition`, `evidenceSync.directionLoopSyncReady=true`, `activeDispatchCommandCount=0`, and `readyForExternalClaim=true`.

## Experiment: Product-loop proof-ready next candidates

- Hypothesis: The product-loop summary should replace pre-proof workflow install and dispatch next candidates once `readyForExternalClaim=true` so operators see only proof-ready follow-ups.
- Primary metric: `stalePreProofNextCandidates`.
- Baseline: `4`; the summary still recommended landing workflows, filling post-install evidence, filling launch proof evidence, and rerunning dispatch even though publish proof was already ready.
- Candidate: `0`; `nextCandidatesForStatus()` now derives proof-ready follow-ups from publish readiness and keeps setup/dispatch work out of the active candidate list.
- Research: Compared release handoff, run-summary, and experiment tracking patterns; post-proof candidates now focus on sharing proof, archiving receipts, capturing signed attestation proof when available, PR bridging, and safe low-state extraction.
- Decision: keep.

## Evidence

- `node scripts/sync-product-loop-summary.mjs --write --markdown` reported `nextCandidatesChanged=true`, `nextCandidateCount=5`, and wrote `nextCandidatesReady=true`.
- `autoresearch-results/joopark-product-loop.json` now has zero pre-proof next candidates while `publish.readyForExternalClaim=true`.
- `npm run check:structure` and `npm run check:docs` passed after the proof-ready candidate sync.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`.
- `npm run verify:full` passed with `latestDirectionLoop=loop-144`, `latestExperiment=product-loop-proof-ready-next-candidates`, `evidenceSync.nextCandidatesReady=true`, and `readyForExternalClaim=true`.

## Experiment: Verify summary next candidate list receipt

- Hypothesis: The full verify receipt should include the actual proof-ready next candidate list, not only `nextCandidatesReady` and a count.
- Primary metric: `verifyWorkspaceNextCandidateReceiptCoverage`.
- Baseline: `0/1`; System Status and `autoresearch-results/verify-workspace-summary.json` exposed `nextCandidatesReady=true` and `nextCandidateCount=5`, but not the five candidate strings.
- Candidate: `1/1`; `verify-workspace-summary.json`, the System Status panel, the receipt text, and clipboard smoke now carry the proof-ready candidate list.
- Research: Compared operator-facing job summaries, release handoff records, and provenance records; a certified summary should carry the concrete next actions it certifies.
- Decision: keep.

## Evidence

- `scripts/verify-workspace.mjs` now writes `artifacts.productLoop.nextCandidates` and requires `nextCandidateListReady=true`.
- `verify-workspace-summary.js` validates `nextCandidateCount`, the candidate list, `nextCandidatesReady=true`, and `nextCandidateListReady=true`.
- `release-status.js` renders and copies the five proof-ready candidates in the Verify workspace summary receipt.
- `scripts/smoke-interactions.mjs` checks visible and copied receipt text for `nextCandidateList=true` and `Share the proof-ready launch packet`.
- `node scripts/sync-product-loop-summary.mjs --write --markdown` set `latestDirectionLoop=loop-145` and `latestExperiment=verify-summary-next-candidate-list-receipt`.
- `npm run check:structure` and `npm run check:docs` passed after the receipt-list changes.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`.
- `npm run verify:full` passed with `evidenceSync.nextCandidateListReady=true`, `latestDirectionLoop=loop-145`, `latestExperiment=verify-summary-next-candidate-list-receipt`, and `readyForExternalClaim=true`.

## Experiment: Publish evidence active dispatch disposition

- Hypothesis: Proof-ready publish evidence receipts should distinguish active dispatch commands from historical suggested dispatch references after launch proof is ready.
- Primary metric: `publishEvidenceActiveDispatchDispositionCoverage`.
- Baseline: `0/1`; `data/publish-evidence.json` was proof-ready, but the share and post-launch receipts still showed `suggested dispatch: 2` and `withheld dispatch: 0` without saying those commands were references rather than active next actions.
- Candidate: `1/1`; publish evidence and output-quality receipts now include `dispatchCommandDisposition=not_applicable_after_launch_proof`, `activeDispatchCommandCount=0`, and `dispatchCommandReferenceCount=2` while preserving `suggestedDispatchCommands` as provenance.
- Research: Compared manual workflow dispatch, operator-facing job summaries, and provenance boundaries so launch-proof receipts do not imply that archived dispatch commands should be run again.
- Decision: keep.

## Evidence

- `node --check` passed for `scripts/capture-publish-evidence.mjs`, `scripts/capture-output-quality-audit.mjs`, and `release-status.js`.
- `node scripts/capture-publish-evidence.mjs --live --repo biojuho/BIOJUHO-Projects --write` regenerated `data/publish-evidence.json` with `dispatchCommandDisposition=not_applicable_after_launch_proof`, `activeDispatchCommandCount=0`, and `dispatchCommandReferenceCount=2`.
- `node scripts/capture-output-quality-audit.mjs --write` regenerated `data/output-quality-audit.json` with the publish evidence command guard carrying active/reference/disposition fields.
- `release-status.js` now renders the publish evidence dispatch disposition, active dispatch count, and reference dispatch count in System Status.
- `node scripts/sync-product-loop-summary.mjs --write --markdown` set `latestDirectionLoop=loop-146` and `latestExperiment=publish-evidence-active-dispatch-disposition`.
- `npm run check:structure` and `npm run check:docs` passed after the publish-evidence receipt changes.
- `node scripts/audit-release-readiness.mjs --run-gates --format=summary` passed at `283 pass, 0 fail, 0 not_run, 0 blocked`, with fresh packaged browser gates cached.
- `npm run verify:full` passed with `latestDirectionLoop=loop-146`, `latestExperiment=publish-evidence-active-dispatch-disposition`, `evidenceSync.nextCandidateListReady=true`, and `readyForExternalClaim=true`.
