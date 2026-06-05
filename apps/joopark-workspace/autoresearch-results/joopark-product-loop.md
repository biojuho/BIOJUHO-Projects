# JooPark Product AutoResearch Loop

Generated: 2026-06-05T19:53:06+09:00

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

- Hypothesis: Candidate priority scores become more actionable when each adoption-candidate card shows a next recommended review action and reason.
- Primary metric: `candidateNextActionVisible` in packaged interaction smoke.
- Baseline: candidate cards had stage, metrics, links, and priority, but no explicit next action.
- Candidate: candidate cards compute and render action labels such as `아키텍처 벤치` and `리스크 리뷰` with reasons; smoke verifies `colanode/colanode` and `opf/openproject`.
- Decision: keep.

## Evidence

- `node scripts/audit-release-readiness.mjs --run-gates` passed with `portfolio_candidate_next_action`.
- Packaged interaction smoke reported `candidateNextActionVisible: true`, `workspaceCompetitiveCandidateVisible: true`, and `portfolioCandidateRanked: true`.

## Experiment: main-compatible release branch

- Hypothesis: Product launch readiness improves when the latest JooPark Workspace release is available on a branch based on repository `main`, because GitHub can open a normal review PR.
- Primary metric: PR-compatible branch state.
- Baseline: standalone branch `codex/joopark-workspace-release` was pushed, but PR creation was blocked because it had no common history with `main`.
- Candidate: branch `codex/joopark-workspace-release-main` is based on `biojuho-projects/main` and carries the latest app, data snapshots, release gates, and AutoResearch evidence under `apps/joopark-workspace/`.
- Decision: keep.

## Evidence

- `npm run lint` passed in `apps/joopark-workspace`.
- `npm run build` and `node scripts/verify-release.mjs` passed in `apps/joopark-workspace`.
- `npm run verify` passed 22/22 in `apps/joopark-workspace`, including packaged route, mobile, interaction, and accessibility gates.
- `PYTHONPATH=.:packages:automation:apps/desci-platform:automation/DailyNews/src:automation/DailyNews/scripts uv run --with pytest pytest tests/test_workspace_regressions.py tests/test_workspace_smoke.py -q` passed `20 passed, 2 skipped`.
- `python3 ops/scripts/run_workspace_smoke.py --scope workspace --json-out var/tmp/joopark-workspace-scope-smoke-rerun.json` passed 6/6 after installing dashboard dependencies with `npm ci --prefix apps/dashboard`.
- Pushed `9f07a71 Port JooPark release to main branch` to `biojuho-projects/codex/joopark-workspace-release-main`.
- Created draft PR `#149`: `https://github.com/biojuho/BIOJUHO-Projects/pull/149`.

## Experiment: GitHub release artifact workflow

- Hypothesis: Product launch readiness improves when GitHub can package the static JooPark Workspace release and expose it as a downloadable Actions artifact without requiring deployment credentials.
- Primary metric: publishable release artifact workflow availability.
- Baseline: no `joopark-workspace-release.yml` workflow existed, so PR and main builds did not produce a JooPark Workspace release artifact.
- Candidate: a local `.github/workflows/joopark-workspace-release.yml` package workflow passed syntax, release, and packaged-browser gates, but could not be published from this OAuth session.
- Decision: reject.

## Evidence

- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/joopark-workspace-release.yml"); puts "workflow_yaml=pass"'` passed.
- `git diff --check` passed.
- `python3 ops/scripts/pr_self_review.py --base biojuho-projects/main` passed with 0 red findings.
- `npm run lint`, `npm run build`, `node scripts/verify-release.mjs`, and `npm run test` passed in `apps/joopark-workspace`.
- Packaged-release smoke passed 15 desktop routes, 15 mobile routes, 18 interaction steps, Markdown sanitizer checks, candidate next-action checks, and accessibility checks with 0 console, network, and layout issues.
- `git push biojuho-projects codex/joopark-workspace-release-main` was rejected because the OAuth app cannot create or update `.github/workflows/joopark-workspace-release.yml` without `workflow` scope.
- Removed the workflow file from the candidate branch and kept the blocker as evidence rather than adopting an unpublishable change.

## Experiment: GitHub prerelease asset publication

- Hypothesis: Product launch readiness improves when the JooPark Workspace package is available as a public GitHub prerelease asset, even without workflow-edit scope.
- Primary metric: public downloadable release assets.
- Baseline: `gh release list --repo biojuho/BIOJUHO-Projects --limit 20` returned no releases, and no matching `joopark-workspace` tags existed.
- Candidate: `joopark-workspace-v3.0.0-rc.1` prerelease targets `codex/joopark-workspace-release-main` and uploads `joopark-workspace-v3.0.0-rc.1.zip`.
- Decision: keep.

