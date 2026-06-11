# GitHub Project Discovery

Generated: 2026-06-10T03:50:18.804Z

Status: pass

This is a read-only launch-support inventory. It discovers local Git checkouts and the biojuho GitHub repositories, then ranks related projects by release relevance, recency, and local checkout presence.

## Summary

- Local Git checkouts: 5
- GitHub repositories: 14
- Ranked projects: 9
- GitHub repositories with pushedAt: 14
- Fresh GitHub repositories (30d): 14
- Private GitHub repositories redacted: 8
- Private local remotes redacted: 1
- Private ranked project rows redacted: 8
- Direct release target ready: true
- Reproducible discovery command: `node scripts/capture-github-project-discovery.mjs --owner biojuho --local-root .. --max-depth 4 --write --markdown`
- External actions performed: read-only discovery only
- Actionable project coverage: 9/9
- Release target included in top-ranked candidates: true

## Freshness Evidence

- Source fields: updatedAt, pushedAt, stargazerCount, repositoryTopics
- Ranking uses pushedAt: true
- Freshness evidence coverage: 1/1

## Local Scan Reproducibility

- Local root mode: relative-to-local-root
- Max depth: 4
- Ignored directories: node_modules, vendor, dist, archive, autoresearch-results, .Trash
- Reproducibility evidence coverage: 1/1

## Public Artifact Privacy

- Absolute local path exposure: false
- Private GitHub metadata exposure: 0
- Private GitHub row exposure: 0
- Private metadata exposure reduction: 9 -> 0
- Private row exposure reduction: 8 -> 0
- Redacted fields: localRoot, localRepos[].path, currentRepo.path, rankedProjects[].localPath, private rankedProjects[].nameWithOwner, private rankedProjects[].url, private rankedProjects[].description, private localRepos[].remotes[].url, private localRepos[].remoteNames[]

## Top Projects

| Project | Relation | Local | Updated | Pushed | Stars | Next action |
| --- | --- | --- | --- | --- | ---: | --- |
| biojuho/BIOJUHO-Projects | current-release-target | JooPark Project | 2026-06-08T23:12:26Z | 2026-06-08T23:12:22Z | 0 | Keep launch proof, Pages workflow parity, and product smoke gates green before any public claim. |
| biojuho/autoresearch-skill-system | autoresearch-toolchain | no | 2026-06-05T09:17:41Z | 2026-06-05T09:17:36Z | 0 | Use as reference tooling only; do not mix toolchain edits into the product release branch without a separate gate. |
| local:Joopark | joopark-product | Joopark | unknown | unknown | 0 | Inspect its own WORKLOG and gates before mutating; keep this product release scope separate. |
| biojuho/vibe-coding | adjacent-workspace | no | 2026-06-05T09:55:01Z | 2026-06-05T09:54:57Z | 1 | No local mutation planned; keep as portfolio/reference unless the user explicitly scopes it. |
| Veritas-7/autoresearch-skill-system | autoresearch-toolchain | JooPark Project/autoresearch-skill-system | unknown | unknown | 0 | Use as reference tooling only; do not mix toolchain edits into the product release branch without a separate gate. |
| biojuho/joolife | portfolio-repository | no | 2026-02-24T08:17:17Z | 2026-06-04T22:08:20Z | 0 | No local mutation planned; keep as portfolio/reference unless the user explicitly scopes it. |
| biojuho/node-test | portfolio-repository | no | 2026-06-04T08:43:13Z | 2026-06-04T08:42:31Z | 0 | No local mutation planned; keep as portfolio/reference unless the user explicitly scopes it. |
| biojuho/sajuchain | portfolio-repository | no | 2026-02-25T12:30:00Z | 2026-06-04T07:11:09Z | 0 | No local mutation planned; keep as portfolio/reference unless the user explicitly scopes it. |
| local:Haplnscience/DW 201 | local-checkout | Haplnscience/DW 201 | unknown | unknown | 0 | Inspect its own WORKLOG and gates before mutating; keep this product release scope separate. |

## A/B Decision

- Baseline: ad_hoc_terminal_search (0 artifacts)
- Candidate: reproducible_github_project_discovery_artifact (2 artifacts)
- Metric: githubDiscoveryActionableProjectCoverage
- Decision: keep_b

## Guard

Do not push, deploy, delete branches, edit unrelated repositories, or publish external copy from this discovery artifact without explicit user approval.
