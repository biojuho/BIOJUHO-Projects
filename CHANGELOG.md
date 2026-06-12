# Changelog

All notable workspace-level changes are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project follows date-based release tags (`YYYY-MM-DD`) rather than SemVer because the workspace bundles multiple independent products.

Per-project changelogs (when they exist) live under each project's own directory.

## [Unreleased]

### Added
- Root `LICENSE` (MIT) — clarifies legal terms for the public repository.
- Root `README.md` — entry point with project map, quick start, and documentation index.
- Root `CHANGELOG.md` (this file) — workspace-level change history.
- `mypy-shared` hook in `.pre-commit-config.yaml` — type-check `packages/shared` against the strict override already in `pyproject.toml`. Opt-in (manual stage): `pre-commit run --hook-stage manual mypy-shared --all-files`.

### Changed
- _(none)_

### Removed
- _(none)_

### Security
- _(none)_

---

## Prior history

Pre-changelog history is preserved in `git log` and dated reports under `docs/reports/`. Notable hardening milestones:

- **2026-05-15** — Quality gate verification: hard gate now enforces `unpinned-uses` (0 findings); `zizmor` informational findings tracked separately.
- **2026-05-15** — Healthcheck observability: per-import timeout raised to 20 s and silent-swallow failure cases now surface item names.
- **2026-05-08** — Supply-chain hardening: `pinact` (SHA-pin every GitHub Action) and `zizmor` adopted across 26 workflows.
- **2026-04-13** — Cloud migration of P2/P3 pipelines to GitHub Actions + Supabase; Telegram and cost alerts wired.
- **2026-04-12** — Dedicated `DAILYNEWS_NOTION_*` secrets to stop cross-publishing into the GetDayTrends database.
- **2026-04-06** — Deep system debug: 47 findings → 30 fixes, `.agent/` ignored.
- **2026-04-05** — Coverage hardening: 27 regression tests for API/LLM/DB/timeout fault paths.

See `git log --oneline main` for the authoritative history.