## Evidence

- Built the release package from a clean detached worktree at `c9d689a`.
- `node scripts/verify-release.mjs` passed with `sourceCommit: c9d689a`, `sourceDirty: false`, and 11 runtime files.
- `npm run test` passed on the exact release asset, including 15 desktop routes, 15 mobile routes, 18 interaction steps, Markdown sanitizer checks, candidate next-action checks, and accessibility checks with 0 console, network, and layout issues.
- `gh release create joopark-workspace-v3.0.0-rc.1 ... --target codex/joopark-workspace-release-main --prerelease` succeeded after the short-SHA target attempt was rejected by the API.
- Published release: `https://github.com/biojuho/BIOJUHO-Projects/releases/tag/joopark-workspace-v3.0.0-rc.1`.
- Published asset: `joopark-workspace-v3.0.0-rc.1.zip`, 137650 bytes, `sha256:da4f72efcd547f0dbe8a0510e0d9d8d7939ad9e611f205a24287dcca2b81bcf6`.
- `git ls-remote --tags biojuho-projects 'joopark-workspace-v3.0.0-rc.1*'` showed the tag at `c9d689a2d935c89a38370e62abef1635baa53d79`.

## Experiment: final GitHub release publication

- Hypothesis: Product launch is materially stronger when the merged `main` commit has a non-prerelease release asset, not only an RC asset.
- Primary metric: public final release assets.
- Baseline: only `joopark-workspace-v3.0.0-rc.1` existed.
- Candidate: `joopark-workspace-v3.0.0` targets the `main` merge commit and uploads `joopark-workspace-v3.0.0.zip`.
- Decision: keep.

## Evidence

- PR `#149` merged into `main` as `bf7852dfed3204b869b94b893e6e628c1c5c2d47`.
- Main-branch workflows after merge passed: Workspace Smoke Test, Security & Quality Gate, CodeQL Security Scan, and Gitleaks Secret Scan.
- Built the final release package from a clean detached worktree at `bf7852d`.
- `node scripts/verify-release.mjs` passed with `sourceCommit: bf7852d`, `sourceDirty: false`, and 11 runtime files.
- `npm run test` passed on the exact final release asset, including 15 desktop routes, 15 mobile routes, 18 interaction steps, Markdown sanitizer checks, candidate next-action checks, and accessibility checks with 0 console, network, and layout issues.
- Published release: `https://github.com/biojuho/BIOJUHO-Projects/releases/tag/joopark-workspace-v3.0.0`.
- Published asset: `joopark-workspace-v3.0.0.zip`, 137649 bytes, `sha256:704ca4fadaa4f05bbfd7bc635e6914b3638a1a158561c2a08b158b93263e9681`.
- `git ls-remote --tags biojuho-projects 'joopark-workspace-v3.0.0'` showed the tag at `bf7852dfed3204b869b94b893e6e628c1c5c2d47`.

## Experiment: release publication surface

- Hypothesis: Users should be able to find and verify the public release from the product settings screen and README, not only from GitHub release history.
- Primary metric: release-publication audit and browser-smoke coverage.
- Baseline: the app documented local package generation, but did not surface the actual public release URL, ZIP asset, target commit, or SHA-256 checksum in the app UI; the release audit had no publication-surface requirement.
- Candidate: settings renders a `공개 릴리스` panel with release tag, download link, target commit, and SHA-256 digest; README mirrors the release URL and digest; interaction smoke asserts the card/link/digest; release audit adds `release_publication_surface`.
- Decision: keep.

## Evidence

- `npm run lint` passed in `apps/joopark-workspace`.
- `npm run build` and `node scripts/verify-release.mjs` passed after adding the release surface.
- `node scripts/audit-release-readiness.mjs --run-gates` passed 23/23 with `release_publication_surface`.
- Packaged interaction smoke reported `releaseInfoVisible: true`, along with `candidateNextActionVisible: true`, `portfolioCandidateRanked: true`, and 0 console/network/layout issues.
- Computer Use app attachment was attempted for Chrome and Safari at `http://127.0.0.1:5181/#settings`, but the local Computer Use server returned `cgWindowNotFound` for both native app windows; deterministic Chrome/CDP smoke remains the verified browser evidence.

## Next Loop

- Continue with the highest-impact product gap after the next full gate: merge-ready release-surface PR, post-release workflow deprecation cleanup, or deeper UI workflow coverage.
