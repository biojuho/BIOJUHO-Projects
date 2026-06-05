# JooPark Product AutoResearch Loop

Generated: 2026-06-05T18:50:00+09:00

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

## Next Loop

- Add a small machine-readable AutoResearch result summary so the next run can compare baseline/candidate metrics without scraping Markdown.
- Continue with the highest-impact product gap after the next full gate: publish/remote state, direct launch packaging, or deeper UI workflow coverage.
